"""Collect KR260 Linux setup information without opening /dev/mem or changing the board.

Run on the KR260: python3 scripts/v2/kr260/doctor.py
"""
from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path


def read(path: str):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def report() -> dict:
    dt = Path("/sys/firmware/devicetree/base")
    reserved = []
    root = dt / "reserved-memory"
    if root.is_dir():
        for node in sorted(root.iterdir()):
            if node.is_dir():
                reg = node / "reg"
                reserved.append({"node": node.name,
                                 "reg_hex": reg.read_bytes().hex() if reg.exists() else None,
                                 "no_map": (node / "no-map").exists()})
    model = dt / "model"
    return {"machine": platform.machine(), "kernel": platform.release(),
            "os_release": read("/etc/os-release"),
            "model": model.read_bytes().decode(errors="replace").rstrip("\0") if model.exists() else None,
            "tools": {name: shutil.which(name) for name in ("python3", "xmutil", "fpgautil", "dtc", "bootgen")},
            "dev_mem_exists": Path("/dev/mem").exists(),
            "fpga_manager_state": read("/sys/class/fpga_manager/fpga0/state"),
            "reserved_memory": reserved,
            "iomem": read("/proc/iomem"),
            "note": "No encoder registers probed. A reserved region must be confirmed before using /dev/mem."}


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
