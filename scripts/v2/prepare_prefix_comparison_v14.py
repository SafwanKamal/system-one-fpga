"""Freeze v14 inputs/sources without modifying prior results or deployment."""
import hashlib,json,shutil,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from run_prefix_comparison_v14 import VERSION
from run_v8_json_retention_v10 import seal_check,preserved
from run_v8_chain_pilot_v5 import dump

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checks=preserved();prior=ROOT/'build/v2/v9d-retention-comparison-v13';checks['v13']=seal_check(prior)
 work=ROOT/'build/v2'/VERSION;bundle=work/'bundle';bundle.mkdir(exist_ok=False)
 old=prior/'evaluation/bundle';jobs=json.loads((old/'frozen-jobs.json').read_text());spec=json.loads((old/'manifest.json').read_text())
 for key in ('maximum_inferences','repeats','prompt_policy'):spec.pop(key,None)
 spec.update(version=VERSION,maximum_records_cached=448,fpga_inferences_cached=328,cpu_records_cold_plus_cached=896,
  cache_policy='single active chain+arm, reset at boundary, no package metadata writes, conservative prompt-only aligned FPGA reuse',
  fpga_cold_control='sealed v13 same-v9d outputs/timings; new live cold/cached qualification; all cached generated IDs checked',
  cpu_cold_control='fresh same persistent server cold and cached sequences; both warm model, exact IDs checked',
  cpu_server_sha256=sha(ROOT/'build/v2/generation/windows/llama-server.exe'),
  cpu_binaries_sha256={p.name:sha(p) for p in (ROOT/'build/v2/generation/windows').glob('*.dll')},
  latency_policy='warm requests on both backends; server/model startup separate; compare cached common-fit steps and sealed v13 FPGA baseline')
 dump(bundle/'manifest.json',spec);dump(bundle/'jobs.json',jobs)
 refs={r['id']:r for r in map(json.loads,(prior/'evaluation/fpga/requests.jsonl').read_text().splitlines()) if r['executed']}
 dump(bundle/'cold-reference.json',refs)
 j={x['id']:x for x in jobs};case='paired-mixed-32';
 patterns=[(1,'json',None),(1,'json',None),(2,'json',None),(3,'json',None),
  (1,'history',None),(2,'history',None),(3,'history',None),(1,'history',None),
  (17,'history',None),(18,'history',None),(18,'history','tag'),(1,'json','reset')]
 q=[]
 for i,(step,arm,invalidate) in enumerate(patterns):
  base=j[f'{case}-{step:03d}-{arm}'];q.append(dict(base,id=f'qualification-{i:02d}',reference_id=base['id'],invalidate=invalidate))
 dump(bundle/'qualification-jobs.json',q)
 for n in json.loads((old/'source-sha256.json').read_text()):
  if not n.startswith(('src/','scripts/','tests/')):continue
  dst=bundle/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/n,dst)
 names=['src/sysone/v2/prefix_cache_v14.py','scripts/v2/cpu_prefix_server_v14.py','scripts/v2/run_prefix_comparison_v14.py',
  'scripts/v2/inventory_prefix_v14.py','scripts/v2/prepare_prefix_comparison_v14.py','scripts/v2/ssh_prefix_comparison_v14.py',
  'tests/test_prefix_cache_v14.py']
 for n in names:
  dst=bundle/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst)
 dump(bundle/'source-sha256.json',{p.relative_to(bundle).as_posix():sha(p) for p in bundle.rglob('*') if p.is_file()})
 with tarfile.open(work/'qualification.tar','w') as t:
  for p in sorted(bundle.rglob('*')):
   if p.is_file():t.add(p,arcname=p.relative_to(bundle).as_posix())
 dump(work/'preflight.json',dict(prior_seals_verified=checks,archive_sha256=sha(work/'qualification.tar'),runnable=328,overflow=120,
  cached_records_per_backend=448,board_access_during_preparation=False,full_sweep_started=False))
 print(json.dumps(dict(prepared=True,qualification_cases=len(q),cached_records=448)))
if __name__=='__main__':main()
