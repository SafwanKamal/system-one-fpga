"""FIT preparation preserves boot contents and refuses unrelated DTB edits."""
import copy
import hashlib
import shutil
import struct
import subprocess

import pytest

from scripts.v2.kr260 import prepare_reserved_fit as fit


def node(name, props=None, children=None):
    return dict(name=name, props=props or {}, children=children or [])


def blob(tree):
    return fit.pack(tree, bytes(16), (16, 0))


@pytest.fixture
def inputs():
    dt = node("", {"model": b"ZynqMP KR260 revB\0"}, [node("reserved-memory",
        {"#address-cells": struct.pack(">I", 2), "#size-cells": struct.pack(">I", 2), "ranges": b""},
        [node("pmu@7ff00000", {"reg": struct.pack(">4I", 0, 0x7ff00000, 0, 0x100000), "no-map": b""})])])
    patched = copy.deepcopy(dt)
    fit.child(patched, "reserved-memory")["children"].insert(0, node(fit.RESERVATION,
        {"no-map": b"", "reg": struct.pack(">4I", 0, 0x60000000, 0, 0x4000000)}))
    images = []
    for name, payload in (("kernel-1", b"kernel contents"), ("ramdisk-1", b"ramdisk contents"),
                          (fit.TARGET, blob(dt)), ("fdt-other", blob(dt))):
        images.append(node(name, {"data": payload, "compression": b"none\0", "arch": b"arm64\0"},
            [node("hash-1", {"algo": b"sha1\0", "value": hashlib.sha1(payload).digest()})]))
    tree = node("", {"timestamp": struct.pack(">I", 123)}, [node("images", children=images),
        node("configurations", {"default": b"conf-1\0"}, [node("conf-1",
            {"kernel": b"kernel-1\0", "ramdisk": b"ramdisk-1\0", "fdt": fit.TARGET.encode() + b"\0"},
            [node("hash-1", {"algo": b"sha1\0"})])])])
    return tree, patched


def test_preserves_all_other_boot_data_and_hashes(inputs, tmp_path):
    tree, patched = inputs
    candidate = fit.prepare(blob(tree), blob(patched))
    rebuilt, _, _ = fit.parse(candidate)
    assert fit.child(rebuilt, "configurations") == fit.child(tree, "configurations")
    assert rebuilt["props"] == tree["props"]
    for old, new in zip(fit.child(tree, "images")["children"], fit.child(rebuilt, "images")["children"]):
        if old["name"] != fit.TARGET:
            assert old == new
        fit.verify_hashes(new)
    # Independent validation with the actual device-tree compiler, when installed.
    dtc = shutil.which("dtc")
    if dtc:
        path = tmp_path / "candidate.fit"
        path.write_bytes(candidate)
        out = subprocess.run([dtc, "-q", "-I", "dtb", "-O", "dts", str(path)],
                             capture_output=True, check=True)
        assert b"configurations" in out.stdout
        path.write_bytes(fit.child(fit.child(rebuilt, "images"), fit.TARGET)["props"]["data"])
        out = subprocess.run([dtc, "-q", "-I", "dtb", "-O", "dts", str(path)],
                             capture_output=True, check=True)
        assert b"sysone@60000000" in out.stdout and b"no-map" in out.stdout


def test_rejects_corrupt_payload(inputs):
    tree, patched = inputs
    fit.child(fit.child(tree, "images"), "kernel-1")["props"]["data"] = b"corrupt"
    with pytest.raises(ValueError, match="bad source hash"):
        fit.prepare(blob(tree), blob(patched))


def test_rejects_unrelated_dtb_edits(inputs):
    tree, patched = inputs
    patched["props"]["model"] = b"different board\0"
    with pytest.raises(ValueError, match="beyond"):
        fit.prepare(blob(tree), blob(patched))


def test_rejects_wrong_reservation(inputs):
    tree, patched = inputs
    fit.child(fit.child(patched, "reserved-memory"), fit.RESERVATION)["props"]["reg"] = bytes(16)
    with pytest.raises(ValueError, match="unexpected encoder"):
        fit.prepare(blob(tree), blob(patched))


def test_rejects_signed_fit(inputs):
    tree, patched = inputs
    tree["children"].append(node("signature-1"))
    with pytest.raises(ValueError, match="signed FIT"):
        fit.prepare(blob(tree), blob(patched))


def test_rejects_truncated_input():
    with pytest.raises(ValueError, match="truncated"):
        fit.parse(bytes(20))


def test_fit_resize_preserves_other_payloads(inputs):
    from scripts.v2.kr260.patch_kernel_dtb import patch
    tree, old = inputs
    target = fit.child(fit.child(tree, "images"), fit.TARGET)
    target["props"]["data"] = blob(old)
    target["children"][0]["props"]["value"] = hashlib.sha1(blob(old)).digest()
    changed = patch(blob(old), size=256 << 20)
    result, _, _ = fit.parse(fit.prepare(blob(tree), changed, size=256 << 20))
    for before, after in zip(fit.child(tree,"images")["children"], fit.child(result,"images")["children"]):
        if before["name"] != fit.TARGET: assert before == after
        fit.verify_hashes(after)
    dt, _, _ = fit.parse(fit.child(fit.child(result,"images"),fit.TARGET)["props"]["data"])
    assert fit.child(fit.child(dt,"reserved-memory"),fit.RESERVATION)["props"]["reg"] == struct.pack(">QQ",0x60000000,256 << 20)
