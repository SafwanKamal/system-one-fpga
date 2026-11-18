"""Clean-data successor experiment; development selection, no BFCL selection.

All previous sealed pilots remain unchanged. Runs host CPU references only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import torch
from torch import nn
from transformers import AutoTokenizer, AutoModelForCausalLM

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_training_v2 import partition_records, prepare_jobs, encoder_text, source_tokens, exact_calls
from sysone.v2.general_tool_encoder import ToolEncoder, KINDS, scalar_from_span
from sysone.v2.general_tools import normalize_tool, validate_calls, parse_functiongemma
from sysone.v2.command_task import percentile
from sysone.v2.command_metrics import process_memory
from sysone.v2.checkpoint_io import write_checkpoint


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--family',choices=['encoder','functiongemma'],required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--train-records',type=int,default=512)
    ap.add_argument('--epochs',type=int,default=2)
    ap.add_argument('--threads',type=int,default=4)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads);torch.manual_seed(2026101702)
    encoder=args.family=='encoder'
    cap=256 if encoder else 2048
    manifest=dict(stage='starting',family=args.family,seed=2026101702,
        arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        execution='host_CPU_only_no_tool_execution',bfcl_used_for_selection=False,blind_test=False,
        profile=dict(tools=8,calls_total=4,calls_per_tool=4,encoder_pass_tokens=256,generator_context=2048,generator_output=256),
        policy=dict(trainable_final_blocks=2,encoder_backbone_lr=1e-5,encoder_new_head_lr=1e-3,generator_lr=5e-6,
            selection='strictly higher complete dev correct, no fewer correct accepted, no worse observed accepted error; ties retain earlier model',
            selection_original_records=16,audit_original_records=64,augmentation='training-only explicit-deny families; different dev/audit wording'),
        data_sha256={name:digest(args.data/name) for name in ['train.jsonl','dev.jsonl','manifest.json']})
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/name for name in ['general_training_v2.py','general_tool_encoder.py','general_tools.py']]
    (args.out/'sources').mkdir()
    manifest['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sources}
    for p in sources:(args.out/'sources'/p.name).write_bytes(p.read_bytes())
    dump(args.out/'run.json',manifest)
    train,selection,audit=partition_records(args.data,args.train_records)
    for name,rows in [('training',train),('selection',selection),('audit',audit)]:
        dump(args.out/f'{name}-cases.json',rows)
    started=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    model=ToolEncoder(args.model,max_calls_per_tool=4) if encoder else AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,dtype=torch.float32)
    if encoder:
        model.encoder.requires_grad_(False)
        for block in model.encoder.encoder.layer[-2:]:block.requires_grad_(True)
        backbone=[p for n,p in model.named_parameters() if p.requires_grad and n.startswith('encoder.')]
        heads=[p for n,p in model.named_parameters() if p.requires_grad and not n.startswith('encoder.')]
        optimizer=torch.optim.AdamW([dict(params=backbone,lr=1e-5),dict(params=heads,lr=1e-3)])
    else:
        model.requires_grad_(False)
        for block in model.model.layers[-2:]:block.requires_grad_(True)
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-6)
    trainable={n for n,p in model.named_parameters() if p.requires_grad}
    manifest.update(load_seconds=time.perf_counter()-started,parameters=sum(p.numel() for p in model.parameters()),
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),memory_after_load=process_memory())
    def save(name,tag):
        state={n:v for n,v in model.state_dict().items() if n in trainable}
        write_checkpoint(dict(trainable_state=state,manifest=manifest,tag=tag),args.out/name,torch.save)
    def restore(name):
        checkpoint=torch.load(args.out/name,map_location='cpu',weights_only=False)
        result=model.load_state_dict(checkpoint['trainable_state'],strict=False)
        if result.unexpected_keys or set(checkpoint['trainable_state'])!=trainable:
            raise ValueError('trainable checkpoint mismatch')
    if encoder:
        jobs,failures,kinds=prepare_jobs(train,tok,cap)
        dump(args.out/'preparation.json',dict(jobs=len(jobs),failures=failures,argument_kinds=kinds))
        dump(args.out/'training-jobs.json',jobs)
    def template(row,training=False):
        messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=row['query'])]
        tools=[dict(type='function',function=normalize_tool(t)) for t in row['tools']]
        p=tok.apply_chat_template(messages,tools=tools,add_generation_prompt=True,tokenize=False)
        if not training:return tok.encode(p,add_special_tokens=False)
        response=dict(role='assistant',tool_calls=[dict(type='function',function=a) for a in row['answers']]) if row['answers'] else dict(role='assistant',content='No suitable function.')
        full=tok.apply_chat_template(messages+[response],tools=tools,tokenize=False)
        if not full.startswith(p):raise ValueError('template prefix mismatch')
        return tok.encode(p,add_special_tokens=False),tok.encode(full[len(p):],add_special_tokens=False)
    stops=[] if encoder else list(dict.fromkeys(list(model.config.eos_token_id)+[tok.convert_tokens_to_ids(t) for t in ['<end_of_turn>','<start_function_response>']]))
    def infer(row):
        if len(row['tools'])>8:raise ValueError('tool-count profile')
        if not encoder:
            p=template(row)
            if len(p)+256>cap:raise ValueError('prompt/output context profile')
            with torch.inference_mode():
                output=model.model(input_ids=torch.tensor([p]),use_cache=True)
                cache=output.past_key_values
                token=int(model.lm_head(output.last_hidden_state[:,-1,:]).argmax(-1)[0]);emitted=[token]
                first=time.perf_counter_ns()
                while token not in stops and len(emitted)<256:
                    output=model.model(input_ids=torch.tensor([[token]]),past_key_values=cache,use_cache=True)
                    cache=output.past_key_values
                    token=int(model.lm_head(output.last_hidden_state[:,-1,:]).argmax(-1)[0]);emitted.append(token)
            raw=tok.decode(emitted,skip_special_tokens=False).strip()
            if token not in stops:raise ValueError('output work cap exhausted')
            return parse_functiongemma(raw,row['tools']),dict(raw_output=raw,prompt_tokens=len(p),output_tokens=len(emitted),first_token_ns=first)
        calls=[];passes=0
        def predict(tool,key=None,slot=0):
            nonlocal passes
            question,lower=encoder_text(tool,key,slot)
            enc=tok(question,row['query'],truncation=False,return_offsets_mapping=True)
            if len(enc['input_ids'])>cap:raise ValueError('encoder input profile')
            with torch.inference_mode():outputs=model({k:torch.tensor([v]) for k,v in enc.items() if k!='offset_mapping'})
            passes+=1
            return enc,outputs,question,lower
        for raw_tool in row['tools']:
            tool=normalize_tool(raw_tool)
            _,(counts,_,_),_,_=predict(tool)
            count=int(counts.argmax(-1)[0])
            if count==5:raise ValueError('call-count overflow')
            for slot in range(count):
                if len(calls)>=4:raise ValueError('total-call profile')
                arguments={}
                for key,spec in tool['parameters']['properties'].items():
                    enc,(_,kinds,spans),question,lower=predict(tool,key,slot)
                    kind=KINDS[int(kinds.argmax(-1)[0])]
                    if kind in ('omit','unrepresentable'):
                        if kind=='unrepresentable' or key in tool['parameters'].get('required',[]):
                            raise ValueError('missing or unrepresentable argument')
                        continue
                    if kind=='span':
                        valid=source_tokens(enc,lower)
                        if not valid:raise ValueError('no eligible value tokens')
                        a=max(valid,key=lambda i:float(spans[0,i,0]))
                        seq=enc.sequence_ids()[a]
                        ends=[i for i in valid if a<=i<a+64 and enc.sequence_ids()[i]==seq]
                        b=max(ends,key=lambda i:float(spans[0,i,1]))
                        text=row['query'] if seq==1 else question
                        arguments[key]=scalar_from_span(text[enc['offset_mapping'][a][0]:enc['offset_mapping'][b][1]],spec)
                    else:arguments[key]={'true':True,'false':False,'null':None,'empty_string':'','empty_array':[],'empty_object':{}}[kind]
                calls.append(dict(name=tool['name'],arguments=arguments))
        validate_calls(calls,row['tools'])
        return calls,dict(encoder_passes=passes)
    def evaluate(rows,name):
        model.eval();predictions=[]
        with (args.out/f'{name}-requests.jsonl').open('w',encoding='utf-8') as stream:
            for row in rows:
                result=dict(id=row['id'],correct=False,valid=False,calls=[],gold_valid=True)
                start=time.perf_counter_ns()
                try:
                    validate_calls(row['answers'],row['tools'])
                except Exception as exc:result.update(gold_valid=False,gold_error=str(exc))
                try:
                    calls,extra=infer(row)
                    result.update(calls=calls,valid=True,**extra)
                    result['inference_ms']=(time.perf_counter_ns()-start)/1e6
                    result['correct']=result['gold_valid'] and exact_calls(calls,row['answers'],row['tools'])
                except Exception as exc:
                    result.update(error=type(exc).__name__+': '+str(exc),inference_ms=(time.perf_counter_ns()-start)/1e6)
                result['accepted']=result['valid'] and bool(result['calls'])
                predictions.append(result);stream.write(json.dumps(result)+'\n');stream.flush()
        accepted=[r for r in predictions if r['accepted']]
        summary=dict(requests=len(rows),correct=sum(r['correct'] for r in predictions),
            correct_accepted=sum(r['correct'] for r in accepted),accepted=len(accepted),wrong_accepted=sum(not r['correct'] for r in accepted),
            valid=sum(r['valid'] for r in predictions),gold_errors=sum(not r['gold_valid'] for r in predictions),
            accuracy=sum(r['correct'] for r in predictions)/len(rows),accepted_error=sum(not r['correct'] for r in accepted)/len(accepted) if accepted else None,
            latency_ms={f'p{q}':percentile([r['inference_ms'] for r in predictions],q/100) for q in [50,95,99]},
            criterion='schema-validated complete call multiset, typed JSON arguments; numeric int/float normalized only for number schemas',
            execution='host_CPU_only',blind=False)
        dump(args.out/f'{name}-summary.json',summary)
        print(json.dumps(dict(evaluation=name,**summary)),flush=True)
        return summary
    best=evaluate(selection,'selection-baseline');best_tag='official_initialization'
    save('best.pt',best_tag)
    dump(args.out/'selection-history.json',[dict(tag=best_tag,result=best)])
    history=[dict(tag=best_tag,result=best)]
    rng=random.Random(2026101702);steps=0;train_start=time.perf_counter()
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as stream:
        for epoch in range(args.epochs):
            model.train()
            if encoder:
                ordered=sorted(jobs,key=lambda j:len(j['tokens']['input_ids']))
                batches=[ordered[i:i+8] for i in range(0,len(ordered),8)];rng.shuffle(batches)
            else:
                batches=list(train);rng.shuffle(batches)
            for batch in batches:
                record=dict(epoch=epoch,step=steps+1)
                optimizer.zero_grad(set_to_none=True)
                if encoder:
                    tokens=tok.pad([j['tokens'] for j in batch],padding=True,return_tensors='pt')
                    count,kind,span=model(tokens);losses=[]
                    for i,j in enumerate(batch):
                        if j['task']=='count':losses.append(nn.functional.cross_entropy(count[i:i+1],torch.tensor([j['count']])))
                        else:
                            loss=nn.functional.cross_entropy(kind[i:i+1],torch.tensor([j['kind']]))
                            if KINDS[j['kind']]=='span':loss+=(nn.functional.cross_entropy(span[i:i+1,:,0],torch.tensor([j['start']]))+nn.functional.cross_entropy(span[i:i+1,:,1],torch.tensor([j['end']])))/2
                            losses.append(loss)
                    loss=torch.stack(losses).mean()
                    record['ids']=[j['id'] for j in batch]
                else:
                    record['id']=batch['id']
                    try:
                        validate_calls(batch['answers'],batch['tools'])
                        p,c=template(batch,True)
                        if len(batch['tools'])>8 or len(p)+len(c)>cap or len(c)>256:raise ValueError('training profile')
                        hidden=model.model(input_ids=torch.tensor([p+c]),use_cache=False).last_hidden_state
                        logits=model.lm_head(hidden[:,len(p)-1:len(p)+len(c)-1,:])
                        loss=nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),torch.tensor(c))
                    except (ValueError,TypeError,KeyError) as exc:
                        record['profile_or_gold_error']=str(exc);stream.write(json.dumps(record)+'\n');stream.flush();continue
                loss.backward();nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.0);optimizer.step();steps+=1
                record.update(step=steps,loss=loss.item(),elapsed_seconds=time.perf_counter()-train_start)
                stream.write(json.dumps(record)+'\n');stream.flush()
                if steps%32==0:
                    print(json.dumps({k:v for k,v in record.items() if k!='ids'}),flush=True)
                if steps%128==0:save('latest.pt',f'epoch{epoch+1}-step{steps}')
            save(f'epoch-{epoch+1}.pt',f'epoch{epoch+1}')
            current=evaluate(selection,f'selection-epoch-{epoch+1}')
            acceptable=(current['accepted_error'] is None or best['accepted_error'] is None or current['accepted_error']<=best['accepted_error'])
            promote=current['correct']>best['correct'] and current['correct_accepted']>=best['correct_accepted'] and acceptable
            history.append(dict(tag=f'epoch{epoch+1}',result=current,promoted=promote))
            if promote:
                best=current;best_tag=f'epoch{epoch+1}';save('best.pt',best_tag)
            dump(args.out/'selection-history.json',history)
            manifest.update(stage='training',completed_epochs=epoch+1,updates=steps,best=best_tag)
            dump(args.out/'run.json',manifest)
    save('last.pt','last')
    manifest.update(training_and_selection_seconds=time.perf_counter()-train_start,updates=steps,best=best_tag)
    restore('best.pt')
    audit_result=evaluate(audit,'audit-best')
    manifest.update(stage='complete',best_checkpoint_sha256=digest(args.out/'best.pt'),
        audit=audit_result,memory_at_end=process_memory(),board_contacted=False,paid_compute=False)
    dump(args.out/'run.json',manifest)


if __name__=='__main__':
    main()
