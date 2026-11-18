"""KR260 host guardrails, with no physical board or /dev/mem access."""
from types import SimpleNamespace

import pytest

from sysone.v2.kr260_link import Kr260Link


def test_performance_counters_are_versioned_and_require_idle():
    link = Kr260Link.__new__(Kr260Link)
    registers = {0x1C: 0, 0: 0}
    link._r = lambda offset: registers.get(offset, offset)
    assert link.performance_counters() is None
    registers[0x1C] = 0x53590108  # UltraRAM but counters absent
    assert link.performance_counters() is None
    registers[0x1C] = 0x5359010F
    registers[0] = 1
    with pytest.raises(RuntimeError, match="idle"):
        link.performance_counters()
    registers[0] = 2
    counts = link.performance_counters()
    assert len(counts) == 10
    assert counts["axi_read_beats"] == 0x30
    assert counts["result_source_wait"] == 0x54


@pytest.mark.parametrize('capability,accepted', [
    (0x5377ffff,True),(0x5373ffff,False),(0x5375ffff,False),(0x5376ffff,False),(0x5363ffff,True),(0x5361ffff,False),(0x5362ffff,False),(0x5363fffe,False),
    (0x535affff, True), (0x535a7fff, False), (0x535abfff, False), (0x535afffe, False),
    (0x53597fff, True), (0x53595fff, False), (0x53596fff, False), (0x53597ffe, False), (0x535907ff, True), (0x53591fff, True), (0x535917ff, False),
    (0x53591bff, False), (0x53590301, False), (0x53591ffe, False),
])
def test_new_counters_require_exact_supported_layout(capability, accepted):
    link = Kr260Link.__new__(Kr260Link)
    link._r = lambda offset: capability if offset == 0x1c else 0 if offset == 0 else offset
    counters = link.performance_counters()
    if accepted:
        assert len(counters) == 10 and counters['result_source_wait'] == 0x54
    else:
        assert counters is None


def test_failed_probe_closes_mapping_and_fd(monkeypatch):
    from sysone.v2 import kr260_link as kl
    monkeypatch.setattr(kl, "check_runtime", lambda *a: {"clock_hz": 71428571})
    class Mapping(bytearray):
        closed = False
        def close(self):
            self.closed = True
    regs = Mapping(4096)
    closed = []
    monkeypatch.setattr(kl.os, "open", lambda *a: 42)
    monkeypatch.setattr(kl.os, "close", closed.append)
    monkeypatch.setattr(kl.os, "O_SYNC", 0, raising=False)
    monkeypatch.setattr(kl.mmap, "mmap", lambda *a, **kw: regs)
    for name in ("MAP_SHARED", "PROT_READ", "PROT_WRITE"):
        monkeypatch.setattr(kl.mmap, name, 1, raising=False)
    with pytest.raises(IOError, match="no kr260_encoder"):
        Kr260Link()
    assert regs.closed and closed == [42]


@pytest.mark.parametrize('build,features', [
    (0x20803004, 0x53591fff), (0x20804004, 0x535907ff),
    (0x20804004, 0x535917ff), (0x20804004, 0x53591bff),
])
def test_stale_frontier_hardware_never_maps_ddr(monkeypatch, build, features):
    import struct
    from sysone.v2 import kr260_link as kl
    monkeypatch.setattr(kl, 'check_runtime', lambda *args: {
        'clock_hz': 200000000, 'expected_build': 0x20804004,
        'expected_capabilities': 0x53591fff})
    class Mapping(bytearray):
        closed = False
        def close(self):
            self.closed = True
    regs = Mapping(4096)
    struct.pack_into('<III', regs, 0x14, 0x53595332, build, features)
    mappings = []
    def map_registers(*args, **kwargs):
        mappings.append(kwargs['offset'])
        assert kwargs['offset'] == 0xa0000000, 'DDR must not be mapped'
        return regs
    closed = []
    monkeypatch.setattr(kl.os, 'open', lambda *args: 42)
    monkeypatch.setattr(kl.os, 'close', closed.append)
    monkeypatch.setattr(kl.os, 'O_SYNC', 0, raising=False)
    monkeypatch.setattr(kl.mmap, 'mmap', map_registers)
    for name in ('MAP_SHARED', 'PROT_READ', 'PROT_WRITE'):
        monkeypatch.setattr(kl.mmap, name, 1, raising=False)
    with pytest.raises(IOError, match='loaded app profile'):
        Kr260Link()
    assert mappings == [0xa0000000] and regs.closed and closed == [42]


