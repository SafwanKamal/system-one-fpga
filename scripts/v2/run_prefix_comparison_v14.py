"""Cached retention comparison; same frozen logical inputs as v13."""
import argparse,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.prefix_cache_v14 import PrefixCache
from sysone.v2.v8_json_retention_v9 import execute
from run_v8_chain_pilot_v5 import dump
from run_retention_comparison_v13 import CandidateFPGA,fixture,verify,sha
from cpu_prefix_server_v14 import Server
VERSION='v9d-prefix-comparison-v14'

class CachedFPGA(CandidateFPGA):
 def __init__(self,package,out):super().__init__(package,out);self.cache=PrefixCache()
 def reset(self):self.cache.reset()
 def infer(self,j,enabled=True):
  e,v=self.session.engine,self.vocab;t=time.monotonic();ids=v.encode_text(j['prompt'])
  if ids!=j['prompt_ids'] or len(ids)+j['output_tokens']>e.context:raise RuntimeError('Input mismatch/capacity')
  reused=self.cache.begin(e,ids,enabled);before={k:getattr(e,k) for k in ('prefill_tokens','prefill_groups','tokens','layers','layer_weight_passes')}
  for pos in range(reused,len(ids),e.prefill_batch_size):
   group=ids[pos:pos+e.prefill_batch_size];token=e.prefill_batch(group,pos,logits=pos+len(group)==len(ids))
  prefill=time.monotonic()-t;decode=time.monotonic();raw=b'';generated=[];eos=False
  for i in range(j['output_tokens']):
   generated.append(token);raw+=v.piece(token);eos=token in e.manifest['eos_ids']
   if eos:break
   if i+1<j['output_tokens']:token=e.step(token,len(ids)+i,logits=True)
  decode_seconds=time.monotonic()-decode;self.cache.commit(e,ids)
  work={k:getattr(e,k)-n for k,n in before.items()}
  if work['prefill_tokens']!=len(ids)-reused or work['prefill_groups']!=math.ceil((len(ids)-reused)/8):raise RuntimeError('Prefill work did not match skipped tokens')
  return dict(generated_text=raw.decode('utf-8',errors='replace'),terminal_eos=eos,generated_ids=generated,
   generated_token_count=len(generated),seconds=time.monotonic()-t,prefill_seconds=prefill,decode_seconds=decode_seconds,
   inference_seconds=prefill+decode_seconds,prefix_tokens_reused=reused,prefill_tokens_evaluated=work['prefill_tokens'],
   work=work,backend='fpga-v9d',cache_enabled=enabled)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['cpu','fpga'],required=True)
 ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--package',type=Path,required=True)
 ap.add_argument('--qualify',action='store_true');a=ap.parse_args();verify(a.work)
 jobs=json.loads((a.work/'jobs.json').read_text());reference=json.loads((a.work/'cold-reference.json').read_text())
 if a.qualify:jobs=json.loads((a.work/'qualification-jobs.json').read_text())
 a.out.mkdir(parents=True,exist_ok=False);backend=None;lock=None;rows=[];group=None
 try:
  if a.backend=='fpga':
   import fcntl
   from inventory_prefix_v14 import inventory,validate
   from run_v8_benchmark import package_identity
   lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   before=inventory(a.package);validate(before);dump(a.out/'board-before.json',before)
   identity=package_identity(a.package);dump(a.out/'deployment-before.json',identity)
   backend=CachedFPGA(a.package,a.out);dump(a.out/'startup.json',backend.session.setup)
   dump(a.out/'fixture-before.json',fixture(backend,a.package,True));backend.reset()
  else:
   expected=json.loads((a.work/'manifest.json').read_text())['cpu_server_sha256']
   if sha(ROOT/'build/v2/generation/windows/llama-server.exe')!=expected:raise RuntimeError('CPU server binary differs')
   for n,h in json.loads((a.work/'manifest.json').read_text())['cpu_binaries_sha256'].items():
    if sha(ROOT/'build/v2/generation/windows'/n)!=h:raise RuntimeError('CPU DLL differs: '+n)
   backend=Server(a.out)
  if a.qualify:
   # Each case gets a fresh cold control, followed by a cached chronological sequence.
   cold={}
   for j in jobs:
    if j['reference_id'] in cold:continue
    q=dict(j,id='cold-'+j['id']);r=backend.infer(q,False);cold[j['reference_id']]=r
    dump(a.out/(q['id']+'.output.json'),dict(q,**r))
   if a.backend=='fpga':backend.reset()
   previous=None
   for i,j in enumerate(jobs):
    if a.backend=='fpga' and j.get('invalidate'):
     if j['invalidate']=='reset':backend.reset()
     elif j['invalidate']=='tag':backend.session.engine.begin_prefix(j['prompt_ids'],enabled=False)
    enabled=i>0
    r=backend.infer(j,enabled)
    control=cold[j['reference_id']]
    if r['generated_ids']!=control['generated_ids'] or r['generated_text']!=control['generated_text']:raise RuntimeError('Cache qualification changed output: '+j['id'])
    if a.backend=='fpga' and j.get('invalidate') and r['prefix_tokens_reused']:raise RuntimeError('Stale cache reused')
    row=dict(j,**r,exact_control_match=True);rows.append(row);dump(a.out/(j['id']+'.output.json'),row)
   if not any(r['prefix_tokens_reused'] for r in rows):raise RuntimeError('Qualification never reused cache')
   dump(a.out/'qualification.json',dict(passed=True,requests=len(rows),cold_controls=len(cold),exact_ids=True,
    evaluated_tokens=sum(r['prefill_tokens_evaluated'] for r in rows),reused_tokens=sum(r['prefix_tokens_reused'] for r in rows)))
  else:
   trials=('cold','cached') if a.backend=='cpu' else ('cached',)
   # Each case+representation owns the single physical cache until its sequence finishes.
   for case_id in dict.fromkeys(j['case_id'] for j in jobs):
    for arm in ('json','history'):
     sequence=[j for j in jobs if j['case_id']==case_id and j['arm']==arm]
     for trial in trials:
      if a.backend=='fpga':backend.reset()
      first=True
      for original in sequence:
       j=dict(original,id=trial+'-'+original['id'],reference_id=original['id'],trial=trial)
       (a.out/(j['id']+'.prompt.txt')).write_bytes(j['prompt'].encode())
       if not j['capacity_ok']:
        row=dict(j,correct=False,parsed=False,observed=None,category='context-overflow',executed=False,
         seconds=None,prefill_seconds=None,decode_seconds=None,inference_seconds=None,prefix_tokens_reused=0,
         prefill_tokens_evaluated=0,generated_token_count=0)
       else:
        enabled=trial=='cached' and not first
        r=execute(j,lambda req:backend.infer(req,enabled));r.update(executed=True)
        if r['prefix_tokens_reused']+r['prefill_tokens_evaluated']!=j['input_tokens']:raise RuntimeError('Token accounting')
        if first and r['prefix_tokens_reused']:raise RuntimeError('Cache crossed group boundary')
        if a.backend=='fpga':
         old=reference[original['id']]
         if r['generated_ids']!=old['generated_ids']:raise RuntimeError('Cached FPGA output differs from sealed cold control: '+original['id'])
         r['exact_sealed_cold_ids']=True
        row=r;first=False
       rows.append(row);dump(a.out/(j['id']+'.output.json'),row)
       with (a.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
       progress=dict(stage='running',completed=len(rows),total=len(jobs)*len(trials),last_id=j['id'],
        executed=sum(r['executed'] for r in rows),correct=sum(r['correct'] for r in rows),
        reused_tokens=sum(r['prefix_tokens_reused'] for r in rows),full_sweep_started=False)
       dump(a.out/'status.json',progress);print(json.dumps(progress),flush=True)
     if a.backend=='fpga':
      backend.reset();dump(a.out/(case_id+'-'+arm+'.fixture.json'),fixture(backend,a.package));backend.reset()
     verify(a.work)
  if a.backend=='fpga':
   backend.reset();dump(a.out/'fixture-after.json',fixture(backend,a.package,True));after=inventory(a.package);validate(after)
   dump(a.out/'board-after.json',after);after_id=package_identity(a.package);dump(a.out/'deployment-after.json',after_id)
   if before!=after or identity!=after_id:raise RuntimeError('Candidate identity changed')
  verify(a.work)
  if not a.qualify:
   if a.backend=='cpu':
    index={r['id']:r for r in rows}
    for j in jobs:
     cold=index['cold-'+j['id']];cached=index['cached-'+j['id']]
     if cold['executed'] and (cold['generated_ids']!=cached['generated_ids'] or cold['observed']!=cached['observed']):raise RuntimeError('CPU cached output differs from same-server cold control: '+j['id'])
   dump(a.out/'status.json',dict(progress,stage='complete',source_integrity_passed=True))
 except Exception as exc:
  dump(a.out/'status.json',dict(stage='attention',completed=len(rows),error=str(exc),full_sweep_started=False));raise
 finally:
  if backend is not None:backend.close()
  if lock is not None:lock.close()
if __name__=='__main__':main()
