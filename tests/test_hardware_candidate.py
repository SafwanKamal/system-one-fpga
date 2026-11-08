"""Integration checks for the consolidated runtime and immutable packaging."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate_packager', ROOT / 'scripts/v2/package_hardware_candidate.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_checked_path_rejects_package_escape(tmp_path):
    with pytest.raises(RuntimeError, match='escapes'):
        packager.checked(tmp_path, '../outside')


def test_matrix_ii_regression_is_not_hidden_by_exception_count():
    record = "Pipelining result : Target II = 1, Final II = 2, Depth = 10, loop 'matrix'"
    with pytest.raises(RuntimeError, match='pipeline II'):
        packager.verify_pipeline_ii(record, {'residual': 2})
    packager.verify_pipeline_ii(record.replace("'matrix'", "'residual'"), {'residual': 2})
    with pytest.raises(RuntimeError, match='No HLS'):
        packager.verify_pipeline_ii('', {})


def test_packager_rejects_changed_pinned_input(tmp_path):
    lock = tmp_path / packager.LOCK
    lock.parent.mkdir(parents=True)
    (tmp_path / 'source').write_bytes(b'changed')
    lock.write_text(json.dumps(dict(artifacts_sha256={'source': '0' * 64})))
    with pytest.raises(RuntimeError, match='Pinned input changed'):
        packager.verify(tmp_path)


def test_packager_preserves_existing_output(tmp_path, monkeypatch):
    source = tmp_path / 'historical'
    source.mkdir()
    output = tmp_path / 'candidate'
    output.mkdir()
    marker = output / 'preserved'
    marker.write_bytes(b'original')
    monkeypatch.setattr(packager, 'verify', lambda root: ({}, source, {}))
    with pytest.raises(RuntimeError, match='output exists'):
        packager.assemble(output, tmp_path)
    assert marker.read_bytes() == b'original'


@pytest.mark.skipif(sys.platform == 'win32', reason='Linux FPGA runtime imports fcntl')
@pytest.mark.parametrize('offset,size', [(0, 4), (0, 64), (4, 68), (0, 156), (4, 156), (8, 1028), (0, 4096)])
def test_device_transfers_use_only_aligned_full_chunks_or_scalar_words(offset, size, monkeypatch):
    from sysone.v2 import qwen_fpga_runtime_candidate as runtime
    scratch = bytearray(size + offset + 16)
    calls = []
    original = struct.pack_into

    def pack(fmt, dest, address, *values):
        calls.append((fmt, address))
        assert fmt == '<I' or (fmt == '<16I' and address % 64 == 0)
        original(fmt, dest, address, *values)

    monkeypatch.setattr(runtime.struct, 'pack_into', pack)
    payload = bytes(i % 256 for i in range(size))
    runtime.QwenFpga._copy_words(SimpleNamespace(scratch=scratch), offset, payload)
    assert scratch[offset:offset+size] == payload
    assert scratch[offset+size:] == bytes(16)
    assert calls


@pytest.mark.skipif(sys.platform == 'win32', reason='Linux FPGA runtime imports fcntl')
def test_device_transfer_rejects_unaligned_payload():
    from sysone.v2.qwen_fpga_runtime_candidate import QwenFpga
    for offset, data in [(1, bytes(4)), (0, bytes(3))]:
        with pytest.raises(ValueError, match='Unaligned'):
            QwenFpga._copy_words(SimpleNamespace(scratch=bytearray(100)), offset, data)


def test_full_context_admission_and_prefix_reuse():
    from test_arm_service_candidate import make
    session, events = make()
    session.engine.context = 2048
    session.vocab.encode_text = lambda text: list(range(1984))
    request = dict(op='generate', query='long', max_tokens=64)
    first = session.generate(request)
    second = session.generate(request)
    assert first['prefix_tokens_reused'] == 0
    assert second['prefix_tokens_reused'] == 1976
    assert second['work']['prefill_tokens'] == 8
    events.clear()
    with pytest.raises(ValueError, match='context'):
        session.generate(dict(request, max_tokens=65))
    assert not events and session.state == 'READY'


@pytest.mark.skipif(sys.platform == 'win32', reason='Linux FPGA runtime imports fcntl')
@pytest.mark.parametrize('refuse_lease', [False, True])
def test_runtime_initialization_uses_bf16_extent_and_claims_abi2_before_mmio(tmp_path, monkeypatch, refuse_lease):
    from sysone.v2 import qwen_fpga_runtime_candidate as runtime
    from sysone.v2 import qwen_dma_ownership_v16 as dma
    from sysone.v2 import qwen_weight_verification_v16 as verifier
    package = tmp_path / 'package'
    app = package / runtime.APP
    app.mkdir(parents=True)
    profile = dict(hidden=1024, ffn=3072, q_heads=16, kv_heads=8, head_dim=128,
                   layers=28, max_context=2048, vocab=151936, prefill_batch=8,
                   quantization='Q8_0', activation_quantization='symmetric INT8 block32')
    model = dict(profile, embedding=0, output_norm=32, layer_offsets=[[0]*11]*28,
                 bytes=64, sha256='pinned')
    (package / 'model-manifest.json').write_text(json.dumps(model))
    (package / 'registers.json').write_text(json.dumps(dict(model=16, scratch=24)))
    (package / 'rope.bin').write_bytes(bytes(2048*512))
    (app / 'build.json').write_text(json.dumps(dict(model_profile=profile, bitstream_sha256='bit')))
    fake = tmp_path / 'system'
    dt = fake / 'sys/firmware/devicetree/base'
    files = {
        'sys/firmware/devicetree/base/__symbols__/amba': b'/amba\0',
        'sys/firmware/devicetree/base/amba/qwen-decoder@a0000000/compatible': b'xlnx,qwen-decoder-v9e-1.0\0',
        'sys/class/fpga_manager/fpga0/state': b'operating',
        'sys/kernel/debug/clk/clk_summary': b'pl0_ref 1 0 0 124999999\npl1_ref 1 0 0 249999998\n',
        'sys/class/misc/sysone_qwen_dma/buffers': b'present',
        'proc/sys/kernel/random/boot_id': b'boot',
        'sys/firmware/devicetree/base/reserved-memory/sysone@0/no-map': b'',
        # BF16 context2048 fits 256 MiB; the old FP32 formula would reject it.
        'sys/firmware/devicetree/base/reserved-memory/sysone@0/reg': struct.pack('>QQ', 0x60000000, 0x10000000),
    }
    for name, value in files.items():
        path = fake / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    real_path = Path
    monkeypatch.setattr(runtime, 'Path', lambda p: fake / str(p).lstrip('/')
                        if str(p).startswith(('/sys/', '/proc/')) else real_path(p))
    monkeypatch.setattr(runtime, 'bound', lambda *a: True)
    monkeypatch.setattr(runtime, 'active_firmware', lambda *a: runtime.APP+'.bit.bin')
    monkeypatch.setattr(runtime, 'dma_segments', lambda: (dict(model_bytes=64), []))
    events = []
    lease = dict(abi=2, sealed=1, loading=0, generation=2, owner_tgid=1)

    def claim(fd):
        events.append('claim')
        if refuse_lease:
            raise RuntimeError('Ownership-capable DMA ABI2 required')
    monkeypatch.setattr(dma, 'claim_inference', claim)
    monkeypatch.setattr(dma, 'ownership', lambda: dict(lease))
    monkeypatch.setattr(verifier, 'verify_weights', lambda *a: events.append('hash') or
                        dict(model_verify_ms=1, model_verify_method='full_sha'))
    monkeypatch.setattr(runtime.os, 'open', lambda *a: events.append(str(a[0])) or 10)
    monkeypatch.setattr(runtime.os, 'close', lambda fd: events.append('close'))
    monkeypatch.setattr(runtime.mmap, 'mmap', lambda *a, **kw: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(runtime.QwenFpga, '_copy_words', lambda *a: None)
    monkeypatch.setattr(runtime.QwenFpga, '_w', lambda *a: None)
    monkeypatch.setattr(runtime.QwenFpga, 'command', lambda *a, **kw: events.append('command'))
    if refuse_lease:
        with pytest.raises(RuntimeError, match='ABI2'):
            runtime.QwenFpga(package)
        assert events == ['/dev/sysone_qwen_dma', 'claim', 'close']
    else:
        engine = runtime.QwenFpga(package)
        assert engine.context == 2048 and engine.dma_abi == 2
        assert events == ['/dev/sysone_qwen_dma', 'claim', 'hash', '/dev/mem', 'command']
        assert engine.rope_copy_mode == 'written (64-byte chunks)'
        engine.close()
