"""Stage a paired D3/V9J Vitis HLS run and launch it in the background."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from make_v9j import OUTPUT, ROOT, STUDY

VITIS = Path("C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat")
RUNS = ROOT / "build/v2/v9j/csynth"
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


def inspect_attention(work):
    synth = work / "hls/solution/syn"
    loops = {}
    for report in sorted((synth / "report").glob("attention*_csynth.xml")):
        tree = ElementTree.parse(report)
        for loop in tree.findall("./PerformanceEstimates/SummaryOfLoopLatency/*"):
            ii = loop.findtext("PipelineII")
            if ii is not None:
                loops[loop.tag] = int(ii)
    rtl = sorted((synth / "verilog").glob("qwen_decoder_attention*.v"))
    if not loops or not rtl:
        raise ValueError(f"Incomplete attention XML or Verilog in {synth}")
    fmul = re.compile(r"^\s*qwen_decoder_fmul_\w+\s+#\(", re.MULTILINE)
    return {
        "fmul_instances": sum(len(fmul.findall(path.read_text(encoding="utf-8"))) for path in rtl),
        "loop_ii": loops,
    }


def synthesize(run, vitis):
    results = {}
    resources = ("LUT", "FF", "DSP", "BRAM_18K")
    for name in ("d3", "v9j"):
        work = run / name
        started = time.monotonic()
        with (work / "console.log").open("wb") as log:
            process = subprocess.run(
                [str(vitis), "--mode", "hls", "--tcl", (work / "run.tcl").as_posix()],
                cwd=work, stdout=log, stderr=subprocess.STDOUT,
            )
        result = dict(exit_code=process.returncode, seconds=round(time.monotonic() - started, 2))
        result["source_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((work / "src").iterdir()) if path.is_file()
        }
        if process.returncode == 0:
            reports = work / "hls/solution/syn/report"
            for module in ("qwen_decoder", "attention", "matvec"):
                report = ElementTree.parse(reports / f"{module}_csynth.xml")
                area = report.find("./AreaEstimates/Resources")
                result[module] = {resource: int(area.findtext(resource)) for resource in resources}
        results[name] = result
        temporary = run / "results.tmp"
        temporary.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        temporary.replace(run / "results.json")
    return int(any(result["exit_code"] for result in results.values()))


def worker(run, vitis, drive):
    alias = Path(f"{drive}/")
    if alias.exists():
        raise ValueError(f"Vitis needs an unused drive letter, but {drive} is in use")
    subprocess.run(["subst", drive, str(run)], check=True)
    try:
        return synthesize(alias, vitis)
    finally:
        subprocess.run(["subst", drive, "/d"], check=True)


def launch(study_root, vitis, drive):
    if not vitis.is_file():
        raise FileNotFoundError(vitis)
    run = RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for name, source in (("d3", study_root / STUDY / "src-d3"), ("v9j", OUTPUT)):
        work = run / name
        shutil.copytree(source, work / "src")
        (work / "run.tcl").write_text(TCL, encoding="utf-8")
    with (run / "driver.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(run),
             "--vitis", str(vitis), "--drive", drive],
            cwd=run, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    print(f"Detached PID {process.pid}")
    print(run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_root", nargs="?", type=Path)
    parser.add_argument("--inspect", type=Path, metavar="RUN", help="read results, attention II and RTL fmul counts")
    parser.add_argument("--vitis", type=Path, default=VITIS)
    parser.add_argument("--drive", choices=[f"{letter}:" for letter in "STUVWXYZ"], default="X:")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        sys.exit(worker(args.worker.resolve(), args.vitis.resolve(), args.drive))
    if args.inspect:
        results = json.loads((args.inspect / "results.json").read_text(encoding="utf-8"))
        for name, result in results.items():
            if result["exit_code"] == 0:
                result.update(inspect_attention(args.inspect / name))
        print(json.dumps(results, indent=2))
        sys.exit(int(any(results.get(name, {}).get("exit_code") != 0 for name in ("d3", "v9j"))))
    if args.study_root is None:
        parser.error("study_root is required")
    launch(args.study_root.resolve(), args.vitis.resolve(), args.drive)
