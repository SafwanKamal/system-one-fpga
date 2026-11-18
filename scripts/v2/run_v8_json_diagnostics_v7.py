"""Freeze, audit, and run a bounded CPU-only development check in a new folder."""
import hashlib
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_json_diagnostics_v7 import VERSION,manifest,campaign,summarize,audit_v6
from run_v8_chain_pilot_v5 import CPU,dump


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_seal(root,name,base=None):
    base=root if base is None else base
    files=json.loads((root/name).read_text())['files_sha256']
    for n,h in files.items():
        if sha(base/n)!=h: raise RuntimeError('Sealed evidence changed: '+str(base/n))
    return len(files)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--primitive-only',action='store_true');args=ap.parse_args()
    work=ROOT/('build/v2/'+VERSION);work.mkdir(parents=True,exist_ok=False)
    old=ROOT/'build/v2/v8-state-pilot-v6-r2'
    before={'v6':verify_seal(old,'pilot-seal.json'),
            'v8':verify_seal(ROOT/'build/v2/qwen-fpga-decoder-v8','seal.json',ROOT)}
    rows=[json.loads(line) for line in (old/'cpu/requests.jsonl').read_text().splitlines()]
    dump(work/'v6-failure-audit.json',audit_v6(rows,json.loads((old/'pilot-manifest.json').read_text())))
    spec=manifest()
    if args.primitive_only:
        spec['cases']=[];spec['maximum_inferences']=24
    dump(work/'manifest.json',spec)
    files=['src/sysone/v2/v8_json_diagnostics_v7.py','src/sysone/v2/v8_state_pilot_v6.py',
           'src/sysone/v2/v8_chain_pilot_v5.py','src/sysone/v2/v8_benchmark.py',
           'src/sysone/v2/qwen_tokenizer_v1.py','scripts/v2/run_v8_chain_pilot_v5.py',
           'scripts/v2/run_v8_json_diagnostics_v7.py','tests/test_v8_json_diagnostics_v7.py']
    hashes={}
    for n in files:
        dst=work/'snapshot'/n;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/n,dst);hashes[n]=sha(ROOT/n)
    exe='build/v2/generation/windows/llama-completion.exe';hashes[exe]=sha(ROOT/exe)
    dump(work/'sources.json',hashes)
    def verify_sources():
        for n,h in hashes.items():
            if sha(ROOT/n)!=h: raise RuntimeError('Frozen source changed: '+n)
    verify_sources();out=work/'cpu';out.mkdir();backend=CPU(ROOT/'build/v2/qwen-fpga-decoder-v8/deployment',out)
    count=0
    def commit(row):
        nonlocal count
        with (out/'requests.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
        count+=1;dump(work/'status.json',dict(stage='running',records=count,last_id=row['id'],board_access=False,full_sweep_started=False))
        print(json.dumps({k:row[k] for k in ('id','correct','local_correct','category','input_tokens')}),flush=True)
    try:
        rs=campaign(spec,backend.vocab.encode_text,backend.infer,commit)
        verify_sources()
        assert before['v6']==verify_seal(old,'pilot-seal.json')
        assert before['v8']==verify_seal(ROOT/'build/v2/qwen-fpga-decoder-v8','seal.json',ROOT)
        dump(work/'summary.json',summarize(rs))
        repeats={}
        for r in rs: repeats.setdefault(tuple(r['prompt_ids']),[]).append(r['generated_text'])
        dump(work/'repeat-checks.json',dict(repeated_groups=sum(len(v)>1 for v in repeats.values()),
             mismatches=sum(len(set(v))>1 for v in repeats.values())))
        dump(work/'status.json',dict(stage='complete',records=count,source_integrity_passed=True,
             prior_seals_verified=before,board_access=False,full_sweep_started=False))
        dump(work/'seal.json',dict(files_sha256={p.relative_to(work).as_posix():sha(p)
             for p in sorted(work.rglob('*')) if p.is_file()}))
    finally: backend.close()


if __name__=='__main__': main()
