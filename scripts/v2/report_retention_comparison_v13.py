"""Independent audit and representation costs; model errors are results, not protocol failure."""
import csv,hashlib,json,re,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.retention_comparison_v13 import VERSION,prepare
from sysone.v2.v8_state_pilot_v6 import normalize
from sysone.v2.v8_json_fpga_qualification_v11 import cpu_prompt_file_bytes
from run_v8_chain_pilot_v5 import CPU
from run_v8_json_retention_v10 import preserved,seal_check

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def stats(rs):
 executed=[r for r in rs if r['executed']]
 def sample(k):
  xs=[r[k] for r in executed if r.get(k) is not None]
  return dict(n=len(xs),total=sum(xs),mean=statistics.mean(xs),median=statistics.median(xs),
   p95=sorted(xs)[max(0,__import__('math').ceil(.95*len(xs))-1)]) if xs else None
 return dict(requested=len(rs),executed=len(executed),overflow=len(rs)-len(executed),
  correct=sum(r['correct'] for r in rs),parsed=sum(r['parsed'] for r in rs),
  delivered_accuracy=sum(r['correct'] for r in rs)/len(rs) if rs else None,
  executed_accuracy=sum(r['correct'] for r in executed)/len(executed) if executed else None,
  wrong_fields={k:sum(k in r.get('wrong_fields',[]) for r in executed) for k in ('status','entity','count')},
  format_failures=sum(not r['parsed'] for r in executed),
  requested_input_tokens=sum(r['input_tokens'] for r in rs),processed_input_tokens=sum(r['input_tokens'] for r in executed),
  input_token_range=[min(r['input_tokens'] for r in rs),max(r['input_tokens'] for r in rs)] if rs else None,
  generated_tokens=sum(r['generated_token_count'] for r in executed),
  latency={k:sample(k) for k in ('seconds','inference_seconds','prefill_seconds','decode_seconds')})

