"""Preserve the encoder reservation in Ubuntu's per-kernel KR260 revB DTB.

Called before flash-kernel by kernel/initramfs hooks. Every original is backed
up by kernel version and SHA256; an already correct reservation is a no-op.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import struct
import tempfile
from pathlib import Path

try:
    from .prepare_reserved_fit import child, pack, parse, RESERVATION
except ImportError:
    from prepare_reserved_fit import child, pack, parse, RESERVATION

DTB_NAME = "zynqmp-smk-k26-revA-sck-kr-g-revB.dtb"
EXPECTED = {"reg": struct.pack(">4I", 0, 0x60000000, 0, 0x04000000), "no-map": b""}


def patch(blob: bytes, base: int = 0x60000000, size: int = 64 << 20) -> bytes:
    if base < 0 or base % 4096 or size <= 0 or size % 4096 or base + size > 0x80000000:
        raise ValueError("allocation must be page-aligned and fit mapped low DDR")
    name = f"sysone@{base:x}"
    expected = {"reg": struct.pack(">QQ", base, size), "no-map": b""}
    tree, reserve, metadata = parse(blob)
    if tree["props"].get("model", b"").rstrip(b"\0") != b"ZynqMP KR260 revB":
        raise ValueError("not the KR260 revB device tree")
    parent = child(tree, "reserved-memory")
    for prop in ("#address-cells", "#size-cells"):
        if parent["props"].get(prop) != struct.pack(">I", 2):
            raise ValueError("expected two address and size cells")
    found = [n for n in parent["children"] if n["name"].startswith("sysone@")]
    if found:
        props = found[0]["props"]
        if (len(found) != 1 or set(props) != {"reg", "no-map"} or props["no-map"] != b""
                or len(props["reg"]) != 16 or found[0]["children"]):
            raise ValueError("existing encoder reservation differs")
        old_base, old_size = struct.unpack(">QQ", props["reg"])
        if old_size <= 0 or found[0]["name"] != f"sysone@{old_base:x}":
            raise ValueError("existing encoder reservation differs")
        parent["children"].remove(found[0])
    for n in parent["children"]:
        reg = n["props"].get("reg", b"")
        if len(reg) % 16:
            raise ValueError("unsupported reserved-memory reg encoding")
        for off in range(0, len(reg), 16):
            other_base, other_size = struct.unpack_from(">QQ", reg, off)
            if other_base < base + size and other_base + other_size > base:
                raise ValueError("encoder allocation overlaps another reservation")
    for off in range(0, len(reserve) - 16, 16):
        other_base, other_size = struct.unpack_from(">QQ", reserve, off)
        if other_base < base + size and other_base + other_size > base:
            raise ValueError("encoder allocation overlaps the FDT reservation map")
    memory_nodes = [n for n in tree["children"] if n["props"].get("device_type") == b"memory\0"]
    if memory_nodes:
        ranges = []
        for n in memory_nodes:
            reg = n["props"].get("reg", b"")
            if len(reg) % 16: raise ValueError("unsupported memory reg encoding")
            ranges.extend(struct.unpack_from(">QQ", reg, off) for off in range(0, len(reg), 16))
        if not any(start <= base and base + size <= start + length for start, length in ranges):
            raise ValueError("allocation is outside physical RAM")
    if found and found[0]["name"] == name and found[0]["props"] == expected:
        return blob
    unchanged = copy.deepcopy(tree)
    parent["children"].append({"name": name, "props": expected, "children": []})
    result = pack(tree, reserve, metadata)
    check, r, m = parse(result)
    region = child(child(check, "reserved-memory"), name)
    child(check, "reserved-memory")["children"].remove(region)
    if check != unchanged or r != reserve or m != metadata:
        raise ValueError("DTB verification failed")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--config", type=Path, default=Path("/etc/sysone/kr260-memory.json"))
    ap.add_argument("--base", type=lambda s: int(s, 0))
    ap.add_argument("--bytes", type=lambda s: int(s, 0))
    ap.add_argument("--check-only", action="store_true", help="validate without changing the kernel DTB")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", args.version):
        ap.error("invalid kernel version")
    model = Path("/sys/firmware/devicetree/base/model").read_bytes().rstrip(b"\0")
    if model != b"ZynqMP KR260 revB":
        raise RuntimeError("this hook is configured for KR260 revB only")
    path = Path("/lib/firmware") / args.version / "device-tree/xilinx" / DTB_NAME
    if not path.is_file():
        raise FileNotFoundError(f"kernel DTB missing: {path}; refusing an unreserved FIT rebuild")
    old = path.read_bytes()
    config = json.loads(args.config.read_text()) if args.config.exists() else {}
    base = args.base if args.base is not None else config.get("base", 0x60000000)
    size = args.bytes if args.bytes is not None else config.get("bytes", 64 << 20)
    if isinstance(base, str): base = int(base, 0)
    if isinstance(size, str): size = int(size, 0)
    new = patch(old, base, size)
    if args.check_only:
        print(f"sysone: validated {size} bytes at {base:#x}; kernel DTB unchanged")
        return
    if old == new:
        print(f"sysone: {args.version} reservation already correct")
        return
    backups = Path("/var/lib/sysone/dtb-backups") / args.version
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / (hashlib.sha256(old).hexdigest() + ".dtb")
    if backup.exists():
        if backup.read_bytes() != old:
            raise RuntimeError("backup verification failed")
    else:
        with backup.open("xb") as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=".sysone-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        if path.read_bytes() != old:
            raise RuntimeError("DTB changed during patching")
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print(f"sysone: patched {path}; original saved to {backup}")


if __name__ == "__main__":
    main()
