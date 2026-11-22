"""Generate B=16 sources in this worktree from an audited v9i checkout."""

import argparse
import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V9I = Path("build/v2/v9i/src")
V9H = Path("build/v2/dual-port-study/src-s2")
OUTPUT = ROOT / "build/v2/v9k/src"
AUDITED_V9I = {
    "matrix_q8.hpp": "71c0e16fb56c37cc4cfdcb17332f240414125a71fdcd34f18a49ccaf20548d82",
    "model_profile.hpp": "d9dd986eadfeae4f8b4a4c9ae7aa0076c7e9e7cbd39a51323460e76842ba81cd",
    "qwen_decoder.cpp": "8084999de5d9b4c132a0eee460318dd8978a60c91a297dd43681ba2c08701cc8",
}


def csr(source):
    text = source.decode("utf-8")
    pragmas = re.findall(r"^\s*#pragma HLS INTERFACE s_axilite ([^\r\n]+)", text, re.M)
    entries = {}
    pattern = r"port=(\w+) bundle=control(?: offset=(0x[0-9a-fA-F]+))?"
    for pragma in pragmas:
        match = re.fullmatch(pattern, pragma.strip())
        if not match or match[1] in entries:
            raise ValueError(f"Unexpected or duplicate CSR interface: {pragma}")
        entries[match[1]] = int(match[2], 16) if match[2] else None
    signature = re.findall(r'extern "C" void qwen_decoder\s*\(([^)]+)\)', text)
    if len(entries) != 14 or len(signature) != 1:
        raise ValueError("Expected 14 AXI-Lite ports and one qwen_decoder signature")
    return entries, " ".join(signature[0].split())


def audited_sources(source_root):
    directory = source_root / V9I
    if {p.name for p in directory.iterdir()} != AUDITED_V9I.keys():
        raise ValueError(f"Source inventory drift in {directory}")
    sources = {name: (directory / name).read_bytes() for name in AUDITED_V9I}
    reference = csr((source_root / V9H / "qwen_decoder.cpp").read_bytes())
    candidate = csr(sources["qwen_decoder.cpp"])
    if candidate != reference:
        raise ValueError(f"CSR interface differs from v9h src-s2: {candidate} != {reference}")
    for name, expected in AUDITED_V9I.items():
        # Normalize line endings only so a different checkout's CRLF policy is harmless.
        payload = sources[name].replace(b"\r\n", b"\n")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"Source drift in {directory / name}; re-audit its batch paths")
    return sources


def patch(payload, old, new, count=1):
    newline = b"\r\n" if b"\r\n" in payload else b"\n"
    before = old.encode().replace(b"\n", newline)
    after = new.encode().replace(b"\n", newline)
    actual = payload.count(before)
    if actual != count:
        raise ValueError(f"Patch count {actual} != {count} for {old!r}")
    return payload.replace(before, after)


def widen_batch(sources):
    sources = sources.copy()
    sources["model_profile.hpp"] = patch(
        sources["model_profile.hpp"], "static const unsigned B=8,", "static const unsigned B=16,",
    )
    # Sixteen slots x eight FP32 partials fill the 4096-bit HLS stream limit
    # for each weight half. Keep their row boundaries synchronized.
    decoder = sources["qwen_decoder.cpp"]
    for old, new in (
        ('hls::stream<matrix_pair<B>> completed("completed");',
         'hls::stream<matrix_partials<B>> completed_a("completed_a"),completed_b("completed_b");'),
        ("#pragma HLS STREAM variable=completed depth=4",
         "#pragma HLS STREAM variable=completed_a depth=4\n#pragma HLS STREAM variable=completed_b depth=4"),
        ("#pragma HLS BIND_STORAGE variable=completed type=fifo impl=srl",
         "#pragma HLS BIND_STORAGE variable=completed_a type=fifo impl=srl\n"
         "#pragma HLS BIND_STORAGE variable=completed_b type=fifo impl=srl"),
        ("half,cols,batch,completed);", "half,cols,batch,completed_a,completed_b);"),
        ("reduce_q8_dual<B,F>(completed,", "reduce_q8_dual<B,F>(completed_a,completed_b,"),
    ):
        decoder = patch(decoder, old, new)
    if csr(decoder) != csr(sources["qwen_decoder.cpp"]):
        raise ValueError("Batch widening changed the CSR declaration")
    sources["qwen_decoder.cpp"] = decoder

    matrix = sources["matrix_q8.hpp"]
    marker = "static void accumulate_q8_dual_packed("
    if matrix.count(marker.encode()) != 1:
        raise ValueError("Expected one packed dual accumulator")
    prefix, suffix = matrix.split(marker.encode(), 1)
    streams = "hls::stream<matrix_partials<TOKENS>>& completed_a,hls::stream<matrix_partials<TOKENS>>& completed_b"
    for old, new, count in (
        ("hls::stream<matrix_pair<TOKENS>>& completed", streams, 2),
        ("matrix_pair<TOKENS> result={};", "matrix_partials<TOKENS> result[2]={};", 1),
        ("result.values[h][b][i]=values[i];", "result[h].values[b][i]=values[i];", 1),
        ("completed.write(result);block=0;", "completed_a.write(result[0]);completed_b.write(result[1]);block=0;", 1),
        ("matrix_pair<TOKENS> pair;\n#pragma HLS ARRAY_PARTITION variable=pair.values complete",
         "matrix_partials<TOKENS> pair_a,pair_b;\n#pragma HLS ARRAY_PARTITION variable=pair_a.values complete\n"
         "#pragma HLS ARRAY_PARTITION variable=pair_b.values complete", 1),
        ("if(h==0)pair=completed.read();", "if(h==0){pair_a=completed_a.read();pair_b=completed_b.read();}", 1),
        ("h?pair.values[1][b][i]:pair.values[0][b][i]", "h?pair_b.values[b][i]:pair_a.values[b][i]", 1),
    ):
        suffix = patch(suffix, old, new, count)
    sources["matrix_q8.hpp"] = prefix + marker.encode() + suffix
    return sources


def generate(source_root):
    sources = widen_batch(audited_sources(source_root))
    if OUTPUT.exists():
        existing = {p.name for p in OUTPUT.iterdir()}
        if existing != sources.keys() or any(
            (OUTPUT / name).read_bytes() != payload for name, payload in sources.items()
        ):
            raise ValueError(f"Existing output differs from the audited build: {OUTPUT}")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.parent / "src-staging"
        temporary.mkdir()
        try:
            for name, payload in sources.items():
                (temporary / name).write_bytes(payload)
            temporary.rename(OUTPUT)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    print(f"{OUTPUT}\nCSR map and declaration match v9h src-s2 (14 ports). Widened fields: none.")
    return OUTPUT


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, help="checkout containing v9i and v9h src-s2")
    args = parser.parse_args()
    generate(args.source_root.resolve())
