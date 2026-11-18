"""Qualify the isolated memory-layout candidate, preserving baseline evidence."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/v2/rtl-memory-check"


def main():
    checks = {}
    previous = json.loads((ROOT / "build/v2/rtl-wide-check/summary.json").read_text())
    for name, old_name, words in (
        ("kr260-memory-wide.log", "kr260-wide.log", 10512),
        ("kr260-memory-l12.log", "kr260-wide-l12.log", 5256),
    ):
        raw = (OUT / name).read_bytes()
        log = raw.decode()
        rows = re.findall(r"case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)", log)
        if [int(r[1]) for r in rows] != [1, 2, 3, 4, 5, 12, 64, 128]:
            raise ValueError(f"Missing request lengths: {name}")
        if any(int(r[2]) or int(r[4]) or not 0 < int(r[5]) <= int(r[6]) for r in rows):
            raise ValueError(f"Invalid results: {name}")
        if f"PASS: KR260 block bit-exact, 8 cases, {words} words compared" not in log:
            raise ValueError(f"Incomplete comparison: {name}")
        if "BUILD register 20803004" not in log:
            raise ValueError("Missing wide configuration")
        cycles = [int(r[5]) for r in rows]
        old_cycles = previous["checks"][old_name]["encoder_clocks"]
        checks[name] = {"cases": 8, "words": words, "sha256": hashlib.sha256(raw).hexdigest(),
                        "encoder_clocks": cycles, "request_clocks": [int(r[6]) for r in rows],
                        "baseline_encoder_clocks": old_cycles,
                        "cycle_change_percent": [100 * (n / o - 1) for n, o in zip(cycles, old_cycles)]}
    for name, marker in (
        ("activation-memory.log", "PASS: activation memories, two depths, 60000 masked-write/read checks"),
        ("nexys-default.log", "PASS: encoder layer bit-exact, 2 cases, 39216 words compared"),
    ):
        raw = (OUT / name).read_bytes()
        if marker not in raw.decode():
            raise ValueError(f"Incomplete comparison: {name}")
        checks[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "passed": True}
    digests = {}
    for line in (OUT / "source-sha256.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        digests[name.strip()] = digest
    hashes = {name: digests[name] for name in previous["rtl_sha256"]}
    if not all((hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest)
               for name, digest in hashes.items()):
        raise ValueError("Current RTL differs from the tested snapshot")
    profile = {"max_hidden": 768, "mac_input_registers": 1, "exp_table_in_bram": 1,
               "pipelined_uram": 1, "activation_read_latency": 4}
    result = {"profile": profile, "hardware_clock_verified": False,
              "checks": checks, "rtl_sha256": hashes,
              "synthetic_reference": previous["synthetic_reference"]}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: pipelined UltraRAM wide/L12/default regressions and masked-write memory checks")


if __name__ == "__main__":
    main()
