"""Record focused synthesis counts; these are not full-design closure gates."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    candidate = sys.argv[1] if len(sys.argv) > 1 else "dot6"
    if candidate not in ("dot6", "dot7"):
        raise ValueError("Unknown focused candidate")
    groups = {}
    for scope in ("arithmetic", "attention"):
        directory = ROOT / f"build/v2/{candidate}-{scope}-ooc"
        rows = json.loads((directory / "result.json").read_text())
        for row in rows:
            name = row["case"]
            raw_report = (directory / f"{name}-utilization.rpt").read_bytes()
            report = raw_report.decode()
            for label, key in (("CLB LUTs*", "clb_luts"), ("LUT as Memory", "memory_luts"),
                               ("CLB Registers", "registers"), ("CARRY8", "carry8"),
                               ("DSPs", "dsp_tiles")):
                match = re.search(r"\|\s*" + re.escape(label) + r"\s*\|\s*(\d+)", report)
                row[key] = int(match[1]) if match else 0
            timing = (directory / f"{name}-timing.rpt").read_text()
            row["estimated_setup_ns"] = float(re.search(r"Setup\s*:.*Worst Slack\s+([-\d.]+)ns", timing)[1])
            row["utilization_sha256"] = hashlib.sha256(raw_report).hexdigest()
            # get_cells DSP* includes internal DSP subcells on this Vivado
            # release; utilization reports count actual occupied DSP tiles.
            row["dsp_cells_including_internal"] = row.pop("dsp")
        groups[scope] = rows
    old, new = groups["attention"]
    if candidate == "dot6" and new["distributed_ram_primitives"] <= old["distributed_ram_primitives"]:
        raise ValueError("No additional RAM inference; review the experiment")
    result = {"groups": groups, "full_design_qualified": False,
              "attention_test_lanes": 4,
              "attention_clb_lut_change": new["clb_luts"] - old["clb_luts"],
              "attention_register_change": new["registers"] - old["registers"],
              "source_sha256": {}}
    for directory in (ROOT / f"build/v2/{candidate}-arithmetic-ooc/rtl-snapshot", ROOT / f"build/v2/{candidate}-attention-ooc/rtl-snapshot"):
        for source in directory.glob("*.sv"):
            result["source_sha256"][str(source.relative_to(ROOT))] = hashlib.sha256(source.read_bytes()).hexdigest()
    output = ROOT / f"build/v2/{candidate}-ooc-summary.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("groups", "source_sha256")}, indent=2))


if __name__ == "__main__":
    main()
