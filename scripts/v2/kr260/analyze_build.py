"""Compare measured implementation cost and routing warnings, including partial runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

STAGES = ("link_design", "opt_design", "place_design", "phys_opt_design", "route_design", "write_bitstream")


def seconds(value: str) -> int:
    h, m, s = map(int, value.split(":"))
    return h * 3600 + m * 60 + s


def analyze(build: Path) -> dict:
    run = build / "sysone_v2_kr260.runs/impl_1/runme.log"
    log = run.read_text(errors="replace") if run.exists() else ""
    stages = {}
    pattern = r"^(\w+): Time \(s\): cpu = (\d+:\d+:\d+) ; elapsed = (\d+:\d+:\d+)"
    for name, cpu, elapsed in re.findall(pattern, log, re.M):
        if name in STAGES:
            stages[name] = {"wall_seconds": seconds(elapsed), "cpu_seconds": seconds(cpu)}
    total = sum(s["wall_seconds"] for s in stages.values())
    outcomes = {name: "failed" if re.search(r"^"+name+r" failed\b",log,re.M)
                else "completed" if re.search(r"^"+name+r" completed successfully\b",log,re.M)
                else "unknown" for name in stages}
    levels = [int(x) for x in re.findall(r"congestion is level (\d+)", log, re.I)]
    overlaps = [int(x) for x in re.findall(r"Number of Nodes with overlaps = (\d+)", log)]
    peaks = [float(x) for x in re.findall(r"Memory \(MB\): peak = ([\d.]+)", log)]
    timing_path = build / "timing.rpt"
    timing = timing_path.read_text(errors="replace") if timing_path.exists() else ""
    # Bound parsing to the first timing path. Avoid a cross-report wildcard
    # expression: small whitespace differences can cause excessive backtracking.
    block = timing.split("Slack (", 1)[1].split("Slack (", 1)[0] if "Slack (" in timing else ""
    slack = re.search(r"(?:VIOLATED|MET)\)\s*:\s*([-\d.]+)ns", block)
    source = re.search(r"Source:[ \t]*(\S+)", block)
    destination = re.search(r"Destination:[ \t]*(\S+)", block)
    delay = re.search(r"Data Path Delay:[ \t]*([\d.]+)ns\s+\(logic ([\d.]+)ns\s+\(([\d.]+)%\)\s+route ([\d.]+)ns\s+\(([\d.]+)%\)\)", block)
    critical = None if not all((slack, source, destination, delay)) else dict(zip(
        ("slack_ns", "source", "destination", "data_delay_ns", "logic_delay_ns", "logic_percent", "route_delay_ns", "route_percent"),
        (float(slack[1]), source[1], destination[1], *(float(delay[i]) for i in range(1, 6)))))
    resources = {}
    resource_path = build / "utilization.rpt"
    if resource_path.exists():
        report = resource_path.read_text()
        for name in ("CLB LUTs", "CLB Registers", "Block RAM Tile", "URAM", "DSPs"):
            row = re.search(r"\|\s*" + re.escape(name) + r"\*?\s*\|\s*([\d,.]+)\s*\|", report)
            if row:
                resources[name] = float(row[1].replace(",", ""))
    clocks_path = build / "clock-candidates.json"
    clocks = json.loads(clocks_path.read_text()) if clocks_path.exists() else None
    result = {
        "candidate": build.name, "stages": stages,
        "stage_outcomes": outcomes,
        "implementation_failed": "failed" in outcomes.values(),
        "reported_stage_seconds": total,
        "route_share_of_reported_stages": stages.get("route_design", {}).get("wall_seconds", 0) / total if total else None,
        "max_congestion_level": max(levels) if levels else None,
        "router_connectivity_priority_warning": "prioritize the successful completion of routing all nets over timing optimizations" in log,
        "peak_overlapping_nodes": max(overlaps) if overlaps else None,
        "peak_vivado_memory_mb": max(peaks) if peaks else None,
        "critical_setup_path": critical, "resources": resources,
        "clock_candidates": clocks,
        "bitstream_completed": "Bitgen Completed Successfully" in log,
        "note": "Stage sum excludes reporting/startup overhead. Missing stages remain unknown; bitstream completion does not establish timing success.",
    }
    (build / "build-diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", nargs="+", type=Path)
    args = parser.parse_args()
    for build in args.build:
        if not build.is_dir():
            parser.error(f"Build directory missing: {build}")
        result = analyze(build)
        stage = result["stages"]
        route = stage.get("route_design", {}).get("wall_seconds")
        place = stage.get("place_design", {}).get("wall_seconds")
        print(f"{build.name}: placement={place}s routing={route}s congestion={result['max_congestion_level']} failed={result['implementation_failed']} bitstream={result['bitstream_completed']}")


if __name__ == "__main__":
    main()
