import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'scripts/v2/kr260'
sys.path.insert(0, str(TOOLS))
from create_locality300_candidate import OUT, verify
from build_locality300 import numerical_gate, placement_tcl, project_tcl


def test_qualified_sources_and_candidate_are_hash_bound_and_not_deployable():
    m = verify()
    assert len(m['baseline_sha256']) == 23
    assert len(m['candidate_sha256']) == 24
    assert m['capability_word'] == '0x5387ffff'
    assert not m['timing_qualified'] and not m['hardware_qualified']
    assert m['profiles']['encoder384']['max_hidden'] == 384
    assert m['profiles']['capacity1024']['max_hidden'] == 1024


def test_build_setup_preserves_profile_sources_and_stops_before_route(tmp_path):
    for profile, capacity in [('encoder384', 384), ('capacity1024', 1024)]:
        text, setup_hash = project_tcl(profile, tmp_path)
        assert f'set_property CONFIG.MAX_HIDDEN {capacity} $enc' in text
        assert 'rtl v2 candidates locality300' in text
        assert 'common deadline_supervisor.sv' in text
        assert f'build v2 locality300-{profile}' in text
        assert 'write_bitstream' not in text and 'route_design' not in text
        assert len(setup_hash) == 64


def test_placement_has_no_route_export_or_timing_exception():
    text = placement_tcl('encoder384')
    assert 'foreach mhz {200 250 300}' in text
    assert 'place_design' in text
    for forbidden in ['route_design', 'write_bitstream', 'set_false_path', 'set_multicycle_path']:
        assert forbidden not in text


def test_incomplete_regression_cannot_admit_synthesis(monkeypatch, tmp_path):
    import build_locality300 as build
    regression = tmp_path / 'locality300-regression'
    regression.mkdir()
    (regression / 'completion-status.json').write_text(json.dumps({'exit_code': 1, 'complete': False}))
    monkeypatch.setattr(build, 'BUILD', tmp_path)
    with pytest.raises(ValueError, match='Complete candidate regression'):
        build.numerical_gate()
