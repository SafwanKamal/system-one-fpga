"""Audit actual skipped work and output parity before sealing cached results."""
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from run_v8_json_retention_v10 import preserved,seal_check
from report_retention_comparison_v13 import stats
from sysone.v2.v8_state_pilot_v6 import normalize
VERSION='v9d-prefix-comparison-v14'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def lcp(a,b):
 n=0
 for x,y in zip(a,b):
  if x!=y:break
  n+=1
 return n

def metrics(rs):
 r=stats(rs);ex=[x for x in rs if x['executed']]
 r.update(reused_tokens=sum(x['prefix_tokens_reused'] for x in ex),evaluated_tokens=sum(x['prefill_tokens_evaluated'] for x in ex),
  requests_with_reuse=sum(x['prefix_tokens_reused']>0 for x in ex))
 r['token_reuse_fraction']=r['reused_tokens']/r['processed_input_tokens'] if r['processed_input_tokens'] else None
 return r

def main():
 work=ROOT/'build/v2'/VERSION;bundle=work/'bundle'
 if (work/'seal.json').exists():raise RuntimeError('Completed evidence immutable')
 for n,h in read(bundle/'source-sha256.json').items():
  if sha(bundle/n)!=h:raise RuntimeError('Frozen source/input differs: '+n)
  if n.startswith(('src/','scripts/')) and (ROOT/n).exists() and sha(ROOT/n)!=h:raise RuntimeError('Executing source differs: '+n)
 checks=preserved();prior=ROOT/'build/v2/v9d-retention-comparison-v13';checks['v13']=seal_check(prior);checks['v14-cpu-phase']=seal_check(work/'cpu')
 spec=read(bundle/'manifest.json')
 if sha(ROOT/'build/v2/generation/windows/llama-server.exe')!=spec['cpu_server_sha256']:raise RuntimeError('CPU server binary changed')
 for n,h in spec['cpu_binaries_sha256'].items():
  if sha(ROOT/'build/v2/generation/windows'/n)!=h:raise RuntimeError('CPU DLL changed')
 jobs=read(bundle/'jobs.json');old=read(prior/'evaluation/bundle/frozen-jobs.json')
 if jobs!=old:raise RuntimeError('Logical workloads changed')
 refs=read(bundle/'cold-reference.json');oldrows={r['id']:r for r in map(json.loads,(prior/'evaluation/fpga/requests.jsonl').read_text().splitlines())}
 if refs!={k:v for k,v in oldrows.items() if v['executed']}:raise RuntimeError('Cold reference differs')
 index={j['id']:j for j in jobs};rows={};qual={}
 for backend in ('cpu','fpga'):
  folder=work/backend;s=read(folder/'status.json')
  if backend=='cpu':
   if s['stage']!='attention' or s['completed']!=896 or not s.get('error','').startswith('CPU cached output differs'):raise RuntimeError('Unexpected CPU execution failure')
  elif s['stage']!='complete' or not s['source_integrity_passed']:raise RuntimeError(backend+' incomplete')
  q=work/('qualification-'+backend);qual[backend]=read(q/'qualification.json')
  if not qual[backend]['passed']:raise RuntimeError('Qualification failed')
  if backend=='cpu' and (not read(q/'server-closed.json')['closed'] or not read(folder/'server-closed.json')['closed']):raise RuntimeError('CPU server still open')
  rs=[json.loads(x) for x in (folder/'requests.jsonl').read_text().splitlines()]
  expected=[]
  for case in dict.fromkeys(j['case_id'] for j in jobs):
   for arm in ('json','history'):
    for trial in (('cold','cached') if backend=='cpu' else ('cached',)):
     expected.extend(trial+'-'+j['id'] for j in jobs if j['case_id']==case and j['arm']==arm)
  if [r['id'] for r in rs]!=expected:raise RuntimeError('Schedule differs')
  previous={}
  for r in rs:
   j=index[r['reference_id']]
   if any(r[k]!=v for k,v in j.items() if k!='id'):raise RuntimeError('Frozen metadata differs')
   if (folder/(r['id']+'.prompt.txt')).read_bytes()!=j['prompt'].encode():raise RuntimeError('Prompt framing differs')
   key=(r['case_id'],r['arm'],r['trial'])
   if not r['executed']:
    if j['capacity_ok'] or r['prefix_tokens_reused'] or r['prefill_tokens_evaluated'] or r['seconds'] is not None:raise RuntimeError('Overflow accounting')
    continue
   if not j['capacity_ok']:raise RuntimeError('Capacity exceeded')
   reused=r['prefix_tokens_reused'];evaluated=r['prefill_tokens_evaluated'];prev=previous.get(key)
   if reused+evaluated!=j['input_tokens'] or evaluated<=0:raise RuntimeError('Work accounting')
   if prev is None and reused:raise RuntimeError('Cache crossed boundary')
   if backend=='fpga':
    n=0 if prev is None else (min(lcp(prev,j['prompt_ids']),len(j['prompt_ids'])-1)//8)*8
    if reused!=n or r['work']['prefill_tokens']!=evaluated:raise RuntimeError('Actual skipped hardware work differs')
    if r['generated_ids']!=refs[j['id']]['generated_ids']:raise RuntimeError('FPGA output changed')
   else:
    response=read(folder/(r['id']+'.response.json'));request=read(folder/(r['id']+'.request.json'))
    if request['prompt']!=j['prompt_ids'] or r['actual_cpu_prompt_ids']!=j['prompt_ids']:raise RuntimeError('CPU input IDs changed')
    tm=response['timings']
    if response.get('truncated') or tm['cache_n']!=reused or tm['prompt_n']!=evaluated or response['tokens']!=r['generated_ids']:raise RuntimeError('CPU telemetry differs')
    if r['trial']=='cold' and reused:raise RuntimeError('Cold CPU reused cache')
    if prev is not None and reused>min(lcp(prev,j['prompt_ids']),len(j['prompt_ids'])-1):raise RuntimeError('CPU prefix exceeds prompt match')
   previous[key]=j['prompt_ids']
   try:obs=normalize(r['generated_text'],terminal=r['terminal_eos'])['record']
   except ValueError:obs=None
   if r['observed']!=obs or r['correct']!=(obs==j['expected']):raise RuntimeError('Independent score mismatch')
  rows[backend]=rs
 cpu_index={r['id']:r for r in rows['cpu']}
 cpu_differences=[]
 for j in jobs:
  a,b=cpu_index['cold-'+j['id']],cpu_index['cached-'+j['id']]
  if a['executed']:
   if a['observed']!=b['observed'] or a['correct']!=b['correct'] or a['parsed']!=b['parsed']:raise RuntimeError('CPU cached semantic result differs')
   if a['generated_ids']!=b['generated_ids']:
    def obj(text):
     import re
     return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip()))
    if obj(a['generated_text'])!=obj(b['generated_text']):raise RuntimeError('CPU difference beyond formatting')
    cpu_differences.append(dict(id=j['id'],cold_text=a['generated_text'],cached_text=b['generated_text']))
 metrics_by={};common={j['id'].rsplit('-',1)[0] for j in jobs if j['arm']=='history' and j['capacity_ok']}
 for backend,data in rows.items():
  metrics_by[backend]={}
  for trial in sorted({r['trial'] for r in data}):
   rs=[r for r in data if r['trial']==trial]
   metrics_by[backend][trial]=dict(by_arm={a:metrics([r for r in rs if r['arm']==a]) for a in ('json','history')},
    common_fit={a:metrics([r for r in rs if r['arm']==a and r['reference_id'].rsplit('-',1)[0] in common]) for a in ('json','history')},
    by_length={str(n):{a:metrics([r for r in rs if r['chain_length']==n and r['arm']==a]) for a in ('json','history')} for n in (16,32,64)})
 baseline=read(prior/'evaluation/comparison-summary.json')['backend_results']['fpga']
 fixtures={str(p.relative_to(work)):read(p) for folder in ('fpga','qualification-fpga') for p in (work/folder).glob('*fixture*.json')}
 board=work/'board';before=read(board/'live-before.json');after=read(board/'live-after.json')
 gates=dict(qualifications_passed=True,all_actual_work_verified=True,all_cpu_cached_semantic_results_equal_fresh_cold=True,strict_cpu_bit_identity_passed=not cpu_differences,
  all_fpga_cached_ids_equal_sealed_v13_cold=True,all_causal_fixtures_passed=len(fixtures)==16 and all(f['passed'] for f in fixtures.values()),
  live_identity_unchanged=before==after,baseline_v13_identity_matches=before==read(prior/'evaluation/board/live-after.json'),package_unchanged=read(work/'fpga/deployment-before.json')==read(work/'fpga/deployment-after.json'),
  shared_reservation_released=read(board/'released.json')['released'],ssh_closed=read(board/'session-closed.json')['closed'])
 summary=dict(version=VERSION,passed=all(gates.values()),semantic_and_cache_validity_passed=all(v for k,v in gates.items() if k!='strict_cpu_bit_identity_passed'),gates=gates,qualification=qual,metrics=metrics_by,
  cpu_original_status=read(work/'cpu/status.json'),cpu_format_differences=cpu_differences,cpu_exact_id_matches=328-len(cpu_differences),
  sealed_v13_fpga_baseline=baseline,fixture_vectors=sum(len(f['cases']) for f in fixtures.values()),
  fixture_worst_abs=max(c['max_absolute_error'] for f in fixtures.values() for c in f['cases']),prior_seals_verified=checks,
  full_sweep_started=False,context_limit=1024,output_budget=48,
  limitations=['Same known teacher-forced reference histories, not closed-loop or a new holdout.',
   'FPGA cold baseline is sealed v13 across runs, same boot/image/clocks/package, not interleaved.',
   'CPU uses fresh same-server warm-model cold controls; v13 CPU process wall is not a cache-only baseline.',
   'One uninterrupted case+arm owns KV cache; interleaved conversations and eviction not measured.',
   'FPGA cache conservatively rounds down to8-token prefix boundary and caches prompt only.',
   'Cached tokens still occupy context; no capacity extension or model correction.',
   'Strict CPU bit-identity check failed:16 formatting-only differences. Original attention status preserved; semantic parity audited separately; server documents batch-size-dependent logits.'])
 write(work/'comparison-summary.json',summary)
 fields=['id','reference_id','case_id','chain_length','step','arm','trial','executed','correct','category','input_tokens',
  'prefix_tokens_reused','prefill_tokens_evaluated','generated_token_count','seconds','prefill_seconds','decode_seconds']
 with (work/'requests-comparison.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['backend']+fields);w.writeheader()
  for backend,data in rows.items():
   for r in data:w.writerow(dict(backend=backend,**{k:r.get(k) for k in fields}))
 (work/'report-source.py').write_bytes(Path(__file__).read_bytes())
 write(work/'seal.json',dict(files_sha256={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()}))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
