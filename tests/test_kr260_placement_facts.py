"""Incomplete or inconsistent evidence must not be presented as routing approval."""
import json
from pathlib import Path
import shutil

import pytest

from scripts.v2.kr260.placement_facts import extract

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence(tmp_path):
    source = ROOT / 'build/v2/kr260-opt-operand-capture-large'
    if not (source / 'placement/frequency-diagnostics.json').exists():
        pytest.skip('Completed placement fixture unavailable')
    (tmp_path / 'placement').mkdir()
    shutil.copyfile(source / 'regression.json', tmp_path / 'regression.json')
    for name in ['completion-status.json', 'frequency-diagnostics.json', 'congestion.rpt',
                 'utilization.rpt', 'timing-200mhz.rpt', 'critical-200mhz.rpt', 'placement-result.json']:
        shutil.copyfile(source / 'placement' / name, tmp_path / 'placement' / name)
    (tmp_path / 'placement/system_wrapper_placed.dcp').write_bytes(b'fixture, not a hardware checkpoint')
    return tmp_path


def test_known_marginal_placement_requires_review(evidence):
    result = extract(evidence)
    assert result['setup_ns'] == .441 and result['hold_ns'] == -.088
    assert result['clb_percent'] == 97.1 and result['congestion_level'] == 5
    assert not result['minimum_setup_margin_met'] and not result['route_approved']
    assert result['review_required'] and len(result['critical_paths']) == 30


@pytest.mark.parametrize('fault', ['unfinished', 'missing_frequency', 'stale_slack'])
def test_inconsistent_reports_rejected(evidence, fault):
    if fault == 'unfinished':
        (evidence / 'placement/completion-status.json').write_text('{"state":"placing"}')
    else:
        path = evidence / 'placement/frequency-diagnostics.json'
        sweep = json.loads(path.read_text())
        if fault == 'missing_frequency':
            sweep.pop()
        else:
            next(row for row in sweep if row['mhz'] == 200)['estimated_setup_slack_ns'] = .8
        path.write_text(json.dumps(sweep))
    with pytest.raises(ValueError):
        extract(evidence)
