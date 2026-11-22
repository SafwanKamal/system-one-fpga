"""Copy the D3 decoder into this checkout and substitute the two BF16 products."""

import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path("build/v2/dual-port-study")
OUTPUT = ROOT / "build/v2/v9j/src"
GEMINI = ROOT.parents[3] / "system-one-fpga-gemini"
GEMINI_COMMIT = "ecc56d22ecd56104e06e2036cb28040152358e91"
HEADER = "experiments/xmul/xmul_hls.hpp"
DECODER = "qwen_decoder.cpp"
CSR = re.compile(
    r"^\s*#pragma HLS INTERFACE s_axilite port=(\w+) bundle=control"
    r"(?: offset=(0x[0-9a-fA-F]+))?[^\S\n]*$", re.MULTILINE
)


def replace_one(source, old, new):
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Expected one occurrence of {old!r}, found {count}")
    return source.replace(old, new)


def make(study_root, gemini):
    baseline = study_root / STUDY / "src-d3"
    reference = study_root / STUDY / "src-s2"
    source = (baseline / DECODER).read_text(encoding="utf-8")
    if source.count("static const unsigned TILE=256,P=4;") != 1:
        raise ValueError("Expected the D3 P=4 attention configuration")
    source = replace_one(
        source, "#include <ap_int.h>",
        '#include <ap_int.h>\n#include "xmul_hls.hpp"\n'
        'static_assert(xmul_hls::kDefaultPolicy == xmul_hls::DenormalPolicy::FTZ,\n'
        '              "v9j requires flush-to-zero products");',
    )
    source = replace_one(
        source,
        "static float from_bf16(ap_uint<16> h) {\n"
        "#pragma HLS INLINE\n"
        "    return asfloat(uint32_t(h.to_uint())<<16);\n}\n",
        "",
    )
    source = replace_one(
        source,
        "// Eight BF16 lanes (one 128-bit half of a cache word) widened to FP32.\n"
        "static float bf16_lane(word w,unsigned chunk,unsigned lane)",
        "// Extract a raw BF16 lane from one 128-bit half of a cache word.\n"
        "static uint16_t bf16_lane(word w,unsigned chunk,unsigned lane)",
    )
    source = replace_one(
        source, "return from_bf16(half.range(lane*16+15,lane*16));",
        "ap_uint<16> bits=half.range(lane*16+15,lane*16);\n    return bits.to_uint();",
    )
    source = replace_one(source, "lanef(qw,lane)*bf16_lane(key,chunk,lane)",
                         "mul_xb(lanef(qw,lane),bf16_lane(key,chunk,lane))")
    source = replace_one(source, "m*bf16_lane(value,c,lane)",
                         "mul_xb(m,bf16_lane(value,c,lane))")
    if source.count("bf16_lane(") != 3 or "from_bf16(" in source:
        raise ValueError("Unexpected BF16 lane extraction or widening site")

    def csr(text):
        entries = sorted(CSR.findall(text))
        pragma_count = len(re.findall(r"^\s*#pragma HLS INTERFACE s_axilite\b", text, re.MULTILINE))
        if not entries or pragma_count != len(entries) or len({port for port, _ in entries}) != len(entries):
            raise ValueError("Unrecognized or duplicate AXI-Lite CSR pragma")
        return entries

    registers = csr((reference / DECODER).read_text(encoding="utf-8"))
    if csr(source) != registers:
        raise ValueError("V9J AXI-Lite CSR map differs from v9h")
    header = subprocess.check_output([
        "git", "-c", f"safe.directory={gemini.as_posix()}", "-C", str(gemini),
        "show", f"{GEMINI_COMMIT}:{HEADER}",
    ])
    expected = {item.name for item in baseline.iterdir()} | {"xmul_hls.hpp"}
    if OUTPUT.exists() and any(item.name not in expected for item in OUTPUT.iterdir()):
        raise ValueError(f"Unexpected files in {OUTPUT}")
    shutil.copytree(baseline, OUTPUT, dirs_exist_ok=True)
    (OUTPUT / DECODER).write_text(source, encoding="utf-8", newline="\n")
    (OUTPUT / "xmul_hls.hpp").write_bytes(header)
    print(OUTPUT)
    print("AXI-Lite CSR map identical to v9h:", ", ".join(
        f"{port}@{offset}" if offset else port
        for port, offset in sorted(registers, key=lambda kv: int(kv[1] or "0", 16))
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_root", type=Path, help="checkout containing the generated D3 and v9h sources")
    parser.add_argument("--gemini-worktree", type=Path, default=GEMINI,
                        help="Gemini worktree holding the pinned published commit")
    args = parser.parse_args()
    make(args.study_root.resolve(), args.gemini_worktree.resolve())