def main():
 root=ROOT/'build/v2'/VERSION;work=root/'evaluation';bundle=work/'bundle'
 if (root/'seal.json').exists():raise RuntimeError('Completed experiment is immutable')
 for n,h in read(bundle/'source-sha256.json').items():
  if sha(bundle/n)!=h:raise RuntimeError('Frozen bundle differs: '+n)
 checks=preserved();checks['v12']=seal_check(ROOT/'build/v2/v8-json-retention-v12');checks['v13-cpu-phase']=seal_check(work/'cpu');checks['v13-cpu-extended-phase']=seal_check(work/'cpu-extended')
 spec=read(bundle/'manifest.json');jobs=read(bundle/'frozen-jobs.json');cpu=CPU(ROOT/'build/v2/qwen-fpga-decoder-v9d/deployment',work)
 try:
  if jobs!=prepare(spec,cpu.vocab.encode_text):raise RuntimeError('Independent observation/prompt replay differs')
 finally:cpu.close()
 index={j['id']:j for j in jobs};data={};statuses={}
 # Independently replay the reducer without calling its implementation.
 for case in spec['cases']:
  state={e:list(v) for e,v in case['initial'].items()}
  for i,step in enumerate(case['steps'],1):
   o=step['observation']
   if o:
    if o['status']=='ok':state[o['entity']][0]=o['count']
    state[o['entity']][1]=o['status']
   e=step['entity']
   for arm in ('json','history'):
    j=index[f'{case["id"]}-{i:03d}-{arm}']
    if j['state']!=state or j['expected']!=[state[e][1],e,state[e][0]]:raise RuntimeError('Independent reducer replay differs')
 for backend in ('cpu','fpga','cpu-extended'):
  folder=work/backend;s=read(folder/'status.json');statuses[backend]=s
  if s['stage']!='complete' or not s['source_integrity_passed']:raise RuntimeError(backend+' incomplete')
  rows=[json.loads(x) for x in (folder/'requests.jsonl').read_text().splitlines()]
  expected=[j for j in jobs if not j['capacity_ok']] if backend=='cpu-extended' else jobs
  if [r['id'] for r in rows]!=[j['id'] for j in expected]:raise RuntimeError('Sequence mismatch')
  for r,j in zip(rows,expected):
   if any(r.get(k)!=v for k,v in j.items()):raise RuntimeError('Frozen metadata changed')
   physical=cpu_prompt_file_bytes(j['prompt']) if backend.startswith('cpu') else j['prompt'].encode()
   if (folder/(j['id']+'.prompt.txt')).read_bytes()!=physical:raise RuntimeError('File framing differs')
   if r['backend_input_ids']!=j['prompt_ids']:raise RuntimeError('Tokenizer parity failure')
   if r['executed']:
    if backend.startswith('cpu'):
     actual=[int(n) for n in re.findall(r"\b(\d+)\s*->\s*'",(folder/(j['id']+'.stderr')).read_text(encoding='utf-8',errors='replace'))]
     if actual!=j['prompt_ids'] or actual!=r['actual_cpu_prompt_ids']:raise RuntimeError('Actual CLI token mismatch')
    try:parsed=normalize(r['generated_text'],terminal=r['terminal_eos']);observed=parsed['record']
    except ValueError:observed=None
    if observed!=r['observed'] or (observed==j['expected'])!=r['correct']:raise RuntimeError('Independent score differs')
    if r['context_used']!=(4096 if backend=='cpu-extended' else 1024):raise RuntimeError('Context differs')
    if min(r['seconds'],r['prefill_seconds'],r['decode_seconds'])<0:raise RuntimeError('Invalid timing')
   elif j['capacity_ok'] or r['category']!='context-overflow' or r['correct'] or r['seconds'] is not None:
    raise RuntimeError('Invalid overflow accounting')
  data[backend]=rows
 metrics={};pairs=[]
 for backend,rs in data.items():
  common={r['id'].rsplit('-',1)[0] for r in rs if r['arm']=='history' and r['executed']}
  metrics[backend]=dict(by_arm={a:stats([r for r in rs if r['arm']==a]) for a in ('json','history')},
   by_length={str(n):{a:stats([r for r in rs if r['chain_length']==n and r['arm']==a]) for a in ('json','history')} for n in (16,32,64)},
   common_fit={a:stats([r for r in rs if r['arm']==a and r['id'].rsplit('-',1)[0] in common]) for a in ('json','history')},chains={})
  for c in spec['cases']:
   metrics[backend]['chains'][c['id']]={}
   for arm in ('json','history'):
    cr=[r for r in rs if r['case_id']==c['id'] and r['arm']==arm]
    metrics[backend]['chains'][c['id']][arm]=dict(stats(cr),
     first_semantic_failure=next((r['step'] for r in cr if r['executed'] and not r['correct']),None),
     first_overflow=next((r['step'] for r in cr if not r['executed']),None),
     all_steps_delivered_correct=bool(cr) and all(r['correct'] for r in cr))
 aidx={r['id']:r for r in data['cpu']};bidx={r['id']:r for r in data['fpga']}
 for j in jobs:
  a,b=aidx[j['id']],bidx[j['id']]
  pairs.append(dict(id=j['id'],arm=j['arm'],executed=a['executed'] and b['executed'],
   cpu_correct=a['correct'],fpga_correct=b['correct'],
   semantic_agreement=a['observed']==b['observed'] if a['parsed'] and b['parsed'] else None,
   text_agreement=a['generated_text']==b['generated_text'] if a['executed'] and b['executed'] else None))
 fixtures={p.name:read(p) for p in (work/'fpga').glob('*fixture*.json')}
 before=read(work/'board/live-before.json');after=read(work/'board/live-after.json');initial=read(work/'board/live-v8-initial.json')
 gates=dict(actual_inputs_verified=True,independent_scoring_verified=True,
  causal_checks_passed=len(fixtures)==8 and all(f['passed'] for f in fixtures.values()),
  candidate_identity_unchanged=before==after,
  candidate_package_unchanged=read(work/'fpga/deployment-before.json')==read(work/'fpga/deployment-after.json'),
  authorized_swap_completed=read(work/'board/deploy-v9d.json')['complete'],
  protected_identity_preserved=all(initial[k]==after[k] for k in ('boot_id','launcher_sha256','dma_table_sha256','services','clocks')),
  reservation_released=read(work/'board/released.json')['released'],ssh_closed=read(work/'board/session-closed.json')['closed'])
 summary=dict(version=VERSION,protocol_passed=all(gates.values()),gates=gates,backend_results=metrics,
  paired_executed=sum(p['executed'] for p in pairs),paired_both_parsed=sum(p['semantic_agreement'] is not None for p in pairs),paired_semantic_matches=sum(p['semantic_agreement'] is True for p in pairs),
  paired_text_matches=sum(p['text_agreement'] is True for p in pairs),fixture_cases=sum(len(f['cases']) for f in fixtures.values()),
  fixture_worst_abs=max(c['max_absolute_error'] for f in fixtures.values() for c in f['cases']),
  source_integrity_passed=True,prior_seals_verified=checks,closed_loop_included=False,full_sweep_started=False,
  schedule_authority='frozen-jobs.json and maximum_records=448: all primary, no explicit repeats; inherited v12 maximum_inferences/repeats/prompt_policy fields describe source provenance only',
  candidate='v9d context1024 left active; v8 baseline immutable; launcher/MVP unchanged and inactive',
  limitations=['Same previously evaluated v12 cases intentionally reused; new representation comparison, not fresh holdout accuracy.',
   'Canonical correct prior assistant replies, not model-output feedback; host reducer provides JSON state.',
   'Only two fixed workload chains per length; repeated snapshots correlated.',
   'CPU context4096 overflow-only diagnostic is separate from matched context1024 comparison.',
   'CPU wall includes process/model loading; compare representation costs within backend, not CPU/FPGA speedup.',
   'Prefix reuse disabled: measures cold prefill of each current prompt with warm FPGA model, not cached-history serving.',
   'CPU output tokens retokenized plus EOS; FPGA generated IDs counted exactly.',
   'Offline prompt construction and host reducer time excluded from request timing.'])
 write(work/'comparison-summary.json',summary);write(work/'paired-comparisons.json',pairs)
 columns=['id','case_id','chain_length','step','arm','input_tokens','generated_token_count','executed','correct','category',
  'seconds','inference_seconds','prefill_seconds','decode_seconds']
 with (work/'requests-comparison.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['backend']+columns);w.writeheader()
  for backend,rs in data.items():
   for r in rs:w.writerow(dict(backend=backend,**{k:r.get(k) for k in columns}))
 (work/'report-source.py').write_bytes(Path(__file__).read_bytes())
 write(root/'seal.json',dict(files_sha256={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
