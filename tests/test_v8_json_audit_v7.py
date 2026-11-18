"""Audit regression checks independent of model calls and old evidence files."""
import copy
import pytest
from sysone.v2.v8_json_diagnostics_v7 import audit_v6


def fixture():
    case=dict(id='unit',mode='closed-loop',initial={'A':[10,'ok'],'B':[70,'ok']},
              steps=[dict(entity='A',op='add',number=3)])
    row=dict(id='unit-J-1',case_id='unit',step=1,suite='dependent',mode='closed-loop',
             status='completed',arm='J',split='development',state_before=case['initial'],
             expected=['ok','A',13],local_expected=['ok','A',13],observed=['ok','A',99],
             state_after={'A':[99,'ok'],'B':[70,'ok']},terminal_eos=True,
             state_matches_snapshot_control=True,generated_text='["ok","A",99]')
    return row,dict(cases=[case])


def test_audit_preserves_wrong_proposal_and_detects_local_error():
    row,spec=fixture();before=copy.deepcopy(row)
    result=audit_v6([row],spec)
    assert result['by_arm']['J']=={'new-local-error':1}
    assert row==before


@pytest.mark.parametrize('field,value',[
    ('expected',['ok','A',99]),('local_expected',['ok','A',99]),
    ('state_after',{'A':[13,'ok'],'B':[70,'ok']})])
def test_audit_detects_bad_gold_local_or_hidden_repair(field,value):
    row,spec=fixture();row[field]=value
    with pytest.raises(RuntimeError):audit_v6([row],spec)
