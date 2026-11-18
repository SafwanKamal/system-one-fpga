import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

SCRIPT=Path(__file__).parents[1]/'scripts/v2/board_status.py'
spec=importlib.util.spec_from_file_location('board_status',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def initial(tmp_path,state='ready'):
    p=tmp_path/'BOARD_STATUS.json'
    p.write_text(json.dumps(dict(canonical_path=str(p.resolve()),revision=0,reservation=None,
        current=dict(state=state),events=[])))
    return p


def test_reservation_is_persistent_and_second_agent_cannot_claim(tmp_path):
    p=initial(tmp_path)
    data=module.transact(p,'reserve',owner='Claude',purpose='candidate RTL')
    with pytest.raises(ValueError,match='reserved by Claude'):
        module.transact(p,'reserve',owner='Codex',purpose='benchmark')
    assert json.loads(p.read_text())['reservation']==data['reservation']
    with pytest.raises(ValueError,match='does not match'):module.transact(p,'release',claim='wrong')


def test_programming_must_leave_a_verified_or_explicit_unknown_observation(tmp_path):
    p=initial(tmp_path);d=module.transact(p,'reserve',owner='Claude',purpose='program')
    claim=d['reservation']['claim_id'];module.transact(p,'begin',claim=claim,operation='program candidate')
    with pytest.raises(ValueError,match='Record verified result'):module.transact(p,'release',claim=claim)
    with pytest.raises(ValueError,match='needs verified_at_utc'):
        module.transact(p,'record',claim=claim,observation=dict(state='ready'))
    observed=dict(state='ready',verified_at_utc='2026-10-21T12:00:00Z',evidence=['candidate-report.json'],
                  active_package='/var/lib/sysone/candidate',boot_id='boot-new')
    module.transact(p,'record',claim=claim,observation=observed)
    d=module.transact(p,'release',claim=claim)
    assert d['reservation'] is None and d['current']['active_package']==observed['active_package']


def test_unknown_state_fails_closed_but_allows_explicit_recovery(tmp_path):
    p=initial(tmp_path,'unknown')
    with pytest.raises(ValueError,match='uncertain'):module.transact(p,'reserve',owner='Codex',purpose='run benchmark')
    d=module.transact(p,'reserve',owner='Codex',purpose='RECOVERY: inspect live image')
    assert d['reservation']['owner']=='Codex'


def test_worktree_copy_is_rejected(tmp_path):
    canonical=initial(tmp_path);copied=tmp_path/'copy.json';copied.write_bytes(canonical.read_bytes())
    with pytest.raises(ValueError,match='canonical status file'):module.transact(copied,'show')


def test_two_processes_racing_for_board_have_exactly_one_winner(tmp_path):
    p=initial(tmp_path)
    procs=[subprocess.Popen([sys.executable,str(SCRIPT),'--file',str(p),'reserve','--owner',owner,
                            '--purpose','race-test'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
           for owner in ('Codex','Claude')]
    for proc in procs:proc.communicate(timeout=15)
    assert sorted(proc.returncode for proc in procs)==[0,2]
    d=json.loads(p.read_text())
    assert d['revision']==1 and d['reservation']['owner'] in ('Codex','Claude')
