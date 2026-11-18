"""Require complete wide-dimension and existing-model RTL evidence before packaging."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/v2/rtl-wide-check"


def main():
    checks = {}
    for name, words in (("kr260-wide.log", 10512), ("kr260-wide-l12.log", 5256)):
        raw = (OUT / name).read_bytes()
        log = raw.decode()
        rows = re.findall(r"case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)", log)
        if [int(r[1]) for r in rows] != [1, 2, 3, 4, 5, 12, 64, 128]:
            raise ValueError(f"Missing request lengths: {name}")
        if any(int(r[2]) or int(r[4]) or not 0 < int(r[5]) <= int(r[6]) for r in rows):
            raise ValueError(f"Invalid encoder results: {name}")
        if f"PASS: KR260 block bit-exact, 8 cases, {words} words compared" not in log:
            raise ValueError(f"Incomplete comparison: {name}")
        if "BUILD register 20803004" not in log:
            raise ValueError("Test did not run the 768-wide implementation")
        checks[name] = {"cases": 8, "words": words, "sha256": hashlib.sha256(raw).hexdigest(),
                        "encoder_clocks": [int(r[5]) for r in rows]}
    manifest = json.loads((OUT / "vectors/manifest.json").read_text())
    if not manifest["synthetic"] or not manifest["reference_verified"] or manifest["dims"]["hidden"] != 768:
        raise ValueError("Missing independent 768-wide integer-reference validation")
    digests = {}
    for line in (OUT / "source-sha256.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        digests[name.strip()] = digest
    files = json.loads((ROOT / "build/v2/rtl-bram-check/summary.json").read_text())["rtl_sha256"]
    hashes = {name: digests[name] for name in files}
    result = {"profile": {"max_hidden": 768, "mac_input_registers": 1, "exp_table_in_bram": 1},
              "hardware_clock_verified": False, "checks": checks,
              "synthetic_reference": manifest, "rtl_sha256": hashes}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: H768 synthetic and existing L12 RTL regressions; 16 cases, 15,768 words")


if __name__ == "__main__":
    main()
