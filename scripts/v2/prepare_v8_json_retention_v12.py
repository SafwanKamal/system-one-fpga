"""Freeze a separate qualification bundle; copy runtime only from sealed v8."""
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.v8_json_retention_v12 import VERSION,prepare
from run_v8_chain_pilot_v5 import CPU,dump
from run_v8_json_retention_v10 import preserved,seal_check


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    checks=preserved()
    for name in ('development','evaluation'):
        checks['v10-r3-'+name]=seal_check(ROOT/'build/v2/v8-json-retention-v10-r3'/name)
    checks['v10-report']=seal_check(ROOT/'build/v2/v8-json-retention-v10-report')
    checks['v11-r2']=seal_check(ROOT/'build/v2/v8-json-retention-v11-r2')
    work=ROOT/'build/v2'/VERSION;work.mkdir(parents=True,exist_ok=False);bundle=work/'bundle';bundle.mkdir()
    package=ROOT/'build/v2/qwen-fpga-decoder-v8/deployment'
    cpu=CPU(package,work)
    try:spec,jobs=prepare(cpu.vocab.encode_text)
    finally:cpu.close()
    selected=json.loads((ROOT/'build/v2/v8-json-retention-v10-r3/evaluation/source-sha256.json').read_text())
    for n,h in selected.items():
        if n.startswith('src/') or n=='build/v2/generation/windows/llama-completion.exe':
            if sha(ROOT/n)!=h:raise RuntimeError('Selected CPU retention source/executable changed: '+n)
    spec['cpu_cli_sha256']=sha(ROOT/'build/v2/generation/windows/llama-completion.exe')
    prior=set()
    for folder in ('v8-json-retention-v9','v8-json-retention-v10/development',
                   'v8-json-retention-v10-r2/development','v8-json-retention-v10-r3/development',
                   'v8-json-retention-v10-r3/evaluation','v8-json-retention-v11-r2'):
        for line in (ROOT/'build/v2'/folder/'cpu/requests.jsonl').read_text().splitlines():
            row=json.loads(line);prior.add(json.dumps([row['state'],row['entity']],sort_keys=True))
    if any(json.dumps([j['state'],j['entity']],sort_keys=True) in prior for j in jobs):raise RuntimeError('Prior task reused')
    dump(bundle/'manifest.json',spec);dump(bundle/'frozen-jobs.json',jobs)
    names=['src/sysone/v2/v8_json_retention_v12.py','src/sysone/v2/v8_json_fpga_qualification_v11.py','src/sysone/v2/v8_json_retention_v10.py',
           'src/sysone/v2/v8_json_retention_v9.py','src/sysone/v2/v8_state_pilot_v6.py',
           'src/sysone/v2/v8_chain_pilot_v5.py','src/sysone/v2/v8_benchmark.py',
           'scripts/v2/run_v8_chain_pilot_v5.py','scripts/v2/run_v8_benchmark.py',
           'scripts/v2/run_v8_json_retention_v12.py','scripts/v2/inventory_v8_json_retention_v11.py',
           'scripts/v2/prepare_v8_json_retention_v12.py','scripts/v2/ssh_v8_json_retention_v12.py',
           'tests/test_v8_json_retention_v12.py','tests/test_v8_json_fpga_qualification_v11.py']
    for n in names:
        dst=bundle/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst)
    for source in (package/'src').rglob('*.py'):
        dst=bundle/'src'/source.relative_to(package/'src');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dst)
    hashes={p.relative_to(bundle).as_posix():sha(p) for p in bundle.rglob('*') if p.is_file()}
    dump(bundle/'source-sha256.json',hashes)
    with tarfile.open(work/'qualification.tar','w') as archive:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():archive.add(p,arcname=p.relative_to(bundle).as_posix())
    dump(work/'preflight.json',dict(sealed_files_verified=checks,prior_task_overlap=0,requests_per_backend=len(jobs),
         primary_per_backend=sum(j['suite']=='primary' for j in jobs),repeats_per_backend=sum(j['suite']=='repeat' for j in jobs),archive_sha256=sha(work/'qualification.tar'),
         selected_prompt_sha256=sha(ROOT/'src/sysone/v2/v8_json_retention_v10.py'),
         board_access_during_preparation=False,full_sweep_started=False))
    print(json.dumps(dict(prepared=True,requests_per_backend=len(jobs),input_tokens=sorted({r['input_tokens'] for r in jobs}))))


if __name__=='__main__':main()
