"""Independently replay probability-output maintenance artifacts and provenance."""
import argparse
import hashlib
import gc
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import torch

from maintenance_decisions import (ROOT,WORK,PARENT,OLD,read_rows,sha,dump,check_seal,
    flatten,unflatten,public_input,encode,verdict,CandidateHead,padded,features,MODELS,probability_models)


def independent_active(v):
    active=['outcome']
    if v['outcome']!='plan':
        return active+['reason']+(['field'] if v['outcome']=='clarify' else [])
    active+=['asset','length','pred_source']
    if v['pred_source']!='_':active+=['pred_op','pred_rhs']
    args={'read_metric':['metric'],'read_history':['metric','count'],'list_alarms':[],
        'read_status':[],'read_metadata':['field'],'lookup_procedure':['topic'],
        'draft_report':['priority','evidence'],'request_inspection':['priority','evidence']}
    try:length=int(v['length'])
    except ValueError:return active
    for i in range(min(length,3)):
        active.extend([f'{i}.tool',f'{i}.guard'])
        try:tool=json.loads(v[f'{i}.tool'])
        except ValueError:continue
        active.extend(f'{i}.{k}' for k in args.get(tool,[]))
    return active


def softmax(z,t):
    z=np.array(z,dtype=np.float64)/t
    e=np.exp(z-z.max())
    return e/e.sum()


