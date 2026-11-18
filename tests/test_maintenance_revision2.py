import copy
import json
from sysone.v2.maintenance.revision2 import corpus,mention_order,demonstrations,calibration_subset,prompt,CONTEXT,OUTPUT
from sysone.v2.maintenance.dataset import public_input,score
from sysone.v2.maintenance.schema import encode,parse,canonical
from sysone.v2.maintenance.baselines import flatten,unflatten


def test_mention_order_does_not_select_or_drop_catalog_candidates():
    public=dict(request='Use P4 instead.',context={'previous_request':'Read P3 temperature.'},catalog=['P3','P4','M1'])
    assert mention_order(public)==['P4','P3','M1']
    assert public['catalog']==['P3','P4','M1']
    public['request']='Read P99 temperature.'
    assert 'P99' not in mention_order(public)


def test_fresh_corpus_and_semantic_targets_are_consistent():
    data=corpus()
    for split,rows in data.items():
        assert len(rows)==(720 if split=='train' else 120)
        for row in rows:
            assert parse(encode(row['gold']),row['catalog'])==row['gold']
            assert unflatten(flatten(row['gold'],row['catalog']),row['catalog'])==row['gold']
            assert score(row,row['gold'])['correct']
            assert len(row['catalog'])==len(set(row['catalog']))==12
    sig=lambda r:json.dumps(public_input(r),sort_keys=True)
    for a,b in (('train','tuning'),('train','audit'),('tuning','audit')):
        assert not {sig(c) for c in data[a]} & {sig(c) for c in data[b]}


def test_examples_are_training_only_and_gold_is_not_in_query():
    data=corpus();demos=demonstrations(data['train'])
    assert len(demos)==4 and all(c['split']=='train' for c in demos)
    case=data['audit'][0];changed=copy.deepcopy(case)
    changed['gold']={'outcome':'reject','reason':'unknown_asset'}
    assert prompt(case,demos)==prompt(changed,demos)
    assert len(calibration_subset(data['tuning']))==24
    assert CONTEXT==1024 and OUTPUT==256
