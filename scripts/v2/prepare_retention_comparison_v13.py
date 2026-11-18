"""Freeze immutable comparison inputs before backend execution."""
import argparse,copy,hashlib,json,shutil,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.retention_comparison_v13 import VERSION,prepare,HISTORY_SYSTEM
from run_v8_chain_pilot_v5 import CPU,dump
from run_v8_json_retention_v10 import seal_check,preserved

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--development',action='store_true');a=ap.parse_args()
 checks=preserved();checks['v12']=seal_check(ROOT/'build/v2/v8-json-retention-v12')
 work=ROOT/'build/v2'/VERSION/('development-r3' if a.development else 'evaluation');work.mkdir(parents=True,exist_ok=False)
 bundle=work/'bundle';bundle.mkdir();package=ROOT/'build/v2/qwen-fpga-decoder-v9d/deployment'
 package_hashes=json.loads((package/'package-sha256.json').read_text())
 for n,h in package_hashes.items():
  if sha(package/n)!=h:raise RuntimeError('Candidate package differs: '+n)
 spec=json.loads((ROOT/'build/v2/v8-json-retention-v12/bundle/manifest.json').read_text())
 spec.update(version=VERSION,context_limit=1024,output_budget=48,maximum_records=448,full_sweep_started=False,
  workload_source='sealed v12 primary six cases, reused intentionally for matched representation comparison',
  history_policy='all prior observations/queries and canonical correct assistant replies; teacher-forced, no truncation',
  overflow_policy='explicit capacity rejection; excluded from inference-only accuracy and latency; counted in delivered accuracy',
  cpu_cli_sha256=sha(ROOT/'build/v2/generation/windows/llama-completion.exe'),
  candidate_package_manifest_sha256=sha(package/'package-sha256.json'),history_system=HISTORY_SYSTEM,
  latency_policy='no inter-request prefix reuse; CPU process wall and internal prefill/decode separated; FPGA warm requests, startup separate')
 if a.development:
  cases=[]
  for idx,(e,s) in enumerate(( (e,s) for e in ('A','B') for s in ('ok','missing','error') )):
   other='B' if e=='A' else 'A';obs=dict(entity=e,status=s)
   if s=='ok':obs['count']=212+idx
   cases.append(dict(id=f'dev-{e}-{s}',family='development',initial={'A':[112+idx,'ok'],'B':[162+idx,'ok']},
    steps=[dict(entity=e,observation=obs),dict(entity=e,observation=dict(entity=other,status='ok',count=262+idx)),
           dict(entity=e,observation=None)]))
  spec['cases']=cases;spec['workload_source']='fresh development cases, disjoint counts from v12';spec['maximum_records']=36
 else:
  dev=ROOT/'build/v2'/VERSION/'development-r3/cpu/status.json'
  if not dev.exists():raise RuntimeError('Development must complete first')
  d=json.loads(dev.read_text())
  if d['stage']!='complete' or d['completed']!=36 or not d['source_integrity_passed']:raise RuntimeError('Development protocol incomplete')
  dr=[json.loads(x) for x in (dev.parent/'requests.jsonl').read_text().splitlines()]
  if not all(r['parsed'] and r['executed'] for r in dr):raise RuntimeError('Development format/protocol failed')
  if not all(r['correct'] for r in dr if r['arm']=='json'):raise RuntimeError('JSON control failed')
  spec['development_policy']='Protocol complete, all actual IDs verified, all parsed and JSON control correct; history semantic errors are outcomes, not a perfection gate'
  spec['development_result']={'json_correct':sum(r['correct'] for r in dr if r['arm']=='json'),'history_correct':sum(r['correct'] for r in dr if r['arm']=='history'),'requests_per_arm':18}
  frozen=json.loads((dev.parents[1]/'bundle/source-sha256.json').read_text())
  for n in ('src/sysone/v2/retention_comparison_v13.py','scripts/v2/run_retention_comparison_v13.py'):
   if sha(ROOT/n)!=frozen[n]:raise RuntimeError('Qualified prompt/runner changed')
 cpu=CPU(package,work)
 try:jobs=prepare(spec,cpu.vocab.encode_text)
 finally:cpu.close()
 assert len(jobs)==spec['maximum_records']
 dump(bundle/'manifest.json',spec);dump(bundle/'frozen-jobs.json',jobs)
 # Prior source snapshot contains all parser/reducer dependencies; do not copy legacy hardware runtime.
 old=ROOT/'build/v2/v8-json-retention-v12/bundle'
 names=[n for n in json.loads((old/'source-sha256.json').read_text()) if n.startswith(('src/','scripts/')) and not n.endswith('qwen_fpga_runtime_v7.py')]
 names+=['src/sysone/v2/retention_comparison_v13.py','scripts/v2/run_retention_comparison_v13.py',
         'scripts/v2/prepare_retention_comparison_v13.py','scripts/v2/ssh_retention_comparison_v13.py','scripts/v2/inventory_retention_v13.py','scripts/v2/smoke_qwen_fpga_v9d.py','tests/test_retention_comparison_v13.py']
 for n in names:
  dst=bundle/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst)
 for p in (package/'src').rglob('*.py'):
  dst=bundle/'src'/p.relative_to(package/'src');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
 for p in (bundle/'src').rglob('*.py'):
  n=p.relative_to(bundle).as_posix()
  if (ROOT/n).exists() and sha(ROOT/n)!=sha(p):raise RuntimeError('Executing runtime differs from pinned candidate: '+n)
 dump(bundle/'source-sha256.json',{p.relative_to(bundle).as_posix():sha(p) for p in bundle.rglob('*') if p.is_file()})
 with tarfile.open(work/'qualification.tar','w') as t:
  for p in sorted(bundle.rglob('*')):
   if p.is_file():t.add(p,arcname=p.relative_to(bundle).as_posix())
 dump(work/'preflight.json',dict(prior_seals=checks,archive_sha256=sha(work/'qualification.tar'),
  records=len(jobs),runnable=sum(j['capacity_ok'] for j in jobs),overflow=sum(not j['capacity_ok'] for j in jobs),
  board_access=False,full_sweep_started=False))
 print((work/'preflight.json').read_text())
if __name__=='__main__':main()
