"""Two frozen phases; fresh evaluation cannot run until development passes."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_json_retention_v10 import VERSION,development,evaluation,execute,development_summary,summarize
from run_v8_chain_pilot_v5 import CPU,dump
from run_v8_json_retention_v9 import preserved as older_preserved


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def seal_check(base):
    hs=json.loads((base/'seal.json').read_text())['files_sha256']
    for n,h in hs.items():
        if sha(base/n)!=h:raise RuntimeError('Sealed evidence changed: '+str(base/n))
    return len(hs)


def preserved():
    result=older_preserved()
    for folder in ('v8-json-retention-v9','v8-json-retention-v9-report'):
        result[folder]=seal_check(ROOT/'build/v2'/folder)
    first=ROOT/'build/v2/v8-json-retention-v10/development'
    if (first/'seal.json').exists():result['v10-first-development']=seal_check(first)
    second=ROOT/'build/v2/v8-json-retention-v10-r2/development'
    if (second/'seal.json').exists():result['v10-r2-development']=seal_check(second)
    return result


def signature(job):return json.dumps([job['state'],job['entity']],sort_keys=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['development','evaluation'],required=True)
    ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--run',action='store_true');args=ap.parse_args()
    parent=ROOT/'build/v2'/VERSION;work=parent/args.phase
    dev=parent/'development'
    if args.phase=='evaluation':
        seal_check(dev);chosen=json.loads((dev/'summary.json').read_text())
        if not chosen['gate_passed']:raise RuntimeError('Development gate failed; evaluation stays stopped')
    if not args.run:
        before=preserved();work.mkdir(parents=True,exist_ok=False);out=work/'cpu';out.mkdir()
        cpu=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',out)
        try:
            spec,jobs=(development(cpu.vocab.encode_text,include_original=False)
                       if args.phase=='development' else evaluation(cpu.vocab.encode_text))
        finally:cpu.close()
        # Task identity ignores prompt wording: changing a template cannot make an old state/query fresh.
        prior=set()
        for folder in ('v8-state-pilot-v6-r2','v8-json-diagnostics-v7','v8-json-diagnostics-v7-r2','v8-json-retention-v9'):
            for line in (ROOT/'build/v2'/folder/'cpu/requests.jsonl').read_text().splitlines():
                r=json.loads(line);state=r.get('state',r.get('state_before'))
                entity=r.get('entity',(r.get('expected') or [None,None])[1])
                if state is not None:prior.add(json.dumps([state,entity],sort_keys=True))
        if args.phase=='evaluation':
            for j in json.loads((dev/'frozen-jobs.json').read_text()):prior.add(signature(j))
        if any(signature(j) in prior for j in jobs):raise RuntimeError('Prior task reused')
        dump(work/'manifest.json',spec);dump(work/'frozen-jobs.json',jobs)
        if args.phase=='evaluation':
            dump(work/'selection.json',dict(development_seal_sha256=sha(dev/'seal.json'),summary=chosen))
        names=['src/sysone/v2/v8_json_retention_v10.py','src/sysone/v2/v8_json_retention_v9.py',
               'src/sysone/v2/v8_state_pilot_v6.py','src/sysone/v2/v8_chain_pilot_v5.py','src/sysone/v2/v8_benchmark.py',
               'src/sysone/v2/qwen_tokenizer_v1.py','scripts/v2/run_v8_chain_pilot_v5.py',
               'scripts/v2/run_v8_json_retention_v9.py','scripts/v2/run_v8_json_retention_v10.py',
               'tests/test_v8_json_retention_v10.py']
        hashes={}
        for n in names:
            dst=work/'snapshot'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst);hashes[n]=sha(ROOT/n)
        n='build/v2/generation/windows/llama-completion.exe';hashes[n]=sha(ROOT/n)
        for n in ('manifest.json','frozen-jobs.json'):
            hashes[(work/n).relative_to(ROOT).as_posix()]=sha(work/n)
        if args.phase=='evaluation':hashes[(dev/'seal.json').relative_to(ROOT).as_posix()]=sha(dev/'seal.json')
        dump(work/'source-sha256.json',hashes)
        dump(work/'preflight.json',dict(prior_seals=before,prior_task_overlap=0,requests=len(jobs),
             board_access=False,full_sweep_started=False,closed_loop_included=False))
        if args.prepare_only:return
    if (work/'seal.json').exists():raise RuntimeError('Completed results cannot be rerun')
    frozen=json.loads((work/'source-sha256.json').read_text())
    def verify():
        for n,h in frozen.items():
            if sha(ROOT/n)!=h:raise RuntimeError('Frozen source/input changed: '+n)
    verify();preserved();jobs=json.loads((work/'frozen-jobs.json').read_text());out=work/'cpu'
    rows=[json.loads(x) for x in (out/'requests.jsonl').read_text().splitlines()] if (out/'requests.jsonl').exists() else []
    if [r['id'] for r in rows]!=[j['id'] for j in jobs[:len(rows)]]:raise RuntimeError('Resume prefix mismatch')
    for r,j in zip(rows,jobs):
        if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Frozen input mismatch')
    cpu=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',out)
    try:
        for job in jobs[len(rows):]:
            row=execute(job,cpu.infer)
            with (out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
            rows.append(row);dump(work/'status.json',dict(stage='running',completed=len(rows),total=len(jobs),
                last_id=row['id'],board_access=False,full_sweep_started=False))
            print(json.dumps(dict(completed=len(rows),total=len(jobs),id=row['id'],correct=row['correct'])),flush=True)
        verify();checks=preserved();summary=(development_summary if args.phase=='development' else summarize)(rows)
        dump(work/'summary.json',summary);dump(work/'failures.json',[r for r in rows if not r['correct']])
        dump(work/'status.json',dict(stage='complete',completed=len(rows),total=len(jobs),source_integrity_passed=True,
             prior_seals_verified=checks,board_access=False,full_sweep_started=False,closed_loop_included=False))
        dump(work/'seal.json',dict(files_sha256={p.relative_to(work).as_posix():sha(p) for p in sorted(work.rglob('*')) if p.is_file()}))
    except Exception as exc:
        dump(work/'status.json',dict(stage='attention',completed=len(rows),error=str(exc),board_access=False,full_sweep_started=False));raise
    finally:cpu.close()


if __name__=='__main__':main()
