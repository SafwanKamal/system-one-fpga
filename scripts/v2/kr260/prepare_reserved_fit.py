"""Prepare a separate, verified FIT with the KR260 revB encoder reservation.

Never installs a boot file. No third-party Python dependencies. Rejects signed
FITs, external payloads, and any DTB change beyond the expected reservation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

MAGIC = 0xD00DFEED
TARGET = "fdt-smk-k26-revA-sck-kr-g-revB.dtb"
RESERVATION = "sysone@60000000"


def parse(blob: bytes):
    if len(blob) < 40:
        raise ValueError("truncated FDT")
    h = struct.unpack_from(">10I", blob)
    magic, total, off_tree, off_strings, off_reserve, version, last, cpu, ns, nt = h
    if magic != MAGIC or version != 17 or total > len(blob):
        raise ValueError("expected a complete version-17 FDT")
    if off_strings + ns > total or off_tree + nt > total:
        raise ValueError("invalid FDT section bounds")
    strings = blob[off_strings:off_strings + ns]
    end_reserve = off_reserve
    while end_reserve + 16 <= total:
        entry = blob[end_reserve:end_reserve + 16]
        end_reserve += 16
        if entry == bytes(16):
            break
    else:
        raise ValueError("unterminated reservation map")
    stack, root, p = [], None, off_tree
    while p + 4 <= off_tree + nt:
        token, = struct.unpack_from(">I", blob, p)
        p += 4
        if token == 1:
            end = blob.index(0, p, off_tree + nt)
            node = {"name": blob[p:end].decode(), "props": {}, "children": []}
            p = (end + 4) & ~3
            if stack:
                stack[-1]["children"].append(node)
            elif root is None:
                root = node
            else:
                raise ValueError("multiple FDT roots")
            stack.append(node)
        elif token == 2:
            if not stack:
                raise ValueError("unbalanced FDT")
            stack.pop()
        elif token == 3:
            if not stack or p + 8 > off_tree + nt:
                raise ValueError("invalid property")
            length, offset = struct.unpack_from(">II", blob, p)
            p += 8
            if offset >= len(strings) or p + length > off_tree + nt:
                raise ValueError("invalid property bounds")
            end = strings.index(0, offset)
            name = strings[offset:end].decode()
            if name in stack[-1]["props"]:
                raise ValueError("duplicate property")
            stack[-1]["props"][name] = blob[p:p + length]
            p = (p + length + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            if stack or root is None:
                raise ValueError("unfinished FDT")
            return root, blob[off_reserve:end_reserve], (last, cpu)
        else:
            raise ValueError(f"unknown FDT token {token}")
    raise ValueError("missing FDT end token")


def pack(tree, reservations: bytes, metadata) -> bytes:
    strings, offsets, body = bytearray(), {}, bytearray()
    def emit(node):
        body.extend(struct.pack(">I", 1) + node["name"].encode() + b"\0")
        body.extend(bytes(-len(body) % 4))
        for name, value in node["props"].items():
            if name not in offsets:
                offsets[name] = len(strings)
                strings.extend(name.encode() + b"\0")
            body.extend(struct.pack(">III", 3, len(value), offsets[name]) + value)
            body.extend(bytes(-len(body) % 4))
        for child in node["children"]:
            emit(child)
        body.extend(struct.pack(">I", 2))
    emit(tree)
    body.extend(struct.pack(">I", 9))
    tree_offset = 40 + len(reservations)
    strings_offset = tree_offset + len(body)
    header = struct.pack(">10I", MAGIC, strings_offset + len(strings), tree_offset,
                         strings_offset, 40, 17, *metadata, len(strings), len(body))
    return header + reservations + body + strings


def child(node, name):
    matches = [n for n in node["children"] if n["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one node {name}")
    return matches[0]


def walk(node):
    yield node
    for n in node["children"]:
        yield from walk(n)


def verify_hashes(image):
    payload = image["props"]["data"]
    hashes = image["children"]
    if not hashes:
        raise ValueError("image has no integrity hash")
    for node in hashes:
        algo = node["props"].get("algo", b"").rstrip(b"\0").decode()
        if not node["name"].startswith("hash") or algo not in ("sha1", "sha256"):
            raise ValueError("only SHA1/SHA256 image hashes are supported")
        if node["props"].get("value") != hashlib.new(algo, payload).digest():
            raise ValueError(f"bad source hash: {image['name']}/{node['name']}")


def prepare(source: bytes, patched: bytes, base: int = 0x60000000, size: int = 64 << 20):
    if base < 0 or base % 4096 or size <= 0 or size % 4096 or base + size > 0x80000000:
        raise ValueError("allocation must fit mapped low DDR")
    reservation = f"sysone@{base:x}"
    tree, reserve, metadata = parse(source)
    for n in walk(tree):
        if n["name"].startswith("signature"):
            raise ValueError("signed FIT requires a signing workflow")
    images = child(tree, "images")["children"]
    for image in images:
        if "data" not in image["props"] or any(k.startswith("data-") for k in image["props"]):
            raise ValueError("external FIT payloads are not supported")
        verify_hashes(image)
    configs = child(tree, "configurations")
    for config in configs["children"]:
        if config["children"] and any("value" in n["props"] for n in config["children"]):
            raise ValueError("configuration digests require a separate hash workflow")
    target = child(child(tree, "images"), TARGET)
    if target["props"].get("compression") != b"none\0":
        raise ValueError("expected an uncompressed DTB")
    original, original_reserve, original_meta = parse(target["props"]["data"])
    changed, changed_reserve, changed_meta = parse(patched)
    region = child(child(changed, "reserved-memory"), reservation)
    if region["props"] != {"reg": struct.pack(">QQ", base, size), "no-map": b""} or region["children"]:
        raise ValueError("unexpected encoder reservation")
    without = copy.deepcopy(changed)
    parent = child(without, "reserved-memory")
    parent["children"].remove(child(parent, reservation))
    original_parent = child(original, "reserved-memory")
    existing = [n for n in original_parent["children"] if n["name"].startswith("sysone@")]
    if existing:
        if len(existing) != 1 or set(existing[0]["props"]) != {"reg", "no-map"} or existing[0]["children"]:
            raise ValueError("unexpected existing encoder reservation")
        original_parent["children"].remove(existing[0])
    # Independently validate all reservation overlaps, including FDT memreserve.
    try:
        from .patch_kernel_dtb import patch
    except ImportError:
        from patch_kernel_dtb import patch
    patch(target["props"]["data"], base, size)
    if without != original or original_reserve != changed_reserve or original_meta != changed_meta:
        raise ValueError("DTB contains changes beyond the encoder reservation")
    target["props"]["data"] = patched
    for node in target["children"]:
        algo = node["props"]["algo"].rstrip(b"\0").decode()
        node["props"]["value"] = hashlib.new(algo, patched).digest()
    candidate = pack(tree, reserve, metadata)
    check, check_reserve, check_meta = parse(candidate)
    if check != tree or check_reserve != reserve or check_meta != metadata:
        raise ValueError("candidate round-trip failed")
    for image in child(check, "images")["children"]:
        verify_hashes(image)
    return candidate


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=Path("/boot/firmware/image.fit"))
    ap.add_argument("--dtb", type=Path, default=Path.home() / "sysone-boot/kr260-reserved.dtb")
    ap.add_argument("--out", type=Path, default=Path.home() / "sysone-boot/image-sysone.fit")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x60000000)
    ap.add_argument("--bytes", type=lambda s: int(s, 0), default=64 << 20)
    ap.add_argument("--auto-patch", action="store_true", help="derive the changed DTB directly from the source FIT")
    args = ap.parse_args()
    backup = args.out.with_suffix(".original.fit")
    report_path = args.out.with_suffix(".json")
    if args.out.resolve() == args.source.resolve() or args.out.parent.resolve() == args.source.parent.resolve():
        ap.error("output must be outside the boot directory")
    if any(p.exists() for p in (args.out, backup, report_path)):
        ap.error("output or backup already exists; choose a fresh --out path")
    source = args.source.read_bytes()
    if args.auto_patch:
        try:
            from .patch_kernel_dtb import patch
        except ImportError:
            from patch_kernel_dtb import patch
        source_tree, _, _ = parse(source)
        dtb = child(child(source_tree, "images"), TARGET)["props"]["data"]
        patched = patch(dtb, args.base, args.bytes)
    else:
        patched = args.dtb.read_bytes()
    candidate = prepare(source, patched, args.base, args.bytes)
    if args.source.read_bytes() != source:
        raise RuntimeError("source changed during preparation; retry after updates finish")
    backup.write_bytes(source)
    args.out.write_bytes(candidate)
    report = {"source": str(args.source), "backup": str(backup), "candidate": str(args.out),
              "source_sha256": hashlib.sha256(source).hexdigest(),
              "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
              "modified_image": TARGET, "base": hex(args.base), "bytes": args.bytes,
              "verified": "all image hashes, DTB change, FIT metadata and payload preservation",
              "installed": False}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