def verify_plan_metrics(rows,saved,reported):
    for label,key in ((None,None),('valid_only','valid'),('accepted_plans_only','accepted')):
        indices=[i for i,r in enumerate(rows) if key is None or r[key]]
        target=reported if label is None else reported[label]
        if key is not None:assert target['count']==len(indices)
        if not indices:
            assert all(target[k] is None for k in ('brier','ece','nll'))
            continue
        p=np.array([saved[i]['plan_correct_probability'] for i in indices])
        y=np.array([rows[i]['correct'] for i in indices],dtype=float)
        assert abs(float(np.mean((p-y)**2))-target['brier'])<1e-10
        likelihood=np.where(y==1,p,1-p)
        assert abs(float(-np.log(np.maximum(likelihood,1e-30)).mean())-target['nll'])<1e-10
        bin_index=np.minimum((p*10).astype(int),9)
        error=sum(abs(float((p[bin_index==i]-y[bin_index==i]).sum()))/len(p) for i in range(10))
        assert abs(error-target['ece'])<1e-10


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=WORK)
    work=ap.parse_args().work
    protocol=json.loads((work/'protocol.json').read_text())
    assert check_seal(PARENT)==protocol['parent']
    assert check_seal(OLD)==protocol['older_parent']
    original_sources=json.loads((PARENT/'protocol.json').read_text())['source_sha256']
    for rel,digest in original_sources.items():
        if rel!='scripts/v2/maintenance_sft.py':assert sha(ROOT/rel)==digest,rel
    for split,digest in protocol['data_sha256'].items():assert sha(work/(split+'.jsonl'))==digest
    assert sha(work/'classes.json')==protocol['classes_sha256']
    classes=json.loads((work/'classes.json').read_text())
    train=read_rows(work/'train.jsonl')
    expected={k:sorted({flatten(c['gold'],c['catalog'])[k] for c in train}) for k in classes}
    assert expected==classes
    keys={split:{json.dumps(public_input(c),sort_keys=True) for c in read_rows(work/(split+'.jsonl'))}
        for split in protocol['data_sha256']}
    for split in keys:
        if split!='calibration':assert not keys[split]&keys['calibration']
    invoked={}
    for entry in (work/'invocations').glob('*.json'):
        meta=json.loads(entry.read_text())
        assert sha(entry.with_suffix('.py'))==meta['source_sha256']
        assert sha(work/'protocol.json')==meta['protocol_sha256']
        invoked.setdefault(meta['phase'],set()).add(meta['source_sha256'])
    assert sha(work/'test-source.py')==sha(ROOT/'tests/test_maintenance_decisions.py')
    comparison=json.loads((work/'comparison.json').read_text());rows_verified=0;fields_verified=0
    for name in probability_models(work):
        for split in ('calibration','fresh','conditional'):
            rows=read_rows(work/name/(split+'-predictions.jsonl'));cases=read_rows(work/(split+'.jsonl'))
            assert [r['id'] for r in rows]==[c['id'] for c in cases]
            for row,case in zip(rows,cases):
                values={}
                assert set(row['field_logits'])==set(classes)
                for k,vs in classes.items():
                    z=np.asarray(row['field_logits'][k],dtype=float)
                    assert z.shape==(len(vs),) and np.isfinite(z).all()
                    values[k]=vs[int(z.argmax())]
                    p=softmax(z,1);assert abs(p.sum()-1)<1e-12
                    fields_verified+=1
                assert values==row['predicted_fields']
                try:raw=encode(unflatten(values,case['catalog']))
                except (ValueError,TypeError,KeyError,IndexError):raw=json.dumps(values)
                assert raw==row['raw_output']
                replay=verdict(case,raw,0)
                assert all(replay[k]==row[k] for k in ('valid','correct','accepted'))
                if name.startswith('laya'):assert row['input_tokens_max']<=1024 and row['native_choice_logits']
                rows_verified+=1
            if split=='calibration':continue
            params=json.loads((work/name/'calibration.json').read_text())
            t=params['temperature'];assert t>0
            assert params['calibration_records']==120 and params['calibration_sha256']==sha(work/'calibration.jsonl')
            nll=[];brier=[]
            for row,case in zip(rows,cases):
                gold=flatten(case['gold'],case['catalog'])
                for k in independent_active(gold):
                    if len(classes[k])==1:continue
                    p=softmax(row['field_logits'][k],t);i=classes[k].index(gold[k])
                    nll.append(-math.log(max(p[i],1e-30)))
                    target=np.zeros(len(p));target[i]=1;brier.append(float(((p-target)**2).sum()))
            reported=comparison[name]['splits'][split]
            assert reported['correct']==sum(r['correct'] for r in rows)
            scaled=reported['field_calibration']['temperature_scaled']
            assert abs(np.mean(nll)-scaled['nll'])<1e-10
            assert abs(np.mean(brier)-scaled['brier'])<1e-10
            calibrated=read_rows(work/name/(split+'-calibrated.jsonl'))
            assert len(calibrated)==len(rows)
            for row,saved in zip(rows,calibrated):
                assert row['id']==saved['id']
                for k,vs in classes.items():
                    actual=np.array([saved['field_probabilities'][k][v] for v in vs])
                    assert np.allclose(actual,softmax(row['field_logits'][k],t),atol=1e-12,rtol=0)
                if row['valid']:
                    score=min(softmax(row['field_logits'][k],t).max() for k in independent_active(row['predicted_fields']))
                    score=np.clip(score,1e-6,1-1e-6)
                    z=params['plan_calibration_slope']*np.log(score/(1-score))+params['plan_calibration_intercept']
                    p=1/(1+np.exp(-np.clip(z,-50,50)))
                else:p=0.
                assert abs(p-saved['plan_correct_probability'])<1e-10
            verify_plan_metrics(rows,calibrated,reported['plan_calibration'])
            for _,risk in reported['risk_coverage'].items():
                chosen=[r for r,p in zip(rows,calibrated) if r['valid'] and p['plan_correct_probability']>=risk['threshold']]
                assert risk['selected']==len(chosen)
                assert risk['wrong']==sum(not r['correct'] for r in chosen)
            if name in ('tfidf','minilm'):
                old=read_rows(PARENT/name/(split+'-predictions.jsonl'))
                assert [r['raw_output'] for r in rows]==[r['raw_output'] for r in old]
    generator_rows=0
    from maintenance_sft import serialize,unwrap,load
    for name in ('qwen','functiongemma'):
        folder=work/(name+'-generative')
        params=json.loads((folder/'calibration.json').read_text())
        meta=json.loads((folder/'model.json').read_text())
        assert params['calibration_records']==120 and params['calibration_sha256']==sha(work/'calibration.jsonl')
        assert meta['checkpoint_sha256']==sha(PARENT/name/'checkpoint.pt')
        tok_gen=__import__('transformers').AutoTokenizer.from_pretrained(str(MODELS[name]),local_files_only=True)
        for split in ('calibration','fresh','conditional'):
            rows=read_rows(folder/(split+'-predictions.jsonl'));cases=read_rows(work/(split+'.jsonl'))
            assert [r['id'] for r in rows]==[c['id'] for c in cases]
            for row,case in zip(rows,cases):
                assert serialize(tok_gen,name,case)['prompt_ids']==row['actual_prompt_ids']
                assert len(row['actual_prompt_ids'])+len(row['generated_ids'])<=1024
                assert tok_gen.decode(row['generated_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False)==row['native_output']
                try:raw=unwrap(name,row['native_output'])
                except ValueError:raw=''
                assert raw==row['raw_output']
                v=verdict(case,raw,0);assert all(v[k]==row[k] for k in ('correct','valid','accepted'))
                lp=np.array(row['selected_token_log_probabilities'])
                assert len(lp)==len(row['generated_ids']) and np.isfinite(lp).all() and np.all(lp<=1e-5)
                assert abs(row['token_min_probability']-(math.exp(float(lp.min())) if len(lp) else 0.))<1e-12
                generator_rows+=1
            if split!='calibration':
                archived=read_rows(PARENT/name/(split+'-predictions.jsonl'))
                assert all(r['raw_output']==a['raw_output'] and r['generated_ids']==a['generated_ids'] for r,a in zip(rows,archived))
                probabilities=read_rows(folder/(split+'-calibrated.jsonl'))
                for row,saved_p in zip(rows,probabilities):
                    if row['valid']:
                        score=np.clip(row['token_min_probability'],1e-6,1-1e-6)
                        z=params['plan_calibration_slope']*np.log(score/(1-score))+params['plan_calibration_intercept']
                        p=1/(1+np.exp(-np.clip(z,-50,50)))
                    else:p=0.
                    assert abs(p-saved_p['plan_correct_probability'])<1e-10
                verify_plan_metrics(rows,probabilities,comparison[name+'-generative']['splits'][split]['plan_calibration'])
                risk=comparison[name+'-generative']['splits'][split]['risk_coverage']
                for values in risk.values():
                    chosen=[r for r,p in zip(rows,probabilities) if r['valid'] and p['plan_correct_probability']>=values['threshold']]
                    assert len(chosen)==values['selected'] and sum(not r['correct'] for r in chosen)==values['wrong']
    # Frozen feature inputs contain only public data and explicitly declared suffix.
    from transformers import AutoTokenizer,AutoModel
    tok=AutoTokenizer.from_pretrained(str(MODELS['qwen']),local_files_only=True)
    for split in protocol['data_sha256']:
        data=torch.load(work/'qwen-features'/(split+'.pt'),weights_only=True)
        cases=read_rows(work/(split+'.jsonl'))
        assert data['ids']==[c['id'] for c in cases]
        for case,ids,hidden in zip(cases,data['token_ids'],data['hidden']):
            text=features(public_input(case))+'\nRepresent the complete maintenance request, preserving comparisons, corrections and actions.'
            assert tok(text)['input_ids']==ids and len(ids)<=1024
            assert hidden.dtype==torch.float32 and hidden.shape[0]==len(ids)
    qmeta=json.loads((work/'qwen-decision/model.json').read_text())
    history=json.loads((work/'qwen-decision/history.json').read_text())
    best=max(history,key=lambda h:(h['tuning_correct'],-h['tuning_active_field_nll']))
    assert len(history)==80 and best['epoch']==qmeta['selected_epoch']
    assert qmeta['source_sha256'] in invoked['train']
    assert sha(work/'qwen-decision/checkpoint.pt')==qmeta['checkpoint_sha256']
    # Recompute selected head logits from saved public-only features, independent of verdicts.
    bank=torch.load(work/'qwen-features/choices.pt',weights_only=True)
    saved=torch.load(work/'qwen-decision/checkpoint.pt',weights_only=True)
    head=CandidateHead(saved['width'],bank['questions'],bank['candidates']).eval()
    head.load_state_dict(saved['state']);torch.set_num_threads(4)
    for split in ('fresh','conditional'):
        data=torch.load(work/'qwen-features'/(split+'.pt'),weights_only=True)
        rows=read_rows(work/'qwen-decision'/(split+'-predictions.jsonl'))
        with torch.no_grad():
            h,m=padded(data['hidden'],[0,1,2,3]);z=head(h,m).numpy()
        for row,logits in zip(rows,z):
            for i,k in enumerate(classes):assert np.allclose(logits[i,:len(classes[k])],row['field_logits'][k],atol=1e-5,rtol=1e-5)
    laya_name=probability_models(work)[-1]
    lmeta=json.loads((work/laya_name/'model.json').read_text())
    if (work/'laya-precision-amendment.json').exists():
        amendment=json.loads((work/'laya-precision-amendment.json').read_text())
        probe=json.loads((work/'laya-precision-probe.json').read_text())
        assert probe['passed'] and sha(work/'laya-precision-probe.json')==amendment['probe_sha256']
        assert sha(work/'laya-precision-probe-source.py')==probe['source_sha256']
    if laya_name=='laya-directml':
        selected=json.loads((work/'laya-runtime-selection.json').read_text())
        qualification=json.loads((work/'directml/qualification.json').read_text())
        assert qualification['passed'] and sha(work/'directml/qualification.json')==selected['qualification_sha256']
        assert lmeta['source_sha256'] in invoked['directml-evaluate']
        assert set(qualification['execution_provider_node_events'])=={'DmlExecutionProvider'}
        assert sha(Path(lmeta['graph_path']))==lmeta['graph_sha256']
        assert sha(work/'directml/laya-float32.onnx.data')==lmeta['weights_data_sha256']
    for rel,digest in lmeta['files_sha256'].items():assert sha(ROOT/'models/laya-typed-decisions'/rel)==digest
    for rel,digest in json.loads((work/'qwen-features/base.json').read_text())['files_sha256'].items():
        assert sha(MODELS['qwen']/rel)==digest
    base=AutoModel.from_pretrained(str(MODELS['qwen']),local_files_only=True,dtype=torch.float32,attn_implementation='sdpa').eval()
    cached=torch.load(work/'qwen-features/train.pt',weights_only=True);cache_errors=[]
    with torch.inference_mode():
        for index in (0,120,360):
            ids=torch.tensor([cached['token_ids'][index]])
            direct=base(input_ids=ids,use_cache=False).last_hidden_state[0]
            diff=direct-cached['hidden'][index]
            cache_errors.append(float(diff.abs().max()))
            assert float(diff.square().mean().sqrt()/direct.square().mean().sqrt())<1e-4
            assert torch.allclose(direct,cached['hidden'][index],atol=0.001,rtol=0.0001)
    # Check the adapted decoder-block subset and independently replay its chosen head.
    from types import SimpleNamespace
    from maintenance_sft import cached_tail
    ameta=json.loads((work/'qwen-decision-adapted/model.json').read_text())
    ahistory=json.loads((work/'qwen-decision-adapted/history.json').read_text())
    abest=max(ahistory,key=lambda h:(h['tuning_correct'],-h['tuning_active_field_nll']))
    assert len(ahistory)==6 and abest['epoch']==ameta['selected_epoch']
    assert ameta['source_sha256'] in invoked['train-adapted']
    assert ameta['initialization_head_sha256']==sha(work/'qwen-decision/checkpoint.pt')
    assert sha(work/'qwen-decision-adapted/checkpoint.pt')==ameta['checkpoint_sha256']
    adapted=torch.load(work/'qwen-decision-adapted/checkpoint.pt',weights_only=True)
    assert set(adapted['layers'])=={'26','27'}
    changed=sum(int(torch.count_nonzero(base.layers[int(i)].state_dict()[k]!=v)) for i,state in adapted['layers'].items() for k,v in state.items())
    assert changed>0
    wrapper=SimpleNamespace(model=base,config=base.config)
    prefix_errors=[]
    pref=torch.load(work/'qwen-prefix/train.pt',weights_only=True)
    with torch.inference_mode():
        for index in (0,120,360):
            replay=cached_tail(wrapper,pref['hidden'][index][None],26)[0]
            assert torch.allclose(replay,cached['hidden'][index],atol=.001,rtol=.0001)
            prefix_errors.append(float((replay-cached['hidden'][index]).abs().max()))
    for i,state in adapted['layers'].items():base.layers[int(i)].load_state_dict(state)
    ahead=CandidateHead(adapted['width'],bank['questions'],bank['candidates']).eval();ahead.load_state_dict(adapted['state'])
    with torch.inference_mode():
        for split in ('fresh','conditional'):
            prefix=torch.load(work/'qwen-prefix'/(split+'.pt'),weights_only=True)
            cases=read_rows(work/(split+'.jsonl'));assert prefix['ids']==[c['id'] for c in cases]
            rows=read_rows(work/'qwen-decision-adapted'/(split+'-predictions.jsonl'))
            h,m=padded(prefix['hidden'],[0,1,2,3]);z=ahead(cached_tail(wrapper,h,26),m).numpy()
            for row,logits in zip(rows,z):
                for i,k in enumerate(classes):assert np.allclose(logits[i,:len(classes[k])],row['field_logits'][k],atol=.001,rtol=.0001)
    del base,cached,pref,wrapper,adapted,head,ahead,prefix,h,m,z
    gc.collect()
    # Validate the raw-logit adapter against the public native API on one calibration
    # question. No semantic performance selection uses this check.
    import laya
    from maintenance_decisions import field_question,option_text
    agent=laya.load(str(ROOT/'models/laya-typed-decisions'),device='cpu',compile=False,fast=False)
    agent.model.float().eval();agent.amp_enabled=lmeta['precision'].startswith('bfloat16')
    agent.dtype=torch.bfloat16 if agent.amp_enabled else torch.float32
    agent.temperature_by_options={};agent.temperature=[1.,1.,1.]
    c=read_rows(work/'calibration.jsonl')[0]
    contract='Interpret a maintenance request as a plan of 1-3 steps, clarification, or rejection. A condition guards the requested action and additional history, not the initial sensor read. Evidence cites all earlier reads. A correction changes only the explicitly corrected asset, preserving the prior request. Unsupported operations: actuator control, Fahrenheit, history counts above 5, more than 3 steps. Clarify missing or ambiguous references and contradictory instructions.'
    native_questions={k:dict(type='choice',instructions=field_question(k),
        criteria={f'v{i}':option_text(k,v) for i,v in enumerate(vs)}) for k,vs in classes.items() if len(vs)>1}
    native=agent.system_one(contract+'\n'+features(public_input(c)),native_questions)
    answers=native.get('answers',native)
    archived=read_rows(work/laya_name/'calibration-predictions.jsonl')[0]
    for k,q in native_questions.items():
        p=softmax(archived['field_logits'][k],1)
        assert np.allclose([answers[k]['probabilities'][v] for v in q['criteria']],p,atol=.001 if laya_name=='laya-directml' else .0002,rtol=0)
    assert agent._amp_failures==0
    del agent
    gc.collect()
    from maintenance_decisions import selected_token_logps
    generator_probability_errors={}
    for name in ('qwen','functiongemma'):
        _,model=load(name,4)
        weights=torch.load(PARENT/name/'checkpoint.pt',weights_only=True)
        for i,state in weights['layers'].items():model.model.layers[int(i)].load_state_dict(state)
        errors=[]
        for split in ('calibration','fresh','conditional'):
            row=read_rows(work/(name+'-generative')/(split+'-predictions.jsonl'))[0]
            measured=selected_token_logps(model,row['actual_prompt_ids'],row['generated_ids'])
            assert np.allclose(measured,row['selected_token_log_probabilities'],atol=.001,rtol=.0001)
            errors.append(float(np.max(np.abs(np.array(measured)-row['selected_token_log_probabilities']))) if measured else 0.)
        generator_probability_errors[name]=errors
        del model,weights
        gc.collect()
    shutil.copyfile(__file__,work/'verification-source.py')
    dump(work/'verification.json',dict(rows_verified=rows_verified,field_distributions_verified=fields_verified,
        parents_unchanged=True,calibration_distinct=True,tuning_only_selection=True,raw_logits_replayed=True,
        metric_recomputations=True,frozen_feature_input_audit=True,selected_qwen_head_replayed=True,
        qwen_full_backbone_cache_errors=cache_errors,laya_native_api_parity=True,
        adapted_prefix_cache_errors=prefix_errors,adapted_parameters_changed=changed,
        generator_decisions_verified=generator_rows,generator_probability_spot_errors=generator_probability_errors,
        no_fpga_access=True,no_energy_measurement=True,source_sha256=sha(Path(__file__))))
    print(json.dumps(dict(rows_verified=rows_verified,generator_rows_verified=generator_rows,field_distributions_verified=fields_verified)),flush=True)
    # No subprocess may still be writing in this directory when this verifier is run.
    sealed={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file() and p.name!='final-seal.json'}
    dump(work/'final-seal.json',dict(files_sha256=sealed,excluded=None,parents_unchanged=True))


if __name__=='__main__':main()
