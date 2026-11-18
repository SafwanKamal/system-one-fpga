import copy
import hashlib
import json
import pytest
from sysone.v2.typed200_qualification import (ARTIFACTS, PREPARATION, FUNCTIONAL,
                                            TIMING, assess_preparation)


def put(root, name, data):
    raw = data if isinstance(data, bytes) else json.dumps(data).encode()
    (root/name).write_bytes(raw)
    return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}


def complete(root):
    artifacts = {role: put(root, role+'.bin', role.encode()) for role in ARTIFACTS}
    p = {'schema': 'sysone.typed200.qualification-preparation.v1',
         'artifacts': artifacts, 'reviews': {}, 'target_run_id': 'synthetic-unit-test'}
    for scope in PREPARATION + FUNCTIONAL + TIMING:
        r = {'schema': 'sysone.typed200.qualification-review.v1', 'scope': scope,
             'verdict': 'pass', 'artifact_sha256': {k: v['sha256'] for k, v in artifacts.items()},
             'evidence': [put(root, scope+'.evidence', b'synthetic test fixture')],
             'run_id': p['target_run_id'], 'instrumentation': 'reviewed_noninterfering'}
        p['reviews'][scope] = put(root, scope+'.json', r)
    return p


def test_complete_metadata_does_not_authorize_or_certify_hardware(tmp_path):
    r = assess_preparation(complete(tmp_path), tmp_path)
    assert r['timing_receipts_complete'] and not r['missing_or_invalid']
    assert not r['hardware_action_authorized'] and not r['target_execution_verified'] and not r['wcet_certified']


@pytest.mark.parametrize('role', ARTIFACTS)
def test_missing_or_changed_artifact_blocks_every_stage(tmp_path, role):
    p = complete(tmp_path);(tmp_path/p['artifacts'][role]['path']).write_bytes(b'changed')
    r = assess_preparation(p, tmp_path)
    assert not r['artifact_review_complete'] and 'artifact:'+role in r['missing_or_invalid']


@pytest.mark.parametrize('scope', PREPARATION+FUNCTIONAL+TIMING)
def test_missing_review_cannot_be_waived_by_ready_booleans(tmp_path, scope):
    p = complete(tmp_path);p['reviews'][scope] = None
    p['deployment_ready'] = p['wcet_certified'] = True
    r = assess_preparation(p, tmp_path)
    assert not r['timing_receipts_complete'] and not r['hardware_action_authorized']


@pytest.mark.parametrize('change', ['foreign', 'empty', 'diagnostic', 'scope', 'run', 'path', 'evidence'])
def test_stale_diagnostic_and_unbound_receipts_rejected(tmp_path, change):
    p = complete(tmp_path);scope = 'deadline_composition'
    r = json.loads((tmp_path/p['reviews'][scope]['path']).read_text())
    if change == 'foreign': r['artifact_sha256']['r5'] = '0'*64
    if change == 'empty': r['evidence'] = []
    if change == 'diagnostic': r['instrumentation'] = 'debugger_breakpoints'
    if change == 'scope': r['scope'] = 'another_scope'
    if change == 'run': r['run_id'] = 'another_run'
    if change == 'evidence': r['evidence'][0]['sha256'] = '0'*64
    if change == 'path': r['evidence'][0]['path'] = '../outside'
    p['reviews'][scope] = put(tmp_path, scope+'.json', r)
    result = assess_preparation(p, tmp_path)
    assert result['functional_receipts_complete'] and not result['timing_receipts_complete']


def test_unknown_schema_or_role_rejected(tmp_path):
    p = complete(tmp_path);q = copy.deepcopy(p);q['artifacts'].pop('fsbl')
    with pytest.raises(ValueError): assess_preparation(q, tmp_path)
    p['schema'] = 'other'
    with pytest.raises(ValueError): assess_preparation(p, tmp_path)
