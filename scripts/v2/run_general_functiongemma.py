"""General tool-calling CPU reference, with full dense vocabulary projection.

Fine-tunes only the final decoder layer on a recorded xLAM subset. No API calls
are executed. Every selected BFCL request is journaled, including profile failures.
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
from transformers import AutoModelForCausalLM,AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_tools import normalize_tool,parse_functiongemma,canonical_outcome
from sysone.v2.general_tool_eval import BFCLPythonChecker,read_jsonl,select_cases,checker_self_check
from sysone.v2.command_task import percentile
from sysone.v2.command_metrics import process_memory
from sysone.v2.checkpoint_io import write_checkpoint

TRIGGER='You are a model that can do function calling with the following functions'


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--train-records',type=int,default=128)
    ap.add_argument('--per-category',type=int,default=5)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--context-cap',type=int,default=2048)
    ap.add_argument('--output-cap',type=int,default=256)
    ap.add_argument('--checkpoint',type=Path)
    ap.add_argument('--dynamic-int8',action='store_true')
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(20261017)
    manifest=dict(stage='starting',execution='host_CPU_only_no_tool_execution',blind_test=False,
        arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        seed=20261017,training_policy='last decoder layer only; full dense output projection, no diagnostic-label vocabulary mask',
        energy_joules=None,hard_deadline_claim=False,
        data_sha256={name:hashlib.sha256((args.data/name).read_bytes()).hexdigest()
                     for name in ('train.jsonl','external-evaluation.jsonl','manifest.json')})
    sources=[Path(__file__),ROOT/'src/sysone/v2/general_tools.py',ROOT/'src/sysone/v2/general_tool_eval.py']
    (args.out/'sources').mkdir()
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    for p in sources:
        (args.out/'sources'/p.name).write_bytes(p.read_bytes())
    dump(args.out/'run.json',manifest)
    start=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,dtype=torch.float32)
    model.requires_grad_(False)
    model.model.layers[-1].requires_grad_(True)
    if args.checkpoint:
        saved=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
        model.model.layers[-1].load_state_dict(saved['last_layer'],strict=True)
        manifest.update(parent_checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                        parent_training_manifest=saved['manifest'])
    manifest.update(load_seconds=time.perf_counter()-start,memory_after_load=process_memory(),
        parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))
    def messages(row):
        return [dict(role='developer',content=TRIGGER),dict(role='user',content=row['query'])]
    def tools(row):
        return [dict(type='function',function=normalize_tool(t)) for t in row['tools']]
    def template(row,training=False):
        m=messages(row)
        prompt=tok.apply_chat_template(m,tools=tools(row),add_generation_prompt=True,tokenize=False)
        if not training:
            return prompt
        calls=[dict(type='function',function=a) for a in row['answers']]
        response=dict(role='assistant',tool_calls=calls) if calls else dict(role='assistant',content='No suitable function.')
        full=tok.apply_chat_template(m+[response],tools=tools(row),tokenize=False)
        if not full.startswith(prompt):
            raise ValueError('training template differs from inference prefix')
        return prompt,full[len(prompt):]
    def ids(text):
        return tok.encode(text,add_special_tokens=False)
    train=read_jsonl(args.data/'train.jsonl')
    random.Random(20261017).shuffle(train)
    train=train[:args.train_records]
    if args.checkpoint:
        train=[]
    dump(args.out/'selected-training.json',dict(ids=[r['id'] for r in train]))
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-5)
    start=time.perf_counter()
    updates=0
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as journal:
        for step,row in enumerate(train,1):
            entry=dict(step=step,id=row['id'])
            p,c=template(row,True)
            p,c=ids(p),ids(c)
            entry.update(prompt_tokens=len(p),completion_tokens=len(c))
            if len(p)+len(c)>args.context_cap or len(c)>args.output_cap:
                entry['profile_failure']='training sequence exceeds cap; preserved, not truncated'
            else:
                model.train()
                opt.zero_grad(set_to_none=True)
                hidden=model.model(input_ids=torch.tensor([p+c]),use_cache=False).last_hidden_state
                # Project only supervised positions, but ALL vocabulary rows.
                logits=model.lm_head(hidden[:,len(p)-1:len(p)+len(c)-1,:])
                loss=torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),torch.tensor(c))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.model.layers[-1].parameters(),1.0)
                opt.step()
                updates+=1
                entry['loss']=loss.item()
            entry['elapsed_seconds']=time.perf_counter()-start
            journal.write(json.dumps(entry)+'\n');journal.flush()
            if step%8==0:
                print(json.dumps(entry),flush=True)
            if step%32==0:
                write_checkpoint(dict(last_layer=model.model.layers[-1].state_dict(),manifest={**manifest,'completed_records':step}),args.out/'latest.pt',torch.save)
    manifest.update(training_seconds=time.perf_counter()-start,issued_training_records=len(train),updates=updates,stage='trained')
    write_checkpoint(dict(last_layer=model.model.layers[-1].state_dict(),manifest=manifest),args.out/'last-layer.pt',torch.save)
    manifest['checkpoint_sha256']=hashlib.sha256((args.out/'last-layer.pt').read_bytes()).hexdigest()
    dump(args.out/'run.json',manifest)
    del opt
    model.eval()
    if args.dynamic_int8:
        model.model=torch.ao.quantization.quantize_dynamic(model.model,{torch.nn.Linear},dtype=torch.qint8,inplace=False)
        manifest['quantization']='PyTorch CPU dynamic INT8 decoder Linear; embeddings and dense vocabulary head stay FP32; not FPGA arithmetic'
    cases=select_cases(args.data/'external-evaluation.jsonl',args.per_category)
    dump(args.out/'selected-evaluation.json',dict(ids=[r['id'] for r in cases]))
    answers=json.loads((args.data/'bfcl-answer-registry.json').read_text())
    checker=checker_self_check(args.data/'bfcl-python-checker',read_jsonl(args.data/'external-evaluation.jsonl'),answers)
    rows=[]
    stop=tok.convert_tokens_to_ids('<start_function_response>')
    stops=list(dict.fromkeys(list(model.config.eos_token_id)+[stop,tok.convert_tokens_to_ids('<end_of_turn>')]))
    manifest['generation_stop_ids']=stops
    manifest['generation_stop_tokens']=tok.convert_ids_to_tokens(stops)
    dump(args.out/'run.json',manifest)
    with (args.out/'requests.jsonl').open('w',encoding='utf-8') as journal:
        for case in cases:
            row=dict(id=case['id'],category=case['category'],correct=False,model_structure_valid=False)
            start=time.perf_counter_ns()
            try:
                prompt=template(case)
                p=ids(prompt)
                row['prompt_tokens']=len(p)
                if len(p)+args.output_cap>args.context_cap:
                    raise ValueError('prompt and reserved output exceed profile; no truncation')
                if len(case['tools'])>8:
                    raise ValueError('more than eight tools in software profile')
                prefill_start=time.perf_counter_ns()
                with torch.inference_mode():
                    output=model.model(input_ids=torch.tensor([p]),use_cache=True)
                    logits=model.lm_head(output.last_hidden_state[:,-1,:])
                    token=int(logits.argmax(-1)[0])
                    emitted=[token]
                    first=time.perf_counter_ns()
                    cache=output.past_key_values
                    while len(emitted)<args.output_cap and token not in stops:
                        output=model.model(input_ids=torch.tensor([[token]]),past_key_values=cache,use_cache=True)
                        cache=output.past_key_values
                        token=int(model.lm_head(output.last_hidden_state[:,-1,:]).argmax(-1)[0])
                        emitted.append(token)
                generated=time.perf_counter_ns()
                raw=tok.decode(emitted,skip_special_tokens=False).strip()
                row.update(raw_output=raw,output_tokens=len(emitted),
                    prefill_and_first_token_ms=(first-prefill_start)/1e6,
                    decode_after_first_ms=(generated-first)/1e6)
                if emitted[-1] not in stops:
                    raise ValueError('output cap exhausted before terminal marker')
                calls=parse_functiongemma(raw,case['tools'])
                row.update(calls=calls,output=canonical_outcome(calls),model_structure_valid=True)
                row['inference_latency_ms']=(time.perf_counter_ns()-start)/1e6
                verdict=checker.score(case,calls,answers[case['id']])
                row.update(correct=bool(verdict['valid']),bfcl_verdict=verdict,
                    arguments=checker.arguments(case,calls,answers[case['id']]))
            except Exception as exc:
                row['inference_latency_ms']=(time.perf_counter_ns()-start)/1e6
                row.update(error=type(exc).__name__+': '+str(exc),output=dict(outcome='Fault',reason='software_reference_failure'),
                    arguments=checker.arguments(case,[],answers[case['id']]))
            row['latency_ms']=(time.perf_counter_ns()-start)/1e6
            rows.append(row)
            journal.write(json.dumps(row)+'\n');journal.flush()
            print(json.dumps({k:row[k] for k in ('id','correct','latency_ms','error') if k in row}),flush=True)
    accepted=[r for r in rows if r['output']['outcome']=='Accepted']
    correct=sum(r['correct'] for r in rows)
    slots={k:sum(r.get('arguments',{}).get(k,0) for r in rows) for k in ('tp','fp','fn')}
    result=dict(requests=len(rows),correct=correct,full_command_accuracy=correct/len(rows),
        model_structural_validity=sum(r['model_structure_valid'] for r in rows)/len(rows),
        accepted_coverage=len(accepted)/len(rows),accepted_error=sum(not r['correct'] for r in accepted)/len(accepted) if accepted else None,
        argument_diagnostic=slots,argument_micro_f1=2*slots['tp']/max(1,2*slots['tp']+slots['fp']+slots['fn']),
        argument_note='Greedy same-name call pairing; full-command decision uses upstream BFCL matching',
        categories={cat:dict(requests=sum(r['category']==cat for r in rows),correct=sum(r['correct'] for r in rows if r['category']==cat))
                    for cat in sorted({r['category'] for r in rows})},
        resident_latency_ms={f'p{q}':percentile([r['inference_latency_ms'] for r in rows],q/100) for q in (50,95,99)},
        timing_boundary='prompt construction/tokenization + dense prefill/decode + validation; excludes local BFCL scoring and file write',
        startup_seconds=manifest['load_seconds'],execution='host_CPU_only',blind_test=False,energy_joules=None,hard_deadline_claim=False)
    dump(args.out/'summary.json',result)
    manifest.update(stage='complete',memory_at_end=process_memory())
    dump(args.out/'run.json',manifest)


if __name__=='__main__':
    main()
