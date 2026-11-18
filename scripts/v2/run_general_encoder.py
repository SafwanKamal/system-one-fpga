"""Train and evaluate a schema-conditioned BERT extraction pilot on general tools."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import torch
from torch import nn
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_tool_encoder import ToolEncoder,KINDS,job_text,training_jobs,scalar_from_span
from sysone.v2.general_tools import normalize_tool,validate_calls,canonical_outcome
from sysone.v2.general_tool_eval import read_jsonl,select_cases,checker_self_check
from sysone.v2.command_task import percentile
from sysone.v2.command_metrics import process_memory
from sysone.v2.checkpoint_io import write_checkpoint


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--train-records',type=int,default=128)
    ap.add_argument('--per-category',type=int,default=5)
    ap.add_argument('--epochs',type=int,default=2)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--checkpoint',type=Path)
    ap.add_argument('--quantize',action='store_true')
    ap.add_argument('--train-last-layers',type=int,default=2)
    ap.add_argument('--max-input-tokens',type=int,default=128)
    ap.add_argument('--integer-reference',action='store_true')
    ap.add_argument('--max-calls-per-tool',type=int,default=4)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads);torch.manual_seed(20261017)
    manifest=dict(stage='starting',execution='host_CPU_only_no_tool_execution',blind_test=False,
        arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        seed=20261017,limitations=['Extractive values plus boolean/null/empty constants; no free-form rewriting',
            'Four calls total and eight candidate tools; legacy checkpoints retain their recorded per-tool cap',
            'Count pass reads tool description and parameter signatures; argument pass additionally reads the selected parameter description',
            'Full catalog is available to adapter; conditional passes expose selected schema views to the model'],
        data_sha256={name:hashlib.sha256((args.data/name).read_bytes()).hexdigest() for name in ('train.jsonl','external-evaluation.jsonl','manifest.json')})
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/n for n in ('general_tool_encoder.py','general_tools.py','general_tool_eval.py','general_tool_integer.py')]
    (args.out/'sources').mkdir()
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    for p in sources:
        (args.out/'sources'/p.name).write_bytes(p.read_bytes())
    dump(args.out/'run.json',manifest)
    start=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    saved=torch.load(args.checkpoint,map_location='cpu',weights_only=False) if args.checkpoint else None
    effective_max_calls=saved['state_dict']['count.weight'].shape[0]-2 if saved else args.max_calls_per_tool
    if not 1<=effective_max_calls<=4:
        raise ValueError('per-tool call cap must be between one and four')
    model=ToolEncoder(args.model,max_calls_per_tool=effective_max_calls)
    manifest['effective_max_calls_per_tool']=effective_max_calls
    model.encoder.requires_grad_(False)
    if not 1<=args.train_last_layers<=len(model.encoder.encoder.layer):
        raise ValueError('invalid trainable layer count')
    for layer in model.encoder.encoder.layer[-args.train_last_layers:]:
        layer.requires_grad_(True)
    if args.checkpoint:
        model.load_state_dict(saved['state_dict'],strict=True)
        manifest.update(parent_checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),parent_training_manifest=saved['manifest'])
    manifest.update(load_seconds=time.perf_counter()-start,memory_after_load=process_memory(),
        parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))
    train=read_jsonl(args.data/'train.jsonl')
    random.Random(20261017).shuffle(train)
    train=train[:args.train_records]
    dump(args.out/'selected-training.json',dict(ids=[r['id'] for r in train]))
    jobs,failures,kinds=training_jobs(train,tok,max_tokens=args.max_input_tokens,max_calls_per_tool=effective_max_calls)
    dump(args.out/'training-preparation.json',dict(records=len(train),jobs=len(jobs),profile_failures=failures,argument_target_kinds=kinds))
    dump(args.out/'training-jobs.json',jobs)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=3e-5)
    rng=random.Random(20261017)
    steps=0
    start=time.perf_counter()
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as stream:
        for epoch in range(0 if args.checkpoint else args.epochs):
            # Shuffle length-matched batches, avoiding padding every short query
            # to the longest schema in a random batch.
            ordered=sorted(jobs,key=lambda j:len(j['tokens']['input_ids']))
            batches=[ordered[i:i+8] for i in range(0,len(ordered),8)]
            rng.shuffle(batches)
            model.train()
            for batch in batches:
                tokens=tok.pad([j['tokens'] for j in batch],padding=True,return_tensors='pt')
                optimizer.zero_grad(set_to_none=True)
                count,kind,span=model(tokens)
                parts=[]
                for i,j in enumerate(batch):
                    if j['task']=='count':
                        parts.append(nn.functional.cross_entropy(count[i:i+1],torch.tensor([j['count']])))
                    else:
                        loss=nn.functional.cross_entropy(kind[i:i+1],torch.tensor([j['kind']]))
                        if KINDS[j['kind']]=='span':
                            loss+=(nn.functional.cross_entropy(span[i:i+1,:,0],torch.tensor([j['start']]))+
                                   nn.functional.cross_entropy(span[i:i+1,:,1],torch.tensor([j['end']])))/2
                        parts.append(loss)
                loss=torch.stack(parts).mean()
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);optimizer.step()
                steps+=1
                record=dict(epoch=epoch,step=steps,loss=loss.item(),elapsed_seconds=time.perf_counter()-start)
                stream.write(json.dumps(record)+'\n');stream.flush()
                if steps%10==0:
                    print(json.dumps(record),flush=True)
                if steps%32==0:
                    write_checkpoint(dict(state_dict=model.state_dict(),manifest={**manifest,'completed_steps':steps}),args.out/'latest.pt',torch.save)
    manifest.update(stage='trained',training_seconds=time.perf_counter()-start,steps=steps,
        issued_training_records=0 if args.checkpoint else len(train),training_jobs_per_epoch=len(jobs),argument_target_kinds=kinds)
    write_checkpoint(dict(state_dict=model.state_dict(),manifest=manifest),args.out/'checkpoint.pt',torch.save)
    manifest['checkpoint_sha256']=hashlib.sha256((args.out/'checkpoint.pt').read_bytes()).hexdigest()
    dump(args.out/'run.json',manifest)
    del optimizer
    if args.integer_reference:
        if args.quantize or args.max_input_tokens>128:
            raise ValueError('FPGA-arithmetic reference requires non-dynamic quantization and <=128 input profile')
        from sysone.v2.general_tool_integer import IntegerToolEncoder
        model=IntegerToolEncoder(model,jobs,args.out)
        manifest['quantization']='existing IntEncoder/ImageMachine FPGA arithmetic; float32 image scales promoted to float64 for decisions'
        manifest['execution']='host_integer_simulation_only'
    if args.quantize:
        model=torch.ao.quantization.quantize_dynamic(model.eval(),{nn.Linear},dtype=torch.qint8,inplace=False)
        manifest['quantization']='PyTorch CPU dynamic INT8 Linear; not FPGA integer arithmetic'
    model.eval()
    cases=select_cases(args.data/'external-evaluation.jsonl',args.per_category)
    dump(args.out/'selected-evaluation.json',dict(ids=[r['id'] for r in cases]))
    answers=json.loads((args.data/'bfcl-answer-registry.json').read_text())
    checker=checker_self_check(args.data/'bfcl-python-checker',read_jsonl(args.data/'external-evaluation.jsonl'),answers)
    rows=[]
    with (args.out/'requests.jsonl').open('w',encoding='utf-8') as journal:
        for case in cases:
            start=time.perf_counter_ns()
            row=dict(id=case['id'],category=case['category'],correct=False,model_structure_valid=False,encoder_passes=0,proposals=[])
            def predict(tool,arg=None,slot=0):
                encoding=tok(job_text(tool,arg,slot,effective_max_calls),case['query'],truncation=False,return_offsets_mapping=True)
                if len(encoding['input_ids'])>args.max_input_tokens:
                    raise ValueError('encoder pass exceeds input profile; no truncation')
                tensors={k:torch.tensor([v]) for k,v in encoding.items() if k!='offset_mapping'}
                with torch.inference_mode():
                    outputs=model(tensors)
                row['encoder_passes']+=1
                return encoding,outputs
            try:
                if len(case['tools'])>8:
                    raise ValueError('more than eight tools')
                calls=[]
                missing=False
                for raw_tool in case['tools']:
                    tool=normalize_tool(raw_tool)
                    encoding,(count,_,_)=predict(tool)
                    n=int(count.argmax(-1)[0])
                    if n==effective_max_calls+1:
                        raise ValueError('predicted call count exceeds per-tool profile')
                    for slot in range(n):
                        if len(calls)>=4:
                            raise ValueError('predicted more than four calls total')
                        arguments={}
                        for name,spec in tool['parameters']['properties'].items():
                            encoding,(_,kind,span)=predict(tool,name,slot)
                            value_kind=KINDS[int(kind.argmax(-1)[0])]
                            if value_kind in ('omit','unrepresentable'):
                                if name in tool['parameters'].get('required',[]) or value_kind=='unrepresentable':
                                    missing=True
                                continue
                            if value_kind=='span':
                                valid=[i for i,s in enumerate(encoding.sequence_ids()) if s==1 and encoding['offset_mapping'][i][1]>encoding['offset_mapping'][i][0]]
                                if not valid:
                                    raise ValueError('no user query tokens')
                                a=max(valid,key=lambda i:float(span[0,i,0]))
                                ends=[i for i in valid if a<=i<a+64]
                                b=max(ends,key=lambda i:float(span[0,i,1]))
                                begin=encoding['offset_mapping'][a][0];end=encoding['offset_mapping'][b][1]
                                arguments[name]=scalar_from_span(case['query'][begin:end],spec)
                            else:
                                arguments[name]={'true':True,'false':False,'null':None,'empty_string':'','empty_array':[],'empty_object':{}}[value_kind]
                        calls.append(dict(name=tool['name'],arguments=arguments))
                row['proposals']=calls
                if missing:
                    row.update(calls=[],output=dict(outcome='Clarify',reason='missing_or_unrepresentable_argument'),model_structure_valid=True)
                    effective=[]
                else:
                    validate_calls(calls,case['tools'])
                    row.update(calls=calls,output=canonical_outcome(calls),model_structure_valid=True)
                    effective=calls
                row['inference_latency_ms']=(time.perf_counter_ns()-start)/1e6
                verdict=checker.score(case,effective,answers[case['id']])
                row.update(correct=bool(verdict['valid']),bfcl_verdict=verdict,arguments=checker.arguments(case,effective,answers[case['id']]))
            except Exception as exc:
                row['inference_latency_ms']=(time.perf_counter_ns()-start)/1e6
                row.update(error=type(exc).__name__+': '+str(exc),output=dict(outcome='Fault',reason='software_reference_failure'),
                    arguments=checker.arguments(case,[],answers[case['id']]))
            row['latency_ms']=(time.perf_counter_ns()-start)/1e6
            rows.append(row);journal.write(json.dumps(row)+'\n');journal.flush()
            print(json.dumps({k:row[k] for k in ('id','correct','latency_ms','encoder_passes','error') if k in row}),flush=True)
    accepted=[r for r in rows if r['output']['outcome']=='Accepted']
    slots={k:sum(r['arguments'][k] for r in rows) for k in ('tp','fp','fn')}
    result=dict(requests=len(rows),correct=sum(r['correct'] for r in rows),full_command_accuracy=sum(r['correct'] for r in rows)/len(rows),
        model_structural_validity=sum(r['model_structure_valid'] for r in rows)/len(rows),
        accepted_coverage=len(accepted)/len(rows),accepted_error=sum(not r['correct'] for r in accepted)/len(accepted) if accepted else None,
        argument_diagnostic=slots,argument_micro_f1=2*slots['tp']/max(1,2*slots['tp']+slots['fp']+slots['fn']),
        categories={cat:dict(requests=sum(r['category']==cat for r in rows),correct=sum(r['correct'] for r in rows if r['category']==cat)) for cat in sorted({r['category'] for r in rows})},
        resident_latency_ms={f'p{q}':percentile([r['inference_latency_ms'] for r in rows],q/100) for q in (50,95,99)},
        timing_boundary='all schema-conditioned passes, tokenization, decoding and validation; excludes local BFCL scoring and file write',
        execution='host_integer_simulation_only' if args.integer_reference else 'host_CPU_only',blind_test=False,energy_joules=None,hard_deadline_claim=False)
    dump(args.out/'summary.json',result)
    manifest.update(stage='complete',memory_at_end=process_memory())
    dump(args.out/'run.json',manifest)


if __name__=='__main__':
    main()
