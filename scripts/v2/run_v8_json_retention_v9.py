"""Freeze and execute a bounded CPU-only retention expansion, never a board sweep."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_json_retention_v9 import VERSION,manifest,prepare,execute,summarize
from run_v8_chain_pilot_v5 import CPU,dump


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def preserved():
    seals=[('v8',ROOT,ROOT/'build/v2/qwen-fpga-decoder-v8/seal.json')]
    for name,filename in [('v8-state-pilot-v6-r2','pilot-seal.json'),('v8-json-diagnostics-v7','seal.json'),('v8-json-diagnostics-v7-r2','seal.json')]:
        base=ROOT/'build/v2'/name;seals.append((name,base,base/filename))
    result={}
    for label,base,path in seals:
        hs=json.loads(path.read_text())['files_sha256']
        for n,h in hs.items():
            if sha(base/n)!=h:raise RuntimeError('Preserved artifact changed: '+str(base/n))
        result[label]=len(hs)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--run',action='store_true');args=ap.parse_args()
    work=ROOT/'build/v2'/VERSION
    if not args.run:
        before=preserved();work.mkdir(parents=True,exist_ok=False)
        out=work/'cpu';out.mkdir();cpu=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',out)
        try:spec=manifest();jobs=prepare(spec,cpu.vocab.encode_text)
        finally:cpu.close()
        # Compare all frozen prompt strings with earlier evaluation inputs before inference.
        prior=set()
        for folder in ('v8-state-pilot-v6-r2','v8-json-diagnostics-v7','v8-json-diagnostics-v7-r2'):
            for line in (ROOT/'build/v2'/folder/'cpu/requests.jsonl').read_text().splitlines():prior.add(json.loads(line)['prompt'])
        if any(j['prompt'] in prior for j in jobs):raise RuntimeError('Prior input reused')
        dump(work/'manifest.json',spec);dump(work/'frozen-jobs.json',jobs)
        names=['src/sysone/v2/v8_json_retention_v9.py','src/sysone/v2/v8_state_pilot_v6.py',
               'src/sysone/v2/v8_chain_pilot_v5.py','src/sysone/v2/v8_benchmark.py',
               'src/sysone/v2/qwen_tokenizer_v1.py','scripts/v2/run_v8_chain_pilot_v5.py',
               'scripts/v2/run_v8_json_retention_v9.py','tests/test_v8_json_retention_v9.py']
        hashes={}
        for n in names:
            dst=work/'snapshot'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst);hashes[n]=sha(ROOT/n)
        n='build/v2/generation/windows/llama-completion.exe';hashes[n]=sha(ROOT/n)
        for n in ('manifest.json','frozen-jobs.json'):hashes[(work/n).relative_to(ROOT).as_posix()]=sha(work/n)
        dump(work/'source-sha256.json',hashes)
        dump(work/'preflight.json',dict(prior_seals=before,prior_prompt_overlap=0,requests=len(jobs),
             board_access=False,full_sweep_started=False,closed_loop_included=False))
        dump(work/'status.json',dict(stage='prepared',completed=0,total=len(jobs)))
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
        if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Completed input differs from frozen job')
    cpu=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',out)
    try:
        for j in jobs[len(rows):]:
            row=execute(j,cpu.infer)
            with (out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
            rows.append(row)
            dump(work/'status.json',dict(stage='running',completed=len(rows),total=len(jobs),last_id=row['id'],
                 board_access=False,full_sweep_started=False))
            print(json.dumps(dict(completed=len(rows),total=len(jobs),id=row['id'],correct=row['correct'])),flush=True)
        verify();checks=preserved();summary=summarize(rows);dump(work/'summary.json',summary)
        dump(work/'failures.json',[r for r in rows if r['suite']=='primary' and not r['correct']])
        dump(work/'status.json',dict(stage='complete',completed=len(rows),total=len(jobs),source_integrity_passed=True,
             prior_seals_verified=checks,board_access=False,full_sweep_started=False,closed_loop_included=False))
        dump(work/'seal.json',dict(files_sha256={p.relative_to(work).as_posix():sha(p) for p in sorted(work.rglob('*')) if p.is_file()}))
    except Exception as exc:
        dump(work/'status.json',dict(stage='attention',completed=len(rows),total=len(jobs),error=str(exc),board_access=False,full_sweep_started=False));raise
    finally:cpu.close()


if __name__=='__main__':main()
