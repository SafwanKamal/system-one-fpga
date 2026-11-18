"""Bounded CPU FunctionGemma training/inference smoke, not a selection benchmark.

Uses the official chat template and a schema-derived task vocabulary for output
projection. Syntax is NOT guaranteed by this vocabulary mask; malformed outputs
are retained and scored. Frozen embedding/head weights; train final decoder layer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import time
import torch
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.command_codec import FIELDS, encode, decode, tool, allowed_values
from sysone.v2.command_task import canonical, evaluate
from sysone.v2.checkpoint_io import write_checkpoint
from sysone.v2.command_metrics import process_memory

TRIGGER='You are a model that can do function calling with the following functions'


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def read(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]


def parse_call(raw):
    pattern=r'<start_function_call>call:publish_command\{(.*?)\}<end_function_call>(?:<start_function_response>)?'
    match=re.fullmatch(pattern,raw,flags=re.DOTALL)
    if not match:
        raise ValueError('malformed or incomplete call')
    payload=match.group(1)
    pairs=re.findall(r'([a-z0-9_]+):<escape>([^<>]*)<escape>',payload)
    if ','.join(k+':<escape>'+v+'<escape>' for k,v in pairs)!=payload:
        raise ValueError('unexpected call syntax')
    fields={}
    for k,v in pairs:
        if k in fields:
            raise ValueError('duplicate field')
        fields[k]=v
    return decode(fields)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--train-examples',type=int,default=16)
    ap.add_argument('--eval-examples',type=int,default=8)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--context-cap',type=int,default=1280)
    ap.add_argument('--output-cap',type=int,default=160)
    ap.add_argument('--grammar',action='store_true')
    ap.add_argument('--checkpoint',type=Path,help='Evaluate saved final-layer checkpoint without training')
    ap.add_argument('--dynamic-int8',action='store_true',help='Evaluate dynamic INT8 decoder Linear layers; selected vocabulary projection remains FP32')
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(20261017)
    start=time.perf_counter()
    manifest=dict(stage='loading',arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        execution='host_CPU_only',scope='pipeline_smoke_not_matched_quality_benchmark',
        schema_sha256=hashlib.sha256((args.data/'schema.json').read_bytes()).hexdigest(),
        data_hashes={s:hashlib.sha256((args.data/f'{s}.jsonl').read_bytes()).hexdigest() for s in ('train','dev','diagnostic')},
        seed=20261017,quantization=None,energy_joules=None,hard_deadline_claim=False,
        output_policy='shared canonical field grammar' if args.grammar else 'schema-derived token-union mask; not full grammar; strict post-validation',
        context_profile='expanded software reference, exceeds provisional 512-token hardware target')
    dump(args.out/'run.json',manifest)
    source_files=[Path(__file__),ROOT/'src/sysone/v2/command_task.py',ROOT/'src/sysone/v2/command_codec.py',ROOT/'src/sysone/v2/command_metrics.py']
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    (args.out/'sources').mkdir()
    for p in source_files:
        (args.out/'sources'/p.name).write_bytes(p.read_bytes())
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,dtype=torch.float32)
    model.requires_grad_(False)
    backbone=model.model
    backbone.layers[-1].requires_grad_(True)
    if args.checkpoint:
        saved=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
        backbone.layers[-1].load_state_dict(saved['last_layer'],strict=True)
        manifest['parent_checkpoint_sha256']=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        manifest['parent_training_manifest']=saved['manifest']
    manifest.update(load_seconds=time.perf_counter()-start,
        parameters=sum(p.numel() for p in model.parameters()),
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))
    manifest['memory_after_load']=process_memory()
    def prompt(text):
        return tok.apply_chat_template([dict(role='developer',content=TRIGGER),dict(role='user',content=text)],
                                        tools=[tool()],add_generation_prompt=True,tokenize=False)
    def completion(fields):
        messages=[dict(role='developer',content=TRIGGER),dict(role='user',content='x')]
        prefix=tok.apply_chat_template(messages,tools=[tool()],add_generation_prompt=True,tokenize=False)
        full=tok.apply_chat_template(messages+[dict(role='assistant',tool_calls=[dict(type='function',
             function=dict(name='publish_command',arguments=fields))])],tools=[tool()],tokenize=False)
        if not full.startswith(prefix):
            raise ValueError('official template prefix mismatch')
        return full[len(prefix):]
    def ids(text):
        return tok.encode(text,add_special_tokens=False)
    # Derive vocabulary from schema alone, without examining diagnostic labels.
    seed_fields={k:v[0] for k,v in FIELDS.items()}
    vocab=set()
    for key,values in FIELDS.items():
        for value in values:
            vocab.update(ids(completion({**seed_fields,key:value})))
    vocab=sorted(vocab)
    lookup={v:i for i,v in enumerate(vocab)}
    vocab_tensor=torch.tensor(vocab)
    # Head is frozen: selecting a complete task-wide legal-token superset saves
    # projection work without allocating dense [sequence,262144] training logits.
    head=model.get_output_embeddings()
    selected_weight=head.weight.detach()[vocab_tensor].contiguous()
    selected_bias=head.bias.detach()[vocab_tensor].contiguous() if head.bias is not None else None
    manifest.update(output_vocab_ids=vocab,output_vocab_count=len(vocab))
    dump(args.out/'run.json',manifest)
    rows=read(args.data/'train.jsonl')
    random.Random(20261017).shuffle(rows)
    if args.train_examples:
        rows=rows[:args.train_examples]
    if args.checkpoint:
        rows=[]
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-5)
    start=time.perf_counter()
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as journal:
        for step,row in enumerate(rows,1):
            entry=dict(step=step,id=row['id'])
            try:
                p=ids(prompt(row['text']))
                c=ids(completion(encode(row['gold'])))
                if len(p)+len(c)>args.context_cap or len(c)>args.output_cap:
                    raise ValueError('profile exceeded; no truncation')
                if any(t not in lookup for t in c):
                    raise ValueError('schema vocabulary missed completion token')
                model.train()
                opt.zero_grad(set_to_none=True)
                out=backbone(input_ids=torch.tensor([p+c]),use_cache=False).last_hidden_state
                hidden=out[:,len(p)-1:len(p)+len(c)-1,:]
                logits=nn.functional.linear(hidden,selected_weight,selected_bias)
                target=torch.tensor([[lookup[t] for t in c]])
                loss=nn.functional.cross_entropy(logits.reshape(-1,len(vocab)),target.reshape(-1))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(backbone.layers[-1].parameters(),1.0)
                opt.step()
                entry.update(loss=loss.item(),prompt_tokens=len(p),completion_tokens=len(c))
            except Exception as exc:
                entry['error']=type(exc).__name__+': '+str(exc)
                journal.write(json.dumps(entry)+'\n');journal.flush()
                manifest.update(stage='training_failed',failed_request=entry)
                dump(args.out/'run.json',manifest)
                raise
            entry['elapsed_seconds']=time.perf_counter()-start
            journal.write(json.dumps(entry)+'\n');journal.flush()
            print(json.dumps(entry),flush=True)
    manifest.update(training_seconds=time.perf_counter()-start,training_examples=len(rows),stage='trained')
    write_checkpoint(dict(last_layer=backbone.layers[-1].state_dict(),manifest=manifest),args.out/'last-layer.pt',torch.save)
    manifest['checkpoint_sha256']=hashlib.sha256((args.out/'last-layer.pt').read_bytes()).hexdigest()
    dump(args.out/'run.json',manifest)
    del opt
    model.eval()
    if args.dynamic_int8:
        start=time.perf_counter()
        backbone=torch.ao.quantization.quantize_dynamic(backbone.eval(),{nn.Linear},dtype=torch.qint8,inplace=False)
        manifest.update(quantization='PyTorch CPU dynamic INT8 decoder Linear; FP32 embeddings/selected vocabulary projection; not FPGA arithmetic',
                        quantization_seconds=time.perf_counter()-start)
    cases=read(args.data/'diagnostic.jsonl')
    random.Random(20261017).shuffle(cases)
    cases=cases[:args.eval_examples]
    predictions=[]
    stop=tok.convert_tokens_to_ids('<start_function_response>')
    with (args.out/'diagnostic-requests.jsonl').open('w',encoding='utf-8') as journal:
        for case in cases:
            row=dict(id=case['id'])
            start=time.perf_counter_ns()
            try:
                p=ids(prompt(case['text']))
                if len(p)+args.output_cap>args.context_cap:
                    raise ValueError('prompt/output budget exceeds context profile')
                emitted=[]
                cache=None
                first=None
                with torch.inference_mode():
                    current=torch.tensor([p])
                    def forward(tokens):
                        nonlocal cache
                        result=backbone(input_ids=torch.tensor([tokens]),past_key_values=cache,use_cache=True)
                        cache=result.past_key_values
                        return nn.functional.linear(result.last_hidden_state[:,-1,:],selected_weight,selected_bias)[0]
                    if args.grammar:
                        scores=forward(p)
                        first=time.perf_counter_ns()
                        partial={}
                        def append_forced(tokens):
                            nonlocal scores
                            if len(emitted)+len(tokens)>args.output_cap:
                                raise ValueError('grammar completion exceeds output cap')
                            emitted.extend(tokens)
                            scores=forward(tokens)
                        for field_index,key in enumerate(sorted(FIELDS)):
                            literal=('<start_function_call>call:publish_command{' if field_index==0 else ',')+key+':<escape>'
                            append_forced(ids(literal))
                            options={v:ids(v+'<escape>') for v in allowed_values(partial,key)}
                            offset=0
                            while True:
                                legal=sorted({seq[offset] for seq in options.values()})
                                if any(t not in lookup for t in legal):
                                    raise ValueError('grammar token missing from schema vocabulary')
                                chosen=max(legal,key=lambda t:float(scores[lookup[t]]))
                                append_forced([chosen])
                                options={v:seq for v,seq in options.items() if seq[offset]==chosen}
                                offset+=1
                                finished=[v for v,seq in options.items() if len(seq)==offset]
                                if finished:
                                    if len(finished)!=1 or len(options)!=1:
                                        raise ValueError('ambiguous terminated grammar value')
                                    partial[key]=finished[0]
                                    break
                        append_forced(ids('}<end_function_call><start_function_response>'))
                        # Tokenization at special-token boundaries must exactly match
                        # the official template; never score an alternate serialization.
                        if emitted!=ids(completion(partial)):
                            raise ValueError('incremental grammar differs from official template tokenization')
                    for index in range(0 if args.grammar else args.output_cap):
                        output=backbone(input_ids=current,past_key_values=cache,use_cache=True)
                        cache=output.past_key_values
                        logits=nn.functional.linear(output.last_hidden_state[:,-1,:],selected_weight,selected_bias)
                        token=vocab[int(logits.argmax(-1)[0])]
                        emitted.append(token)
                        if first is None:
                            first=time.perf_counter_ns()
                        if token==stop:
                            break
                        current=torch.tensor([[token]])
                end=time.perf_counter_ns()
                raw=tok.decode(emitted,skip_special_tokens=False)
                row.update(raw_output=raw,prompt_tokens=len(p),output_tokens=len(emitted),
                    prefill_first_token_ms=(first-start)/1e6,decode_after_first_ms=(end-first)/1e6,
                    output_cap_reached=len(emitted)==args.output_cap and emitted[-1]!=stop)
                try:
                    row['output']=canonical(parse_call(raw))
                except ValueError as exc:
                    row.update(output=raw,decode_error=str(exc))
            except Exception as exc:
                row.update(error=type(exc).__name__,output='')
            row['latency_ms']=(time.perf_counter_ns()-start)/1e6
            predictions.append(row)
            journal.write(json.dumps(row)+'\n');journal.flush()
            print(json.dumps({k:row[k] for k in ('id','latency_ms','output_tokens') if k in row}),flush=True)
    result=evaluate(cases,predictions)
    result.update(blind_test=False,execution='host_CPU_only',training_examples=len(rows),
                  timing_boundary='resident prompt/tokenization + prefill + bounded greedy decode + strict parse; first request included')
    dump(args.out/'diagnostic-summary.json',result)
    manifest['stage']='complete'
    manifest['memory_at_end']=process_memory()
    dump(args.out/'run.json',manifest)


if __name__=='__main__':
    main()
