"""Run the v9h/v9i decode audit or a standalone v9i Vitis HLS synthesis."""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from ctypes import wintypes
from xml.etree import ElementTree


BASELINE = Path("build/v2/dual-port-study/src-s2")
VARIANT = Path("build/v2/v9i/src")
OUTPUT = Path("build/v2/v9i/csim")
FIXTURES = (
    Path("models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf"),
    Path("build/v2/schedule-invariance-audit/meta.bin"),
    Path("build/v2/qwen-fpga-decoder-v9e/rope.bin"),
)
RESOURCES = ("LUT", "FF", "DSP", "BRAM_18K")
TIME_LIMIT = 90 * 60


def stage_harness(source, scratch):
    destination = scratch / "experiments/attn_reclaim/audit"
    destination.mkdir(parents=True)
    for name in ("audit.py", "testbench.cpp"):
        shutil.copyfile(source / name, destination / name)
    spec = importlib.util.spec_from_file_location("gemini_audit", destination / "audit.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    return audit


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def stop_tree(pid):
    """Terminate an owned Windows process tree without the taskkill/WMI service."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("usage", wintypes.DWORD),
            ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
            ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
            ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
            ("flags", wintypes.DWORD), ("image", wintypes.WCHAR * 260),
        ]

    win = ctypes.WinDLL("kernel32", use_last_error=True)
    win.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    win.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for function in (win.Process32FirstW, win.Process32NextW):
        function.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
        function.restype = wintypes.BOOL
    win.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    win.OpenProcess.restype = wintypes.HANDLE
    win.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    win.TerminateProcess.restype = wintypes.BOOL
    win.CloseHandle.argtypes = (wintypes.HANDLE,)
    win.CloseHandle.restype = wintypes.BOOL
    win.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    win.WaitForSingleObject.restype = wintypes.DWORD

    snapshot = win.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    children = {}
    entry = ProcessEntry(size=ctypes.sizeof(ProcessEntry))
    try:
        found = win.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            children.setdefault(entry.parent, []).append(entry.pid)
            found = win.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        win.CloseHandle(snapshot)

    handles = {}
    pending = [pid]
    try:
        for member in pending:
            pending.extend(children.get(member, ()))
            handle = win.OpenProcess(0x100001, False, member)  # SYNCHRONIZE | PROCESS_TERMINATE
            if handle:
                handles[member] = handle
            elif ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER, already exited
                raise ctypes.WinError(ctypes.get_last_error())
        for member, handle in handles.items():
            if not win.TerminateProcess(handle, 1) and win.WaitForSingleObject(handle, 0) != 0:
                raise OSError(f"Could not terminate PID {member}")
        for member, handle in handles.items():
            if win.WaitForSingleObject(handle, 5000) != 0:
                raise OSError(f"Timed out waiting for PID {member} to exit")
    finally:
        for handle in handles.values():
            win.CloseHandle(handle)
    return list(handles)


def launch(audit, drive, relative_dir, tcl, timeout=None):
    run_dir = Path(f"{drive}:/{relative_dir.as_posix()}")
    (run_dir / "run.tcl").write_text(tcl, encoding="utf-8")
    log = run_dir / "console.log"
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        cmd = [str(audit.VITIS_RUN), "--mode", "hls", "--tcl", str(run_dir / "run.tcl")]
        process = subprocess.Popen(cmd, cwd=run_dir, stdout=stream, stderr=subprocess.STDOUT)
        print(f"{relative_dir}: PID {process.pid}, log {log}", flush=True)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stopped = stop_tree(process.pid)
            stream.write(f"Wall limit reached. Stopped simulation PIDs {stopped}.\n")
            process.wait(timeout=15)
    return {
        "wall_seconds": round(time.monotonic() - start, 3),
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "log": (relative_dir / "console.log").as_posix(),
    }


def decode(audit, source, scratch, drive, verdict):
    for relative in FIXTURES:
        target = scratch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    verdict["fixture_sha256"] = {
        path.as_posix(): sha256(scratch / path) for path in FIXTURES
    }
    verdict.update(mode="decode", tile_cross=False, layers=audit.NL, fields=None,
                   timeout_seconds_per_run=TIME_LIMIT)
    tb = audit.TESTBENCH_PATH.read_text(encoding="utf-8")
    if "qwen_decoder(model, model, scratch," not in tb:
        raise ValueError("The dual-port testbench must pass model to both ports")

    runs = []
    for name, relative_src in (("v9h", BASELINE), ("v9i", VARIANT)):
        relative_dir = OUTPUT / f"decode-{name}"
        run_dir = scratch / relative_dir
        staged_src = run_dir / "src"
        shutil.copytree(source / relative_src, staged_src)
        (run_dir / "tb").mkdir()
        shutil.copyfile(audit.TESTBENCH_PATH, run_dir / "tb/testbench.cpp")
        if audit.is_single_port(staged_src):
            raise ValueError(f"Expected the dual-port ABI for {name}")
        tcl = audit.render_tcl(
            f"{drive}:/{relative_dir.as_posix()}", "decode", False, False, drive=drive,
        )
        run = {"source": relative_src.as_posix(), "source_sha256": audit.compute_source_hash(staged_src)}
        verdict[name] = run
        run.update(launch(audit, drive, relative_dir, tcl, TIME_LIMIT))
        sim_log = run_dir / "csim/solution/csim/build/temp0.log"
        logs = (run_dir / "console.log", sim_log)
        run["completed_positions"] = sorted({
            int(match)
            for log in logs if log.is_file()
            for match in re.findall(r"decode group start=(\d+) size=1 keep=1", log.read_text(errors="replace"))
        })
        if run["timed_out"]:
            verdict["verdict"] = "TIMEOUT"
            return
        if run["exit_code"]:
            raise RuntimeError(f"{name} Vitis C-sim exited {run['exit_code']}")
        results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
        if (results["mode"] != "decode" or results["tile_boundary_crossed"]
                or results["positions"] != list(range(24))):
            raise ValueError(f"Unexpected {name} decode mode or coverage")
        run.update(testbench_seconds=results["elapsed_seconds"], kv_nan_values=results["kv_nan_values"])
        runs.append(run_dir / "dump.bin")

    positions = list(range(24))
    fields, total, first = audit.compare_dumps(*runs, positions)
    expected = (audit.NL * 24 * audit.H, audit.NL * 2 * audit.NK * 24 * audit.KV_WORDS_PER_ROW,
                24 * audit.H, 24, 24)
    if [fields[field]["words"] for field in audit.FIELDS] != list(expected):
        raise ValueError("Unexpected dump field sizes")
    verdict.update(
        verdict="PASS" if total == 0 and all(verdict[name]["kv_nan_values"] == 0
                                           for name in ("v9h", "v9i")) else "FAIL",
        positions=positions, fields=fields, total_differing_words=total, first_mismatch=first,
    )


def synthesize(audit, source, scratch, drive, verdict):
    relative_dir = OUTPUT / "csynth"
    run_dir = scratch / relative_dir
    staged_src = run_dir / "src"
    shutil.copytree(source / VARIANT, staged_src)
    run_path = f"{drive}:/{relative_dir.as_posix()}"
    tcl = f"""open_project {run_path}/hls
set_top qwen_decoder
add_files {run_path}/src/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {{xck26-sfvc784-2LV-c}}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
csynth_design
exit
"""
    verdict.update(source=VARIANT.as_posix(), source_sha256=audit.compute_source_hash(staged_src),
                   top="qwen_decoder", part="xck26-sfvc784-2LV-c", clock_ns=8, pipeline_loops=0)
    verdict.update(launch(audit, drive, relative_dir, tcl))
    if verdict["exit_code"]:
        raise RuntimeError(f"Vitis csynth exited {verdict['exit_code']}")
    report_dir = run_dir / "hls/solution/syn/report"
    verdict.update(verdict="PASS", resources=read_synth_resources(report_dir))


def read_synth_resources(report_dir):
    resources = {}
    for label, module in (("total", "qwen_decoder"), ("attention", "attention"), ("matvec", "matvec")):
        report = ElementTree.parse(report_dir / f"{module}_csynth.xml")
        area = report.find("./AreaEstimates/Resources")
        resources[label] = {name: int(area.findtext(name)) for name in RESOURCES}
    return resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("decode", "csynth"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--drive", required=True, help="An unused subst drive letter")
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(prefix="v9i-")).resolve()
    out = scratch / OUTPUT
    out.mkdir(parents=True)
    print(f"Scratch checkout: {scratch}", flush=True)
    verdict = {"verdict": "ERROR", "scratch": str(scratch)}
    start = time.monotonic()
    drive = None
    try:
        audit = stage_harness(args.harness, scratch)
        verdict["harness_sha256"] = sha256(Path(audit.__file__))
        verdict["testbench_sha256"] = sha256(audit.TESTBENCH_PATH)
        audit.self_test()
        letter = audit.normalize_drive(args.drive)
        if Path(f"{letter}:/").exists():
            raise ValueError(f"Drive {letter}: is already in use")
        drive = audit.ensure_subst(scratch, letter)
        work = decode if args.step == "decode" else synthesize
        work(audit, args.source.resolve(), scratch, drive, verdict)
    except Exception as exc:
        verdict["error"] = str(exc)
        raise
    finally:
        verdict["driver_wall_seconds"] = round(time.monotonic() - start, 3)
        write_json(out / f"{args.step}-verdict.json", verdict)
        if drive is not None:
            subprocess.run(["subst", f"{drive}:", "/D"], check=True)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
