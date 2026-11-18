"""Preservation and physical-flow guard checks for the telemetry successor."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/v2/kr260'))
import create_counter300_candidate as candidate
import build_counter300 as build


def test_successor_only_changes_top_and_adds_telemetry():
    m = candidate.verify()
    parent = candidate.parent.verify()
    changed = {n for n, h in parent['candidate_sha256'].items() if m['candidate_sha256'][n] != h}
    assert changed == {'platform/kr260/kr260_encoder.sv'}
    assert set(m['candidate_sha256']) - set(parent['candidate_sha256']) == {'common/performance_telemetry.sv'}
    assert m['capability_word'] == '0x5397ffff'
    assert m['telemetry_latency_cycles'] == 1
    assert not m['hardware_qualified']


def test_isolated_build_and_mapping_cuts(tmp_path):
    text, _ = build.project_tcl('encoder384', tmp_path)
    assert 'rtl v2 candidates counter300' in text
    assert 'build v2 counter300-encoder384' in text
    assert 'common performance_telemetry.sv' in text
    assert 'telemetry_inst*delta_reg*' in text
    assert 'Telemetry input cut disappeared' in text
    for text in [text, build.placement_tcl('encoder384')]:
        for forbidden in ['route_design', 'write_bitstream', 'set_false_path', 'set_multicycle_path']:
            assert forbidden not in text


def test_build_requires_completed_counter_equivalence(monkeypatch, tmp_path):
    import json
    p = tmp_path / 'counter300-regression-v2'
    p.mkdir()
    (p / 'completion-status.json').write_text(json.dumps({'exit_code': 1, 'complete': False}))
    monkeypatch.setattr(build, 'BUILD', tmp_path)
    with pytest.raises(ValueError, match='Complete candidate regression'):
        build.numerical_gate()
