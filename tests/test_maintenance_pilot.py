import copy
import json
import pytest
from sysone.v2.maintenance.schema import node, plan, terminal, validate, encode, parse, canonical
from sysone.v2.maintenance.simulator import world, execute, counterfactuals
from sysone.v2.maintenance.dataset import pilot, public_input, prompt, score, make_case, manifest, STRATA
from sysone.v2.maintenance.baselines import flatten, unflatten, rules


def conditional(op='gt', rhs='limit'):
    return plan(node('read_metric','P3',metric='temperature'),
                node('read_history','P3',guard=True,metric='temperature',count=3),
                node('draft_report','P3',guard=True,priority='high',evidence=[0,1]),
                predicate=dict(source=0,op=op,rhs=rhs))


@pytest.mark.parametrize('op,counts',[('gt',[0,0,1]),('ge',[0,1,1]),('lt',[1,0,0]),('le',[1,1,0])])
def test_branch_boundary_and_error_status(op,counts):
    ast=conditional(op)
    for val,count in zip((69,70,71),counts):
        initial=world(['P3'],value=val)
        result=execute(ast,initial)
        assert len(result['state']['reports'])==count
        assert result['trace'][1]['status']==('ok' if count else 'skipped')
        assert initial['reports']==[]
    for status in ('missing','error'):
        result=execute(ast,world(['P3'],status=status))
        assert result['outcome']=='tool_error'
        assert len(result['trace'])==1
        assert result['trace'][0]['status']==status
        assert not result['state']['reports']


def test_evidence_preserves_results_and_epoch_without_world_mutation():
    ast=conditional()
    initial=world(['P3'])
    result=execute(ast,initial)
    report=result['state']['reports'][0]
    assert report['evidence'][0]['sample_id']=='P3/temperature/1'
    assert len(report['evidence'][1]['samples'])==3
    assert all(r['epoch']==1 for r in report['evidence'])
    report['evidence'][0]['value']=999
    assert initial['assets']['P3']['metrics']['temperature']['value']==75
    assert result['trace'][0]['result']['value']==75


def test_fixed_point_explicit_threshold_uses_reading_scale():
    ast=plan(node('read_metric','P3',metric='current'),
             node('request_inspection','P3',guard=True,priority='normal',evidence=[0]),
             predicate=dict(source=0,op='ge',rhs=70))
    assert len(execute(ast,world(['P3'],value=70))['state']['inspections'])==1
    assert len(execute(ast,world(['P3'],value=69))['state']['inspections'])==0


@pytest.mark.parametrize('kind,reason',[('clarify','ambiguous_asset'),('clarify','missing_reference'),
    ('clarify','missing_asset'),('clarify','contradiction'),('reject','unknown_asset'),
    ('reject','unsupported_unit'),('reject','unsupported_value'),('reject','plan_capacity'),
    ('reject','unsupported_operation')])
def test_terminal_outcome_cannot_execute_tools(kind,reason):
    ast=terminal(kind,reason)
    assert parse(encode(ast))==ast
    initial=world(['P3'])
    result=execute(ast,initial)
    assert result['trace']==[] and result['state']==initial


@pytest.mark.parametrize('mutation',[
    lambda a: a['steps'][0].update(guard=1),
    lambda a: a['steps'][0].update(unexpected=True),
    lambda a: a['steps'][1].update(count=True),
    lambda a: a['steps'][1].update(count=6),
    lambda a: a['steps'][1].update(asset='P4'),
    lambda a: a['steps'][2].update(evidence=[2]),
    lambda a: a['steps'][2].update(evidence=[0,0]),
    lambda a: a['steps'][2].update(guard=False),
    lambda a: a['predicate'].update(source=1),
    lambda a: a['predicate'].update(rhs=70.0),
    lambda a: a['predicate'].update(op='eq'),
    lambda a: a['steps'].append(copy.deepcopy(a['steps'][0])),
])
def test_malformed_or_incoherent_plans_fail_closed(mutation):
    ast=conditional();mutation(ast)
    with pytest.raises(ValueError):validate(ast)


@pytest.mark.parametrize('raw',[
    '["plan",[["read_metric","P3",{"metric":"temperature","metric":"current"},false]],null]',
    '```json\n["reject","unknown_asset"]\n```',
    '["reject","unknown_asset"] trailing text',
    '["reject","unknown_asset"] ["reject","unknown_asset"]',
    '["clarify","missing_asset","priority"]',
    '["plan",[["read_metric","P3",{"metric":"temperature","guard":false},false]],null]',
    '["plan",[["read_metric","P3",{"metric":"temperature"},0]],null]',
])
def test_parser_never_repairs_or_salvages(raw):
    with pytest.raises(ValueError):parse(raw)


def test_unknown_asset_not_implicitly_admitted():
    with pytest.raises(ValueError):parse(encode(conditional()),['P4'])


def test_counterfactual_and_exact_scoring_catches_lucky_false_branch():
    case=dict(gold=conditional(),catalog=['P3'])
    wrong=conditional('ge')
    assert not score(case,wrong)['correct']
    assert not score(case,wrong)['behavioral_match']
    assert len(counterfactuals(['P3'],conditional()))==4
    assert score(case,conditional())['correct']


def test_pilot_targets_roundtrip_for_all_baseline_representations():
    data=pilot()
    for split,rows in data.items():
        for row in rows:
            assert parse(encode(row['gold']),row['catalog'])==row['gold']
            assert unflatten(flatten(row['gold'],row['catalog']),row['catalog'])==row['gold']
            assert score(row,row['gold'])['correct']
            assert set(public_input(row))=={'request','context','catalog'}
    info=manifest(data)
    assert info['counts']=={'train':720,'tuning':120,'audit':120}
    assert not any(info['cross_split_exact_input_overlap'].values())
    assert info['development_only'] and not info['human_reviewed']
    assert pilot()==data


def test_model_inputs_do_not_change_when_gold_or_id_changes():
    case=make_case('audit','conditional',0)
    changed=copy.deepcopy(case)
    changed['gold']=terminal('reject','unsupported_operation')
    changed['id']='different';changed['stratum']='direct'
    assert public_input(case)==public_input(changed)
    assert prompt(case)==prompt(changed)
    assert rules(public_input(case))==rules(public_input(changed))


@pytest.mark.parametrize('category',STRATA)
def test_each_pilot_stratum_exercises_valid_simulator_paths(category):
    for i in range(24):
        row=make_case('tuning',category,i)
        assert score(row,row['gold'])['correct']


def test_output_codec_is_reversible_without_hidden_references():
    ast=conditional('le',90)
    assert parse(encode(ast))==ast
    assert 'draft_report' in encode(ast)
    assert json.loads(encode(ast))[2]==[0,'le',90]
