import copy
import struct

import pytest

from scripts.v2.kr260 import patch_kernel_dtb as kd
from scripts.v2.kr260.prepare_reserved_fit import child, pack, parse


def original():
    return {"name": "", "props": {"model": b"ZynqMP KR260 revB\0"}, "children": [
        {"name": "reserved-memory", "props": {"#address-cells": struct.pack(">I", 2),
         "#size-cells": struct.pack(">I", 2), "ranges": b""}, "children": [
            {"name": "pmu@7ff00000", "props": {"reg": struct.pack(">QQ", 0x7ff00000, 0x100000)},
             "children": []}]}]}


def test_preserves_other_nodes_and_is_idempotent():
    source = pack(original(), bytes(16), (16, 0))
    result = kd.patch(source)
    assert result != source
    assert kd.patch(result) == result
    tree, _, _ = parse(result)
    parent = child(tree, "reserved-memory")
    reservation = child(parent, kd.RESERVATION)
    assert reservation["props"] == kd.EXPECTED
    parent["children"].remove(reservation)
    assert tree == original()


def test_refuses_overlapping_reservation():
    tree = original()
    child(tree, "reserved-memory")["children"][0]["props"]["reg"] = struct.pack(">QQ", 0x61000000, 4096)
    with pytest.raises(ValueError, match="overlaps"):
        kd.patch(pack(tree, bytes(16), (16, 0)))


def test_refuses_conflicting_existing_node():
    tree = original()
    child(tree, "reserved-memory")["children"].append(
        {"name": kd.RESERVATION, "props": {}, "children": []})
    with pytest.raises(ValueError, match="differs"):
        kd.patch(pack(tree, bytes(16), (16, 0)))


def test_refuses_wrong_board():
    tree = original()
    tree["props"]["model"] = b"different board\0"
    with pytest.raises(ValueError, match="not the KR260"):
        kd.patch(pack(tree, bytes(16), (16, 0)))


def test_resize_to_256_mib_preserves_other_nodes_and_is_idempotent():
    small = kd.patch(pack(original(), bytes(16), (16, 0)))
    expanded = kd.patch(small, size=256 << 20)
    tree, _, _ = parse(expanded)
    parent = child(tree, "reserved-memory")
    region = child(parent, kd.RESERVATION)
    assert region["props"]["reg"] == struct.pack(">QQ", 0x60000000, 256 << 20)
    parent["children"].remove(region)
    assert tree == original()
    assert kd.patch(expanded, size=256 << 20) == expanded


def test_enlargement_cannot_cover_pmu_or_memreserve():
    small = kd.patch(pack(original(), bytes(16), (16, 0)))
    with pytest.raises(ValueError, match="overlaps"):
        kd.patch(small, size=512 << 20)
    reserve = struct.pack(">QQ", 0x68000000, 4096) + bytes(16)
    with pytest.raises(ValueError, match="reservation map"):
        kd.patch(pack(original(), reserve, (16, 0)), size=256 << 20)


@pytest.mark.parametrize("base,size", [(1,4096),(0x60000000,0),(0x60000000,1),
                                      (0x800000000,256 << 20)])
def test_invalid_or_unmapped_budget_is_refused(base, size):
    with pytest.raises(ValueError, match="low DDR"):
        kd.patch(pack(original(), bytes(16), (16, 0)), base, size)
