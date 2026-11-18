"""Qualified batch evaluator for the frozen official FunctionGemma reference.

Different execution profile from the single-request trace; all cases retained.
Parity mode compares literal token-decoded outputs with a saved official run.
"""
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
from sysone.v2.general_clean_inference import CleanInference
from sysone.v2.general_schema_annotations import adapt_tool
from sysone.v2.general_tools import parse_functiongemma
from sysone.v2.general_tool_eval import read_jsonl,select_cases,checker_self_check
from sysone.v2.functiongemma_profile import validate_prompt_ids
from sysone.v2.functiongemma_batch import generate_ids
from sysone.v2.command_metrics import process_memory


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',required=True)
    ap.add_argument('--data',type=Path,default=Path('build/v2/general-tool-data-v1'))
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--batch-size',type=int,default=4)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--parity-journal',type=Path)
    args=ap.parse_args()
    if not 1<=args.batch_size<=8:raise ValueError('batch outside declared profile')
    args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(args.threads)
    cases=select_cases(args.data/'external-evaluation.jsonl',0)
    answers=json.loads((args.data/'bfcl-answer-registry.json').read_text(encoding='utf-8'))
    checker=checker_self_check(args.data/'bfcl-python-checker',cases,answers)
    expected=None
    if args.parity_journal:
        expected={r['id']:r for r in read_jsonl(args.parity_journal)}
        cases=[r for r in cases if r['id'] in expected]
        if len(cases)!=len(expected):raise ValueError('parity cases differ')
    manifest=dict(stage='starting',family='functiongemma',official_reference=True,checkpoint_loaded=False,
        model_path=args.model,mode='parity' if expected is not None else 'full_bfcl',
        requests=len(cases),batch_size=args.batch_size,threads=args.threads,
        execution='host_CPU_FP32_batch_no_tool_execution',blind=False,checkpoint_selection=False,
        data_sha256={n:digest(args.data/n) for n in ['external-evaluation.jsonl','bfcl-answer-registry.json','manifest.json']},
        latency_scope='batch execution wall time per member; excludes pretokenization, queueing, load and checker; not single-request latency',
        board_contacted=False,paid_compute=False)
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/n for n in ['functiongemma_batch.py','functiongemma_profile.py',
        'general_clean_inference.py','general_training_v2.py','general_tool_encoder.py','general_schema_annotations.py',
        'general_tools.py','general_tool_eval.py']]
    (args.out/'sources').mkdir()
    manifest['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sources}
    for p in sources:(args.out/'sources'/p.name).write_bytes(p.read_bytes())
    def dump(name,value):(args.out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    dump('run.json',manifest);dump('selected-cases.json',cases)
    started=time.perf_counter()
    engine=CleanInference('functiongemma',args.model,None)
    model,tok=engine.model,engine.tok
    prepared=[];rows=[]
    for case in cases:
        tools=[adapt_tool(t) for t in case['tools']]
        messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),dict(role='user',content=case['query'])]
        text=tok.apply_chat_template(messages,tools=[dict(type='function',function=t) for t in tools],add_generation_prompt=True,tokenize=False)
        ids=tok.encode(text,add_special_tokens=False)
        if len(tools)>8:raise ValueError('tool profile preflight failed')
        validate_prompt_ids(ids,model.config.vocab_size)
        prepared.append((case,tools,ids))
    prepared.sort(key=lambda r:(len(r[2]),r[0]['id']))
    manifest['load_and_preparation_seconds']=time.perf_counter()-started
    start_eval=time.perf_counter()
    with (args.out/'requests.jsonl').open('w',encoding='utf-8') as stream:
        for offset in range(0,len(prepared),args.batch_size):
            batch=prepared[offset:offset+args.batch_size]
            emitted,batch_ms=generate_ids(model,[r[2] for r in batch],engine.stops,model.config.pad_token_id)
            for (case,tools,ids),tokens in zip(batch,emitted):
                raw=tok.decode(tokens,skip_special_tokens=False).strip()
                row=dict(id=case['id'],category=case['category'],correct=False,valid=False,calls=[],
                    raw_output=raw,prompt_tokens=len(ids),output_tokens=len(tokens),batch_offset=offset,
                    actual_batch_size=len(batch),padded_prompt_tokens=max(len(r[2]) for r in batch),batch_wall_ms=batch_ms)
                try:
                    if tokens[-1] not in engine.stops:raise ValueError('output work cap exhausted')
                    row.update(calls=parse_functiongemma(raw,tools),valid=True)
                except (ValueError,TypeError,KeyError) as exc:row['error']='ValueError: '+str(exc)
                row['accepted']=row['valid'] and bool(row['calls'])
                if row['valid']:
                    row['bfcl_verdict']=checker.score(case,row['calls'],answers[case['id']])
                    row['correct']=bool(row['bfcl_verdict']['valid'])
                if expected is not None:
                    prior=expected[case['id']]
                    row['parity']=(row['raw_output']==prior.get('raw_output') and row['calls']==prior.get('calls',[])
                        and row['valid']==prior.get('valid',prior.get('model_structure_valid',False))
                        and row.get('error')==prior.get('error'))
                rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
            print(json.dumps(dict(completed=len(rows),requests=len(cases),batch_ms=batch_ms)),flush=True)
    accepted=[r for r in rows if r['accepted']]
    summary=dict(requests=len(rows),correct=sum(r['correct'] for r in rows),accepted=len(accepted),
        correct_accepted=sum(r['correct'] for r in accepted),wrong_accepted=sum(not r['correct'] for r in accepted),
        errors=dict(Counter(r['error'] for r in rows if r.get('error'))),
        categories={c:dict(requests=sum(r['category']==c for r in rows),correct=sum(r['category']==c and r['correct'] for r in rows)) for c in sorted({r['category'] for r in rows})},
        evaluation_seconds=time.perf_counter()-start_eval,batch_size=args.batch_size)
    if expected is not None:
        summary['parity_passed']=all(r['parity'] for r in rows)
        summary['parity_failures']=[r['id'] for r in rows if not r['parity']]
    manifest.update(stage='complete' if expected is None or summary['parity_passed'] else 'failed_parity',
        summary=summary,memory_at_end=process_memory())
    dump('summary.json',summary);dump('run.json',manifest);print(json.dumps(summary))
    if expected is not None and not summary['parity_passed']:raise ValueError('batch prediction parity failed')


if __name__=='__main__':main()
