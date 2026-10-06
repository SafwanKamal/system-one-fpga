"""Request frames for the Ethernet testbench, and the checker for its responses.

    uv run python scripts/ethernet_vectors.py            # write simulation/vectors/ethernet_*
    uv run python scripts/ethernet_vectors.py --check    # decode simulation/ethernet_responses.hex

Frames are built with src/sysone/ethernet_protocol.py, the same encoder the host
tool uses, and the responses are decoded with the same decoder. So a passing run
checks the host software as well as the RTL: FCS, byte order, sequence numbers and
every one of the 151 logits against the NumPy golden model.

Besides the CLINC150 test set, the stream includes frames that must be ignored
(bad FCS, wrong EtherType, wrong destination MAC, a runt, a non-request message
type) and frames that exercise the parser (broadcast destination, a length field
longer than the frame, a long message, and the LAN8720A's CRS_DV toggle at the end
of a frame).
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rtl_pack import EDGE_CASES, load_qm                         # noqa: E402
from sysone.deployed import DEPLOYED_EXPORT  # noqa: E402
from sysone import ethernet_protocol as ep                       # noqa: E402
from sysone.data import load_clinc150                            # noqa: E402
from sysone.hashing import encode_corpus                         # noqa: E402

HOST_MAC = "02:00:00:00:00:aa"
END_OF_FRAME = 0x100
END_OF_FRAME_WITH_TOGGLE = 0x101


def golden_logits(qm, man, texts: list[bytes]) -> np.ndarray:
    m = man["model"]
    decoded = [t.decode("utf-8", errors="ignore") for t in texts]
    flat, offs = encode_corpus(decoded, m["n_buckets"], m["use_bigrams"], m["max_tokens"],
                               m["use_trigrams"], tuple(m["char_ngrams"]))
    return qm.forward_int(flat, offs)


def build_cases(limit: int) -> list[dict]:
    ds = load_clinc150()
    texts = EDGE_CASES + list(ds.test.texts)
    if limit:
        texts = texts[:limit]

    cases = []
    sequence = 1000

    def add(frame: bytes, text: bytes | None, note: str, toggle: bool = False):
        nonlocal sequence
        cases.append({"frame": frame, "text": text, "note": note, "toggle": toggle,
                      "sequence": sequence if text is not None else None})

    def request(text: bytes, **kw) -> bytes:
        return ep.encode_request_frame(text, sequence, HOST_MAC, **kw)

    # frames that must be ignored first, so a stuck parser shows up immediately
    good = request(b"what is my credit score")
    bad_fcs = bytearray(good)
    bad_fcs[30] ^= 0x01
    add(bytes(bad_fcs), None, "bad FCS")
    sequence += 1

    wrong_type = bytearray(ep.encode_request_frame(b"x", sequence, HOST_MAC, with_fcs=False))
    wrong_type[12:14] = b"\x08\x00"
    add(bytes(wrong_type) + ep.frame_check_sequence(bytes(wrong_type)), None, "IPv4 EtherType")
    sequence += 1

    add(request(b"not for us", fpga_mac="02:00:00:00:00:99"), None, "other destination MAC")
    sequence += 1

    runt = ep.encode_request_payload(b"hi", sequence)
    runt = ep.FPGA_MAC + ep.mac_bytes(HOST_MAC) + struct.pack(">H", ep.ETHERTYPE) + runt
    add(runt + ep.frame_check_sequence(runt), None, "runt, 26 bytes before the FCS")
    sequence += 1

    other_message = bytearray(ep.encode_request_frame(b"x", sequence, HOST_MAC, with_fcs=False))
    other_message[15] = 0x01                      # Genome's result message type
    add(bytes(other_message) + ep.frame_check_sequence(bytes(other_message)), None,
        "message type 0x01")
    sequence += 1

    # parser corner cases that must be answered
    add(request(b"book a flight to paris", fpga_mac=ep.BROADCAST_MAC), b"book a flight to paris",
        "broadcast destination")
    sequence += 1

    short = b"transfer money"
    frame = bytearray(ep.encode_request_frame(short, sequence, HOST_MAC, with_fcs=False))
    frame[20:22] = struct.pack(">H", 300)        # claims more text than the frame holds
    # the Ethernet padding zeros are separators, so the answer equals the text alone
    add(bytes(frame) + ep.frame_check_sequence(bytes(frame)), short, "length field too long")
    sequence += 1

    long_text = (" ".join(["please transfer money from my checking account to savings"] * 24)).encode()
    add(request(long_text), long_text, f"long message, {len(long_text)} bytes")
    sequence += 1

    add(request(b"set an alarm for six am"), b"set an alarm for six am", "CRS_DV toggle", toggle=True)
    sequence += 1

    for i, text in enumerate(texts):
        data = text.encode("utf-8")
        if len(data) > ep.MAXIMUM_TEXT_BYTES:
            continue                              # does not fit in one frame
        add(request(data), data, "edge case" if i < len(EDGE_CASES) else "test set",
            toggle=(i % 7 == 3))
        sequence += 1
    return cases


def write_vectors(limit: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    qm, man = load_qm(DEPLOYED_EXPORT)
    cases = build_cases(limit)

    answered = [c for c in cases if c["text"] is not None]
    logits = golden_logits(qm, man, [c["text"] for c in answered])

    with open(out / "ethernet_requests.hex", "w") as f:
        for c in cases:
            for b in c["frame"]:
                f.write(f"{b:03x}\n")
            f.write(f"{END_OF_FRAME_WITH_TOGGLE if c['toggle'] else END_OF_FRAME:03x}\n")
    # Verilator is two-state, so the testbench cannot find the end of a file by
    # looking for X; it reads the frame count instead.
    (out / "ethernet_frame_count.hex").write_text(f"{len(cases):08x}\n")
    with open(out / "ethernet_expect.hex", "w") as f:
        for c in cases:
            f.write(f"{1 if c['text'] is not None else 0}\n")

    expected = {"host_mac": HOST_MAC, "frames": len(cases), "answered": len(answered),
                "results": [{"sequence": c["sequence"], "note": c["note"],
                             "logits": [int(v) for v in row],
                             "class": int(np.argmax(row))}
                            for c, row in zip(answered, logits)]}
    (out / "ethernet_expected.json").write_text(json.dumps(expected))
    print(f"{len(cases)} frames ({len(answered)} answered, {len(cases) - len(answered)} ignored)"
          f" -> {out}")


def check(responses: Path, expected_path: Path) -> int:
    expected = json.loads(expected_path.read_text())
    words = [int(x, 16) for x in responses.read_text().split()]
    frames, current = [], []
    for w in words:
        if w == END_OF_FRAME:
            frames.append(bytes(current))
            current = []
        else:
            current.append(w)

    errors = 0
    results = expected["results"]
    if len(frames) != len(results):
        print(f"FAIL: {len(frames)} result frames, expected {len(results)}")
        errors += 1

    for i, (frame, want) in enumerate(zip(frames, results)):
        try:
            got = ep.decode_result_frame(frame)
        except ep.ProtocolError as e:
            print(f"frame {i}: {e}")
            errors += 1
            continue
        problems = []
        if got.destination_mac != expected["host_mac"]:
            problems.append(f"destination {got.destination_mac}")
        if got.source_mac != ep.mac_string(ep.FPGA_MAC):
            problems.append(f"source {got.source_mac}")
        if got.sequence_number != want["sequence"]:
            problems.append(f"sequence {got.sequence_number} != {want['sequence']}")
        if got.logits != want["logits"]:
            bad = sum(a != b for a, b in zip(got.logits, want["logits"]))
            problems.append(f"{bad} logits differ")
        if got.class_index != want["class"]:
            problems.append(f"class {got.class_index} != {want['class']}")
        top_two = sorted(want["logits"], reverse=True)[:2]
        if (got.top_logit, got.second_logit) != tuple(top_two):
            problems.append("top/second logit")
        if problems:
            errors += 1
            if errors <= 10:
                print(f"frame {i} ({want['note']}): " + ", ".join(problems))

    n_logits = sum(len(r["logits"]) for r in results)
    if errors:
        print(f"FAIL: {errors} bad result frames")
        return 1
    print(f"PASS: {len(frames)} result frames decoded by the host decoder, FCS good, "
          f"sequence numbers in order, {n_logits} logits bit-exact")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N messages")
    ap.add_argument("--out", default=str(ROOT / "simulation/vectors"))
    ap.add_argument("--responses", default=str(ROOT / "simulation/ethernet_responses.hex"))
    args = ap.parse_args()
    if args.check:
        raise SystemExit(check(Path(args.responses), Path(args.out) / "ethernet_expected.json"))
    write_vectors(args.limit, Path(args.out))


if __name__ == "__main__":
    main()
