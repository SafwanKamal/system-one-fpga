"""Launch one detached Vitis HLS synthesis each for v9i and v9k."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from make_v9k import ROOT, audited_sources, generate

VITIS = Path("C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat")
RUNS = ROOT / "build/v2/v9k/csynth"
DESIGNS = ("v9i", "v9k")
RESOURCES = ("LUT", "FF", "DSP", "BRAM_18K", "URAM")
TCL = """set work [file dirname [file normalize [info script]]]
open_project "$work/hls"
set_top qwen_decoder
add_files "$work/src/qwen_decoder.cpp" -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
csynth_design
exit
"""


def inspect_reports(work):
    reports = work / "hls/solution/syn/report"
    area = {}
    for module in ("qwen_decoder", "attention", "matvec"):
        report = ElementTree.parse(reports / f"{module}_csynth.xml")
        resources = report.find("./AreaEstimates/Resources")
        area[module] = {name: int(resources.findtext(name)) for name in RESOURCES}
    loops = {}
    for path in sorted(reports.glob("*_csynth.xml")):
        tree = ElementTree.parse(path)
        schedule = {
            loop.tag: int(loop.findtext("PipelineII"))
            for loop in tree.findall("./PerformanceEstimates/SummaryOfLoopLatency/*")
            if loop.findtext("PipelineII") is not None
        }
        if schedule:
            loops[path.name.removesuffix("_csynth.xml")] = schedule
    if not loops:
        raise ValueError(f"No pipelined loop schedules in {reports}")
    return {"area": area, "loop_ii": loops}


def synthesize(work, vitis):
    started = time.monotonic()
    with (work / "console.log").open("wb") as log:
        process = subprocess.run(
            [str(vitis), "--mode", "hls", "--tcl", (work / "run.tcl").as_posix()],
            cwd=work, stdout=log, stderr=subprocess.STDOUT,
        )
    result = {
        "exit_code": process.returncode,
        "seconds": round(time.monotonic() - started, 2),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((work / "src").iterdir())
        },
    }
    if process.returncode == 0:
        result.update(inspect_reports(work))
    return result


def worker(run, vitis, drive, designs):
    alias = Path(f"{drive}/")
    if alias.exists():
        raise ValueError(f"Vitis needs an unused drive letter, but {drive} is in use")
    subprocess.run(["subst", drive, str(run)], check=True)
    try:
        with ThreadPoolExecutor(max_workers=len(designs)) as executor:
            tasks = {name: executor.submit(synthesize, alias / name, vitis) for name in designs}
            results = {}
            for name, task in tasks.items():
                try:
                    results[name] = task.result()
                except Exception as error:
                    results[name] = {"error": str(error)}
        temporary = run / "results.tmp"
        temporary.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        temporary.replace(run / "results.json")
        return int(any(result.get("exit_code") != 0 for result in results.values()))
    finally:
        subprocess.run(["subst", drive, "/d"], check=True)


def launch(source_root, vitis, drive, designs):
    if not vitis.is_file():
        raise FileNotFoundError(vitis)
    run = RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for name in designs:
        if name == "v9i":
            sources = audited_sources(source_root)
        else:
            sources = {path.name: path.read_bytes() for path in generate(source_root).iterdir()}
        work = run / name
        (work / "src").mkdir(parents=True)
        for filename, payload in sources.items():
            (work / "src" / filename).write_bytes(payload)
        (work / "run.tcl").write_text(TCL, encoding="utf-8")
    with (run / "driver.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(run),
             "--vitis", str(vitis), "--drive", drive, "--design", *designs],
            cwd=run, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    print(f"Detached PID {process.pid}\n{run}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", nargs="?", type=Path)
    parser.add_argument("--vitis", type=Path, default=VITIS)
    parser.add_argument("--drive", choices=[f"{letter}:" for letter in "STUVWXYZ"], default="Y:")
    parser.add_argument("--design", nargs="+", choices=DESIGNS, help="select designs to run or inspect")
    parser.add_argument("--inspect", type=Path, metavar="RUN", help="print paired results as JSON")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    designs = tuple(dict.fromkeys(args.design or DESIGNS))
    if args.worker:
        sys.exit(worker(args.worker, args.vitis, args.drive, designs))
    if args.inspect:
        results = json.loads((args.inspect / "results.json").read_text(encoding="utf-8"))
        if args.design:
            results = {name: results[name] for name in designs}
        print(json.dumps(results, indent=2))
        sys.exit(int(any(result.get("exit_code") != 0 for result in results.values())))
    if args.source_root is None:
        parser.error("source_root is required")
    launch(args.source_root.resolve(), args.vitis.resolve(), args.drive, designs)
