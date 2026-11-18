"""Fresh software development comparison within 1024 total tokens; no FPGA access."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import tokenizers

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from maintenance_pilot import (sha,dump,write_rows,read_rows,verdict,summary,http,run_classical,run_encoder)
from sysone.v2.maintenance.revision2 import VERSION,CONTEXT,OUTPUT,corpus,prompt,demonstrations,calibration_subset
from sysone.v2.maintenance.dataset import public_input,manifest,STRATA
from sysone.v2.maintenance.schema import encode,parse,canonical
from sysone.v2.maintenance.baselines import flatten,unflatten
from sysone.v2.qwen_tokenizer_v1 import Vocabulary


def verify_parent():
    parent=ROOT/'build/v2/maintenance-pilot-v1'
    sealed=json.loads((parent/'final-seal.json').read_text())['files_sha256']
    if any(sha(parent/name)!=digest for name,digest in sealed.items()):
        raise RuntimeError('Parent seal mismatch')
    return dict(seal_sha256=sha(parent/'final-seal.json'),verified_files=len(sealed))


def verify(work):
    for name,digest in json.loads((work/'source-sha256.json').read_text()).items():
        if sha(ROOT/name)!=digest or sha(work/'snapshot'/name)!=digest:raise RuntimeError('Source differs: '+name)
    for name,digest in json.loads((work/'data-sha256.json').read_text()).items():
        if sha(work/name)!=digest:raise RuntimeError('Frozen data differs: '+name)


def prepare(work):
    prior=verify_parent();work.mkdir(parents=True,exist_ok=False)
    data=corpus()
    for split,rows in data.items():
        write_rows(work/(split+'.jsonl'),rows)
        for row in rows:
            assert parse(encode(row['gold']),row['catalog'])==row['gold']
            assert unflatten(flatten(row['gold'],row['catalog']),row['catalog'])==row['gold']
    demos=demonstrations(data['train'])
    selected=calibration_subset(data['tuning'])
    dump(work/'demonstrations.json',demos)
    dump(work/'tuning-selection-ids.json',[c['id'] for c in selected])
    vocabulary=Vocabulary(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment')
    from transformers import AutoTokenizer
    encoder_tok=AutoTokenizer.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'),local_files_only=True)
    from sysone.v2.maintenance.baselines import features
    jobs=[]
    try:
        for split,rows in data.items():
            for case in rows:
                for mode,examples in (('zero',()),('examples',demos)):
                    text=prompt(case,examples);ids=vocabulary.encode_text(text)
                    jobs.append(dict(id=case['id'],split=split,mode=mode,prompt=text,prompt_ids=ids,
                        input_tokens=len(ids),output_reservation=OUTPUT,total_context=CONTEXT,
                        fits=len(ids)+OUTPUT<=CONTEXT,
                        encoder_input_tokens=len(encoder_tok(features(public_input(case)))['input_ids'])))
    finally:vocabulary.close()
    write_rows(work/'frozen-jobs.jsonl',jobs)
    token_report={}
    for split in data:
        token_report[split]={}
        for mode in ('zero','examples'):
            rows=[r for r in jobs if r['split']==split and r['mode']==mode]
            token_report[split][mode]=dict(count=len(rows),eligible=sum(r['fits'] for r in rows),
                min_input=min(r['input_tokens'] for r in rows),max_input=max(r['input_tokens'] for r in rows),
                max_total=max(r['input_tokens']+OUTPUT for r in rows),
                encoder_max_input=max(r['encoder_input_tokens'] for r in rows))
    dump(work/'token-audit-summary.json',token_report)
    candidate=ROOT/'build/v2/qwen-fpga-decoder-v9d/deployment/model-manifest.json'
    evidence=ROOT/'build/v2/qwen-fpga-decoder-v9d/board-evidence-1/validation-summary.json'
    candidate_manifest=json.loads(candidate.read_text())
    assert candidate_manifest['max_context']==CONTEXT
    dump(work/'manifest.json',dict(manifest(data),version=VERSION,context=CONTEXT,output_tokens=OUTPUT,
        candidate_context_evidence={str(candidate.relative_to(ROOT)):sha(candidate),str(evidence.relative_to(ROOT)):sha(evidence)},
        active_candidate_assumed=False,board_access=False,parent=prior,
        candidate_ordering='request mentions, previous-request mentions, then other public assets; no gold access',
        neural_policy=dict(encoder_epochs=6,encoder_seeds=1,qwen_weight_training=False,
            qwen_prompt_candidates=['zero','examples'],examples=4,
            selection='24 balanced tuning cases: maximize correct then valid, tie choose zero',
            examples_from='training_only; demonstration requests without repeated catalogs; full catalog in actual query')))
    names=[Path(__file__),ROOT/'scripts/v2/maintenance_pilot.py',ROOT/'tests/test_maintenance_pilot.py',
           ROOT/'tests/test_maintenance_revision2.py',ROOT/'src/sysone/v2/qwen_tokenizer_v1.py',
           ROOT/'src/sysone/v2/v8_benchmark.py']+list((ROOT/'src/sysone/v2/maintenance').glob('*.py'))
    hashes={}
    for path in names:
        name=path.relative_to(ROOT).as_posix();dst=work/'snapshot'/name
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dst);hashes[name]=sha(path)
    dump(work/'source-sha256.json',hashes)
    files=('train.jsonl','tuning.jsonl','audit.jsonl','demonstrations.json','tuning-selection-ids.json',
           'frozen-jobs.jsonl','manifest.json','token-audit-summary.json')
    dump(work/'data-sha256.json',{n:sha(work/n) for n in files})
    print(json.dumps(token_report),flush=True)


def run_qwen(work,threads):
    model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    binary=ROOT/'build/v2/generation/windows/llama-server.exe'
    if sha(model)!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':raise RuntimeError('Model differs')
    server=work/'qwen-server';server.mkdir(exist_ok=False)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    command=[str(binary),'-m',str(model),'--host','127.0.0.1','--port',str(port),'-c',str(CONTEXT),
             '-np','1','-ngl','0','-t',str(threads),'-tb',str(threads),'--no-warmup']
    dump(server/'command.json',command)
    log=(server/'server.log').open('wb');child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
    jobs={(j['id'],j['mode']):j for j in read_rows(work/'frozen-jobs.jsonl')}
    config=dict(model_sha256=sha(model),server_sha256=sha(binary),context=CONTEXT,
        output_reservation=OUTPUT,threads=threads,prefix_cache=False,greedy=True,weight_training=False,
        actual_prompt_ids_verified=True,board_access=False,energy_joules=None)
    def evaluate(cases,mode,name):
        out=work/name;out.mkdir(exist_ok=False);rows=[]
        for i,case in enumerate(cases):
            verify(work);job=jobs[(case['id'],mode)]
            if not job['fits']:
                row=verdict(case,'',0,capacity_failure=True)
            else:
                ids=http(base,'/tokenize',dict(content=job['prompt'],add_special=False))['tokens']
                if ids!=job['prompt_ids']:raise RuntimeError('Actual tokenizer mismatch')
                tick=time.perf_counter()
                response=http(base,'/completion',dict(prompt=ids,n_predict=OUTPUT,temperature=0,seed=0,
                                                     repeat_penalty=1,cache_prompt=False,stream=False))
                dump(out/(case['id']+'.response.json'),response)
                row=verdict(case,response['content'],time.perf_counter()-tick,
                    actual_prompt_ids=ids,input_tokens=len(ids),total_budget=len(ids)+OUTPUT,
                    generated_tokens=response.get('tokens_predicted'),stop_type=response.get('stop_type'),
                    truncated=response.get('truncated'),mode=mode)
            with (out/'predictions.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n');stream.flush()
            rows.append(row);dump(out/'status.json',dict(completed=i+1,total=len(cases)))
            print(json.dumps(dict(phase=name,completed=i+1,correct=row['correct'])),flush=True)
        dump(out/'summary.json',dict(summary(rows),config=config,mode=mode))
        return rows
    try:
        tick=time.monotonic()
        while True:
            if child.poll() is not None:raise RuntimeError('Server exited')
            try:
                if http(base,'/health').get('status')=='ok':break
            except (urllib.error.URLError,TimeoutError):pass
            if time.monotonic()-tick>180:raise RuntimeError('Startup timed out')
            time.sleep(.5)
        tuning=read_rows(work/'tuning.jsonl');chosen=set(json.loads((work/'tuning-selection-ids.json').read_text()))
        tuning=[c for c in tuning if c['id'] in chosen]
        stats={}
        for mode in ('zero','examples'):
            rows=evaluate(tuning,mode,'qwen-tuning-'+mode)
            stats[mode]=summary(rows)
        # Earlier mode wins exact ties. No audit output participates in selection.
        selected=max(('zero','examples'),key=lambda m:(stats[m]['correct'],stats[m]['valid']))
        dump(work/'selection.json',dict(selected=selected,tuning_stats=stats,
             selected_before_audit=True,criterion='correct, then valid, then earlier zero mode'))
        evaluate(read_rows(work/'audit.jsonl'),selected,'qwen-audit')
    finally:
        child.terminate()
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        log.close()


def report(work):
    cases={c['id']:c for c in read_rows(work/'audit.jsonl')}
    from sysone.v2.maintenance.dataset import score
    results={}
    for name in ('rules','tfidf','minilm','qwen-audit'):
        folder=work/name
        p=folder/('predictions.jsonl' if name=='qwen-audit' else 'audit-predictions.jsonl')
        rows=read_rows(p)
        if [r['id'] for r in rows]!=list(cases):raise RuntimeError('Incomplete audit')
        for row in rows:
            case=cases[row['id']]
            try:
                ast=parse(row['raw_output'],case['catalog']);correct=score(case,ast)['correct'];valid=True
            except (ValueError,TypeError,KeyError,IndexError):correct=False;valid=False
            if (correct,valid)!=(row['correct'],row['valid']):raise RuntimeError('Rescore mismatch')
        unique={}
        for row in rows:
            unique.setdefault(json.dumps(public_input(cases[row['id']]),sort_keys=True),row)
        results[name]=dict(summary(rows),distinct_inputs=len(unique),distinct_correct=sum(r['correct'] for r in unique.values()))
    dump(work/'comparison.json',dict(results=results,context=CONTEXT,development_only=True,
        all_verdicts_reproduced=True,parent=verify_parent(),energy_measured=False,board_access=False))
    lines=['# Maintenance revision2:1024-token software development comparison','',
        '| Baseline | Correct/120 | Valid/120 | Correct actionable/accepted | Distinct correct |',
        '|---|---:|---:|---:|---:|']
    for n,r in results.items():lines.append(f'| {n} | {r["correct"]} | {r["valid"]} | {r["correct_accepted"]}/{r["accepted"]} | {r["distinct_correct"]}/{r["distinct_inputs"]} |')
    lines+=['','All generator prompt+output reservations are checked against1024. No FPGA access or energy result.',
        'Authored-template development only. New candidate ordering and training budget differ fromv1; no causal score-delta claim.',
        'Qwen prompt chosen on tuning only; examples come from training; no weight adaptation or decoding constraint.']
    (work/'REPORT.md').write_text('\n'.join(lines)+'\n')
    verify(work)
    files={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file() and p.name!='final-seal.json'}
    dump(work/'final-seal.json',dict(files_sha256=files,verified_parent=True))
    print(json.dumps(results),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=['prepare','classical','encoder','qwen','report'])
    ap.add_argument('--out',type=Path,default=ROOT/'build/v2'/VERSION)
    ap.add_argument('--threads',type=int,default=4);a=ap.parse_args()
    if a.phase=='prepare':prepare(a.out);return
    verify(a.out)
    if a.phase=='classical':run_classical(a.out)
    elif a.phase=='encoder':run_encoder(a.out,epochs=6,threads=a.threads)
    elif a.phase=='qwen':run_qwen(a.out,a.threads)
    else:report(a.out)
    verify(a.out)


if __name__=='__main__':main()
