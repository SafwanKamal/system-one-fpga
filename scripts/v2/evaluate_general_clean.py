"""Evaluate frozen clean-training checkpoints without any training or selection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.general_clean_inference import CleanInference, InferenceFailure
from sysone.v2.general_tool_eval import read_jsonl, select_cases, checker_self_check
from sysone.v2.command_task import percentile
from sysone.v2.command_metrics import process_memory


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--mode',choices=['audit-parity','bfcl'],required=True)
    ap.add_argument('--data',type=Path,default=Path('build/v2/general-tool-data-v1'))
    ap.add_argument('--per-category',type=int,default=5,help='0 evaluates all declared BFCL requests')
    ap.add_argument('--parity-limit',type=int,default=8,help='0 checks the full audit')
    ap.add_argument('--threads',type=int,default=4)
    args=ap.parse_args()
    if args.per_category<0 or args.parity_limit<0:
        raise ValueError('negative limit')
    run=json.loads((args.run/'run.json').read_text())
    if run['stage']!='complete':
        raise ValueError('training run incomplete')
    checkpoint=args.run/'best.pt'
    if digest(checkpoint)!=run['best_checkpoint_sha256']:
        raise ValueError('checkpoint hash mismatch')
    args.out.mkdir(parents=True,exist_ok=False)
    manifest=dict(stage='starting',mode=args.mode,family=run['family'],best=run['best'],
        parent_run=str(args.run),parent_checkpoint_sha256=digest(checkpoint),
        execution='host_CPU_only_no_tool_execution',board_contacted=False,paid_compute=False,
        training_updates=0,checkpoint_selection=False,blind=False)
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/n for n in
        ['general_clean_inference.py','general_training_v2.py','general_schema_annotations.py',
         'general_tool_encoder.py','general_tools.py','general_tool_eval.py']]
    (args.out/'sources').mkdir()
    manifest['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sources}
    for p in sources:(args.out/'sources'/p.name).write_bytes(p.read_bytes())
    if args.mode=='audit-parity':
        cases=json.loads((args.run/'audit-cases.json').read_text())
        cases=cases[:args.parity_limit] if args.parity_limit else cases
        expected={r['id']:r for r in read_jsonl(args.run/'audit-best-requests.jsonl')}
    else:
        cases=select_cases(args.data/'external-evaluation.jsonl',args.per_category)
        answers=json.loads((args.data/'bfcl-answer-registry.json').read_text())
        checker=checker_self_check(args.data/'bfcl-python-checker',read_jsonl(args.data/'external-evaluation.jsonl'),answers)
        manifest['data_sha256']={n:digest(args.data/n) for n in
            ['external-evaluation.jsonl','bfcl-answer-registry.json','manifest.json']}
    manifest['requests']=len(cases)
    dump(args.out/'selected-cases.json',cases)
    dump(args.out/'run.json',manifest)
    torch.set_num_threads(args.threads)
    start=time.perf_counter()
    model=CleanInference(run['family'],run['arguments']['model'],checkpoint)
    manifest['load_seconds']=time.perf_counter()-start
    rows=[]
    with (args.out/'requests.jsonl').open('w',encoding='utf-8') as stream:
        for case in cases:
            result=dict(id=case['id'],valid=False,calls=[])
            start=time.perf_counter_ns()
            try:
                calls,extra=model(case['query'],case['tools'])
                result.update(calls=calls,valid=True,**extra)
            except InferenceFailure as exc:
                result.update(error='ValueError: '+str(exc),**exc.details)
            result['inference_ms']=(time.perf_counter_ns()-start)/1e6
            result['accepted']=result['valid'] and bool(result['calls'])
            if args.mode=='audit-parity':
                prior=expected[case['id']]
                result['parity']=(result['valid']==prior['valid'] and result['calls']==prior['calls']
                    and result.get('error')==prior.get('error')
                    and result.get('raw_output')==prior.get('raw_output'))
                if not result['parity']:
                    raise ValueError('inference parity differs '+case['id'])
            else:
                result['category']=case['category']
                result['correct']=False
                if result['valid']:
                    result['bfcl_verdict']=checker.score(case,result['calls'],answers[case['id']])
                    result['correct']=bool(result['bfcl_verdict']['valid'])
            rows.append(result)
            stream.write(json.dumps(result)+'\n');stream.flush()
            print(json.dumps({k:result[k] for k in ['id','correct','parity','error'] if k in result}),flush=True)
    accepted=[r for r in rows if r['accepted']]
    summary=dict(requests=len(rows),valid=sum(r['valid'] for r in rows),accepted=len(accepted),
        failures=dict(Counter(r['error'] for r in rows if r.get('error'))),
        latency_ms={f'p{q}':percentile([r['inference_ms'] for r in rows],q/100) for q in [50,95,99]},
        execution='host_CPU_only',blind=False)
    if args.mode=='audit-parity':
        summary['parity_passed']=all(r['parity'] for r in rows)
    else:
        summary.update(correct=sum(r['correct'] for r in rows),
            correct_accepted=sum(r['correct'] for r in accepted),
            wrong_accepted=sum(not r['correct'] for r in accepted),
            categories={c:dict(requests=sum(r['category']==c for r in rows),
                correct=sum(r['category']==c and r['correct'] for r in rows)) for c in sorted({r['category'] for r in rows})})
    dump(args.out/'summary.json',summary)
    manifest.update(stage='complete',memory_at_end=process_memory(),summary=summary)
    dump(args.out/'run.json',manifest)
    print(json.dumps(summary))


if __name__=='__main__':
    main()
