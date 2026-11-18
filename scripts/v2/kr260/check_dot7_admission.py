"""Require measured numerical/source/OOC relief before full synthesis."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    summary = json.loads((ROOT / "build/v2/dot7-ooc-summary.json").read_text())
    old, new = summary["groups"]["attention"]
    if old["lanes"] != 4 or new["lanes"] != 4:
        raise ValueError("Wrong OOC comparison size")
    if new["clb_luts"] >= old["clb_luts"] or new["memory_luts"] >= old["memory_luts"]:
        raise ValueError("Shared read did not reduce total/memory LUTs; review before full build")
    for relative, digest in summary["source_sha256"].items():
        frozen = ROOT / relative
        if hashlib.sha256(frozen.read_bytes()).hexdigest() != digest:
            raise ValueError(f"OOC source evidence changed: {relative}")
        original = ROOT / "rtl/v2" / ("common" if frozen.name == "sequential_divider.sv" else "encoder") / frozen.name
        if hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Current RTL differs from OOC source: {original}")
    report = json.loads((ROOT / "build/v2/rtl-dot7-large-check/summary.json").read_text())
    if report["profile"]["local_accumulator_controls"] != 3 or report["profile"]["max_hidden"] != 1024:
        raise ValueError("Wrong tested capacity/RAM mode")
    for relative, digest in report["rtl_sha256"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Current RTL differs from complete regressions: {relative}")
    if "PASS: residual cursor frozen equivalence 281736 writes" not in (ROOT / "build/v2/rtl-dot7-arithmetic/residual.log").read_text():
        raise ValueError("Cursor reset/boundary equivalence evidence missing")
    focused = ROOT / "build/v2/rtl-dot7-attention-equivalence"
    if "PASS: shared-read frozen equivalence 11 profiles" not in (focused / "result.log").read_text():
        raise ValueError("Shared-read nonzero/head-group/reset equivalence evidence missing")
    hashes = {name: digest for digest, name in (line.split(maxsplit=1) for line in (focused / "source-sha256.txt").read_text().splitlines())}
    if hashes["attention_engine.sv"] != hashlib.sha256((ROOT / "rtl/v2/encoder/attention_engine.sv").read_bytes()).hexdigest():
        raise ValueError("Focused shared-read RTL hash changed")
    legacy = (ROOT / "build/v2/kr260-opt-dot6-large/rtl-snapshot/encoder/attention_engine.sv").read_bytes().replace(b"module attention_engine", b"module attention_legacy", 1)
    if hashes["attention_legacy.sv"] != hashlib.sha256(legacy).hexdigest():
        raise ValueError("Focused comparison is not the frozen dual-read baseline")
    print("PASS: shared RAM lowers memory/total LUTs; numerical and OOC source hashes agree")


if __name__ == "__main__":
    main()
