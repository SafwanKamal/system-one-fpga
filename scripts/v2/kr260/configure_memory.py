"""Persist a validated KR260 low-DDR budget; does not rebuild FIT or reboot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

try:
    from .patch_kernel_dtb import DTB_NAME, patch
except ImportError:
    from patch_kernel_dtb import DTB_NAME, patch


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x60000000)
    ap.add_argument("--bytes", type=lambda s: int(s, 0), required=True)
    args = ap.parse_args()
    if os.geteuid() != 0:
        ap.error("run with sudo on the KR260")
    if Path("/sys/firmware/devicetree/base/model").read_bytes().rstrip(b"\0") != b"ZynqMP KR260 revB":
        ap.error("requires KR260 revB")
    version = os.uname().release
    dtb = Path("/lib/firmware") / version / "device-tree/xilinx" / DTB_NAME
    patch(dtb.read_bytes(), args.base, args.bytes)
    path = Path("/etc/sysone/kr260-memory.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(".json.previous")
        backup.write_bytes(path.read_bytes())
    fd, temp = tempfile.mkstemp(prefix=".kr260-memory-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump({"base": args.base, "bytes": args.bytes}, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print(f"Configured {args.bytes / (1 << 20):g} MiB at {args.base:#x}; boot FIT and live reservation unchanged")


if __name__ == "__main__":
    main()
