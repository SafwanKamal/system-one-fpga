"""Reproduce SFT provenance, raw-token verdicts, and selected weight changes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import torch
from safetensors import safe_open
from transformers import AutoTokenizer

from maintenance_sft import (ROOT, DEFAULT, MODELS, PARENT, check_seal, read_rows, sha, dump,
    serialize, unwrap, verdict, summary, load, cached_tail)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work',type=Path,default=DEFAULT)
    a=ap.parse_args(); work=a.work
    protocol=json.loads((work/'protocol.json').read_text())
    for source,digest in protocol['source_sha256'].items():
        if source!='scripts/v2/maintenance_sft.py':
            assert sha(ROOT/source)==digest, 'Shared schema/simulator/baseline source changed: '+source
    parent=check_seal(PARENT)
    original=check_seal(PARENT.parent/'maintenance-pilot-v1')
    shutil.copyfile(__file__,work/'verification-source.py')
    for split,digest in protocol['data_sha256'].items():
        assert sha(work/(split+'.jsonl'))==digest
    conditional=json.loads((work/'conditional-protocol.json').read_text())
    assert sha(work/'conditional.jsonl')==conditional['data_sha256']
    reference=json.loads((work/'pretrained-reference-ids.json').read_text())
    if (work/'precision-amendment.json').exists():
        amendment=json.loads((work/'precision-amendment.json').read_text())
        assert amendment['main_reference_precision']=='float32' and amendment['checkpoint_selection_unchanged']
    else:
        assert protocol['inference'].startswith('CPU float32 reference')
    expected=[]
    fresh=read_rows(work/'fresh.jsonl')
    for stratum in ('direct','composition','conditional','context_correction','clarification','unsupported'):
        seen=set()
        for case in fresh:
            if case['stratum']!=stratum: continue
            key=json.dumps({k:case[k] for k in ('request','context','catalog')},sort_keys=True)
            if key not in seen: expected.append(case['id']);seen.add(key)
            if len(seen)==4: break
    assert reference['ids']==expected and len(expected)==24
    invocations=list((work/'invocations').glob('*.json'))
    for path in invocations:
        entry=json.loads(path.read_text())
        assert sha(path.with_suffix('.py'))==entry['source_sha256']
        assert entry['protocol_sha256']==sha(work/'protocol.json')
    models={}; decisions=0
    for name in ('qwen','functiongemma'):
        out=work/name
        tok=AutoTokenizer.from_pretrained(str(MODELS[name]),local_files_only=True)
        for file,digest in json.loads((out/'model.json').read_text())['files_sha256'].items():
            assert sha(MODELS[name]/file)==digest
        diagnostic=json.loads((out/'precision-diagnostic.json').read_text())
        assert diagnostic['float32_completion_loss']<0.01
        assert abs(diagnostic['float32_completion_loss']-diagnostic['cached_completion_loss'])<0.0001
        assert diagnostic['float32_first_prompt_id']==diagnostic['expected_first_id']
        vocabulary_size=json.loads((MODELS[name]/'config.json').read_text())['vocab_size']
        for split in ('train','tuning'):
            jobs=read_rows(out/('training-jobs.jsonl' if split=='train' else 'tuning-jobs.jsonl'))
            cases=read_rows(work/(split+'.jsonl'))
            assert [j['id'] for j in jobs]==[c['id'] for c in cases]
            for case,job in zip(cases,jobs):
                assert serialize(tok,name,case,True)==job
                assert max(job['input_ids'])<vocabulary_size
        if name=='qwen':
            old=read_rows(PARENT/'sft-export/train.jsonl')
            assert all(x['input_ids']==y['input_ids'] for x,y in zip(read_rows(out/'training-jobs.jsonl'),old))
        history=json.loads((out/'training-history.json').read_text())
        assert len(history)==protocol['epochs']
        selected=min(history,key=lambda r:r['tuning_token_loss'])
        saved=torch.load(out/'checkpoint.pt',weights_only=True)
        assert saved['epoch']==selected['epoch']
        assert saved['tuning_loss']==selected['tuning_token_loss']
        selection=json.loads((out/'selection.json').read_text())
        assert selection['checkpoint_sha256']==sha(out/'checkpoint.pt')
        assert selection['audit_seen'] is False and selection['fresh_seen'] is False
        files=list(MODELS[name].glob('*.safetensors')); changed=0; parameters=0
        for file in files:
            with safe_open(file,framework='pt',device='cpu') as source:
                for i,state in saved['layers'].items():
                    for key,tensor in state.items():
                        fullkey=f'model.layers.{i}.{key}'
                        if fullkey not in source.keys(): continue
                        original_tensor=source.get_tensor(fullkey).float()
                        assert original_tensor.shape==tensor.shape
                        changed+=int(torch.count_nonzero(original_tensor!=tensor)); parameters+=tensor.numel()
        assert changed>0
        assert parameters==json.loads((out/'model.json').read_text())['trainable_parameters']
        # Real-model cache parity on a newly computed training record, beyond the resumed prefix files.
        _,base=load(name,4)
        jobs=read_rows(out/'training-jobs.jsonl'); errors=[]; numerical=[]
        original_tail={int(i):copy.deepcopy(base.model.layers[int(i)].state_dict()) for i in saved['layers']}
        with torch.no_grad():
            for index in (120,240,360):
                job=jobs[index]; ids=torch.tensor([job['input_ids'][:-1]])
                key=hashlib.sha256(ids.numpy().tobytes()).hexdigest()
                frozen=torch.load(out/'prefix-cache'/(key+'.pt'),weights_only=True)
                direct=base.model(ids,use_cache=False).last_hidden_state
                replay=cached_tail(base,frozen,saved['cut'])
                error=float((direct-replay).abs().max()); errors.append(error)
                print(json.dumps(dict(model=name,cache_parity_index=index,max_hidden_error=error,
                    mean_hidden_error=float((direct-replay).abs().mean()))),flush=True)
                # Split SDPA passes can accumulate float32 roundoff, especially in Gemma's
                # large normalized hidden coordinates. Also qualify the trained completion
                # distribution, rather than accepting a hidden-state tolerance alone.
                relative_rms=float((direct-replay).square().mean().sqrt()/direct.square().mean().sqrt())
                for i,state in saved['layers'].items(): base.model.layers[int(i)].load_state_dict(state)
                trained_direct=base.model(ids,use_cache=False).last_hidden_state
                trained_replay=cached_tail(base,frozen,saved['cut'])
                start=job['prompt_tokens']-1
                def logits(hidden):
                    z=base.lm_head(hidden[:,start:,:])
                    cap=getattr(base.config,'final_logit_softcapping',None)
                    return torch.tanh(z/cap)*cap if cap else z
                ld=logits(trained_direct); lr=logits(trained_replay)
                target=torch.tensor(job['target_ids'])
                loss_difference=float(abs(torch.nn.functional.cross_entropy(ld[0],target)-torch.nn.functional.cross_entropy(lr[0],target)))
                agreement=bool(torch.equal(ld.argmax(-1),lr.argmax(-1)))
                logit_error=float((ld-lr).abs().max())
                numerical.append(dict(training_index=index,relative_hidden_rms=relative_rms,
                    trained_completion_loss_difference=loss_difference,
                    trained_completion_top1_identical=agreement,max_completion_logit_error=logit_error))
                print(json.dumps(dict(model=name,**numerical[-1])),flush=True)
                assert error<0.01 and relative_rms<0.00001
                assert loss_difference<0.0001 and agreement and logit_error<0.01
                for i,state in original_tail.items(): base.model.layers[i].load_state_dict(state)
        del base
        model_result=dict(parameters_updated=changed,trainable_parameters=parameters,selected_epoch=saved['epoch'],
            real_cache_max_absolute_errors=errors,real_cache_completion_qualification=numerical,splits={})
        for variant in (name,name+'-pretrained'):
            if not (work/variant).exists(): continue
            for split in ('audit','fresh','conditional'):
                path=work/variant/(split+'-predictions.jsonl')
                if not path.exists(): continue
                assert json.loads((work/variant/(split+'-summary.json')).read_text())['inference_precision']=='float32 CPU'
                cases=read_rows(work/(split+'.jsonl')); rows=read_rows(path)
                if variant.endswith('-pretrained'):
                    chosen=set(json.loads((work/'pretrained-reference-ids.json').read_text())['ids'])
                    cases=[c for c in cases if c['id'] in chosen]
                assert [r['id'] for r in rows]==[c['id'] for c in cases]
                for case,row in zip(cases,rows):
                    job=serialize(tok,name,case)
                    assert row['actual_prompt_ids']==job['prompt_ids']
                    assert row['total_reserved']==len(job['prompt_ids'])+256<=1024
                    assert len(row['generated_ids'])<=256
                    assert tok.decode(row['generated_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False)==row['native_output']
                    try: payload=unwrap(name,row['native_output'])
                    except ValueError: payload=''
                    assert payload==row['raw_output']
                    replay=verdict(case,payload,0)
                    assert all(replay[k]==row[k] for k in ('valid','correct','accepted'))
                    decisions+=1
                model_result['splits'][variant+'/'+split]=summary(rows)
        models[name]=model_result
    expected_decisions=2*(sum(len(read_rows(work/(split+'.jsonl'))) for split in ('audit','fresh','conditional'))+len(reference['ids']))
    assert decisions==expected_decisions, 'Required generator decisions missing'
    result=dict(parent=parent,original_pilot=original,verified_decisions=decisions,invocations_verified=len(invocations),models=models,
        verification_source_sha256=sha(Path(__file__)),
        data_files_verified=5,tuning_only_selection=True,board_access=False,energy_measured=False)
    dump(work/'verification.json',result)
    print(json.dumps(dict(verified_decisions=decisions,selected={k:v['selected_epoch'] for k,v in models.items()})),flush=True)


if __name__=='__main__': main()
