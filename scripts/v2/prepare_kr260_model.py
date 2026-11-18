"""Prepare and verify both board images after a completed training run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if Path(args.name).name != args.name or args.name in (".", ".."):
        ap.error("name must be a model directory name")
    suite = ROOT / "build/v2/eval" / f"{args.name}-matched.json"
    commands = [
        ("Compile baseline with fresh calibration", "compile_image.py", "build", "--name", args.name),
        ("Compile KR260 with the same calibration", "compile_image.py", "build", "--name", args.name,
         "--board", "kr260", "--base", "0x60000000", "--suffix=-kr260", "--reuse-calibration"),
        ("Check image against IntEncoder", "compile_image.py", "check", "--name", args.name, "--chains", "50"),
        ("Calibrate OOS/HWU routing rules", "oos_threshold.py", "--name", args.name, "--extra", "hwu"),
        ("Freeze matched board goldens", "prepare_eval_suite.py", "--image", args.name,
         "--peer-image", args.name + "-kr260", "--per-dataset", "50", "--seed", "0", "--out", str(suite)),
        ("Package checked KR260 image and runtime", "package_eval.py", "--image", args.name + "-kr260",
         "--suite", str(suite), "--include-model", "--out", str(ROOT / "build/v2" / f"kr260-{args.name}.tar.gz")),
    ]
    if not args.dry_run:
        result = json.loads((ROOT / "results/v2/chain" / f"{args.name}.json").read_text())
        if result["name"] != args.name or "test_int8" not in result or not result["history"]:
            raise ValueError("Training has not completed validation/export")
        if len(result["history"]) != result["args"]["epochs"]:
            raise ValueError("Training epoch history is incomplete")
    for index, (description, script, *argv) in enumerate(commands, 1):
        cmd = [sys.executable, "-u", str(ROOT / "scripts/v2" / script), *argv]
        print(f"[{index}/{len(commands)}] {description}: {subprocess.list2cmdline(cmd)}", flush=True)
        if args.dry_run:
            continue
        subprocess.run(cmd, cwd=ROOT, check=True)
        if script == "oos_threshold.py":
            folder = ROOT / "export/v2/image"
            shutil.copy2(folder / args.name / "decision.json", folder / (args.name + "-kr260") / "decision.json")
    print("Preparation plan complete" if args.dry_run else "Verified transfer bundle ready; FPGA execution is still required", flush=True)


if __name__ == "__main__":
    main()