def test_image_and_request_must_fit_build_and_region():
    link = Kr260Link.__new__(Kr260Link)
    link.mem_base, link.mem_size = 0x60000000, 64 << 20
    link.build = dict(tile_out=32, max_tokens=128, max_hidden=384, drain_lanes=4)
    header = dict(base=link.mem_base, tile_in=16, tile_out=32, max_tokens=128, hidden=384)
    layout = SimpleNamespace(ids=link.mem_base + (24 << 20), result=link.mem_base + (24 << 20) + 4096,
                             max_tokens=128, hidden=384)
    link.validate_image(header, 23 << 20, layout)
    with pytest.raises(ValueError, match="tile"):
        link.validate_image(dict(header, tile_out=12), 23 << 20, layout)
    with pytest.raises(ValueError, match="dimensions"):
        link.validate_image(dict(header, max_tokens=256), 23 << 20, layout)
    layout.result = link.mem_base + link.mem_size - 16
    with pytest.raises(ValueError, match="reserved region"):
        link.validate_image(header, 23 << 20, layout)
    with pytest.raises(ValueError):
        link._span(link.mem_base, -1)


def test_wide_build_accepts_768_but_refuses_oversized_ffn_and_heads():
    link=Kr260Link.__new__(Kr260Link)
    link.mem_base,link.mem_size=0x60000000,256 << 20
    link.build=dict(tile_out=32,max_tokens=128,max_hidden=768,drain_lanes=4)
    header=dict(base=link.mem_base,tile_in=16,tile_out=32,max_tokens=128,hidden=768,ffn=3072,head_dim=64)
    layout=SimpleNamespace(ids=link.mem_base+(110 << 20),result=link.mem_base+(110 << 20)+4096,
                           max_tokens=128,hidden=768)
    link.validate_image(header,110 << 20,layout)
    for wrong in (dict(header,hidden=784),dict(header,ffn=4096),dict(header,head_dim=128)):
        with pytest.raises(ValueError,match="dimensions"):
            link.validate_image(wrong,110 << 20,layout)


def test_invalid_region_rejected_before_device_open():
    with pytest.raises(ValueError, match="page-aligned"):
        Kr260Link(memory=(1, 4096))
    with pytest.raises(ValueError, match="4 GiB"):
        Kr260Link(memory=(0xFFFFF000, 8192))


def test_runtime_rejection_never_opens_mmio(monkeypatch):
    from sysone.v2 import kr260_link as kl
    def refuse(*args):
        raise IOError("sysone-v2 overlay is absent")
    def forbidden(*args):
        pytest.fail("MMIO must not open when runtime preflight fails")
    monkeypatch.setattr(kl, "check_runtime", refuse)
    monkeypatch.setattr(kl.os, "open", forbidden)
    with pytest.raises(IOError, match="overlay is absent"):
        Kr260Link()


def test_missing_image_rejected_without_encoder_writes():
    link = Kr260Link.__new__(Kr260Link)
    link.mem_base, link.mem_size, link.mem = 0x60000000, 4096, bytearray(4096)
    with pytest.raises(IOError, match="not loaded"):
        link.verify_loaded_image(0x60000000, b"model")
    link.mem[:5] = b"model"
    link.verify_loaded_image(0x60000000, b"model")
