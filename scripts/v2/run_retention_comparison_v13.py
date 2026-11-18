"""Finite v9d representation comparison, separately versioned and resumable only by new runs."""
import argparse,hashlib,json,re,subprocess,sys,time,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from sysone.v2.retention_comparison_v13 import VERSION,CONTEXT
from sysone.v2.v8_json_retention_v9 import execute
from sysone.v2.v8_json_fpga_qualification_v11 import cpu_prompt_file_bytes
from run_v8_chain_pilot_v5 import CPU,FPGA,dump

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(work):
 for n,h in json.loads((work/'source-sha256.json').read_text()).items():
  if sha(work/n)!=h:raise RuntimeError('Frozen source differs: '+n)
  if n.startswith(('src/','scripts/')) and (ROOT/n).exists() and sha(ROOT/n)!=h:
   raise RuntimeError('Executing source differs: '+n)

class TimedCPU(CPU):
 def __init__(self,package,out,context):super().__init__(package,out);self.context=context
 def infer(self,job):
  path=self.out/(job['id']+'.prompt.txt');path.write_bytes(cpu_prompt_file_bytes(job['prompt']))
  cmd=[str(ROOT/'build/v2/generation/windows/llama-completion.exe'),'-m',str(self.model),'-f',str(path),
   '-n',str(job['output_tokens']),'-c',str(self.context),'-ngl','0','--temp','0','--seed','0','--repeat-penalty','1',
   '--no-conversation','--no-display-prompt','--no-escape','--no-warmup','--verbose-prompt','--no-context-shift']
  t=time.monotonic();p=subprocess.run(cmd,capture_output=True,timeout=300);wall=time.monotonic()-t
  (self.out/(job['id']+'.stdout')).write_bytes(p.stdout);(self.out/(job['id']+'.stderr')).write_bytes(p.stderr)
  if p.returncode:raise RuntimeError('CPU failed: '+job['id'])
  err=p.stderr.decode(errors='replace');ids=[int(n) for n in re.findall(r"\b(\d+)\s*->\s*'",err)]
  if ids!=job['prompt_ids']:raise RuntimeError('Actual CLI token mismatch')
  raw=p.stdout.decode().replace('\r\n','\n');eos=' [end of text]' in raw
  text=raw.split(' [end of text]',1)[0] if eos else raw.rstrip('\n')
  def timing(label):
   m=re.search(label+r'\s*=\s*([0-9.]+) ms',err)
   if not m:raise RuntimeError('Missing CPU timing: '+label)
   return float(m[1])/1000
  prefill=timing('prompt eval time');decode=timing(r'(?<!prompt )eval time')
  return dict(generated_text=text,terminal_eos=eos,seconds=wall,prefill_seconds=prefill,decode_seconds=decode,
   inference_seconds=prefill+decode,load_seconds=timing('load time'),actual_cpu_prompt_ids=ids,
   generated_token_count=len(self.vocab.encode_text(text))+int(eos),
   output_count_method='retokenized output plus terminal EOS; not a CPU generated-ID trace',
   context_used=self.context,prefix_tokens_reused=0,backend='cpu')

class CandidateFPGA(FPGA):
 def __init__(self,package,out):
  from sysone.v2.qwen_fpga_runtime_v9d import QwenFpga
  from sysone.v2.qwen_tokenizer_v1 import Vocabulary
  from types import SimpleNamespace
  t=time.monotonic();self.vocab=Vocabulary(package)
  try:e=QwenFpga(package,preserve_prefix=False)
  except Exception:self.vocab.close();raise
  self.session=SimpleNamespace(engine=e,vocab=self.vocab,setup=dict(startup_wall_seconds=time.monotonic()-t,
    model_verify_ms=e.model_verify_ms,model_verify_method=e.model_verify_method))
 def infer(self,job):
  r=super().infer(job);r['generated_token_count']=r.pop('output_tokens');r['backend']='fpga-v9d'
  r['inference_seconds']=r['prefill_seconds']+r['decode_seconds'];r['context_used']=CONTEXT
  r['output_count_method']='exact FPGA generated IDs including EOS';return r
 def close(self):self.session.engine.close();self.vocab.close()

def fixture(backend,package,long=False):
 import smoke_qwen_fpga_v9d as smoke
 e=backend.session.engine;smoke.CASES.clear();block=package/'block-fixture'
 ids=json.loads((block/'manifest.json').read_text())['ids']
 for start,count in [(0,8),(0,1),(1,7)]:
  smoke.prefill(e,ids,start,count)
  for lane in range(count):
   e.command(10,layer=lane);smoke.compare(e,block/f'expected-{start+lane}.bin',dict(kind='block',position=start+lane))
 if long:
  path=package/'long-fixture';ids=json.loads((path/'manifest.json').read_text())['ids']
  for start in range(0,len(ids),8):
   count=min(8,len(ids)-start);smoke.prefill(e,ids,start,count)
   for lane in range(count):
    e.command(10,layer=lane);smoke.compare(e,path/f'expected-{start+lane}.bin',dict(kind='long-prefill',position=start+lane))
  for pos,token in enumerate(ids):
   e.command(1,page=e.manifest['embedding']+token*e.embedding_row_bytes,position=pos)
   e._copy_words(smoke.DESCRIPTOR,struct.pack('<11I',*e.manifest['layer_offsets'][0]))
   e.command(2,page=smoke.DESCRIPTOR,layer=0,position=pos);e.command(5)
   smoke.compare(e,path/f'expected-{pos}.bin',dict(kind='long-decode',position=pos))
 return dict(passed=True,cases=list(smoke.CASES),long=long)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['cpu','fpga'],required=True)
 ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--package',type=Path,required=True);ap.add_argument('--extended',action='store_true');a=ap.parse_args()
 verify(a.work);spec=json.loads((a.work/'manifest.json').read_text());jobs=json.loads((a.work/'frozen-jobs.json').read_text())
 if a.extended:
  if a.backend!='cpu':raise ValueError('Extended context is CPU-only diagnostic')
  jobs=[j for j in jobs if not j['capacity_ok']]
 if a.backend=='cpu' and sha(ROOT/'build/v2/generation/windows/llama-completion.exe')!=spec['cpu_cli_sha256']:raise RuntimeError('CPU CLI changed')
 a.out.mkdir(parents=True,exist_ok=False);rows=[];backend=None;lock=None
 try:
  if a.backend=='fpga':
   import fcntl
   from inventory_retention_v13 import inventory,validate
   from run_v8_benchmark import package_identity
   lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   before=inventory(a.package);validate(before);dump(a.out/'board-before.json',before)
   ident=package_identity(a.package);dump(a.out/'deployment-before.json',ident)
   backend=CandidateFPGA(a.package,a.out);dump(a.out/'startup.json',backend.session.setup)
   dump(a.out/'fixture-before.json',fixture(backend,a.package,True))
  else:backend=TimedCPU(a.package,a.out,4096 if a.extended else CONTEXT)
  for i,j in enumerate(jobs):
   ids=backend.vocab.encode_text(j['prompt'])
   if ids!=j['prompt_ids']:raise RuntimeError('Frozen input tokenizer mismatch')
   (a.out/(j['id']+'.prompt.txt')).write_bytes((j['prompt']+'\n' if a.backend=='cpu' else j['prompt']).encode())
   if not j['capacity_ok'] and not a.extended:
    row=dict(j,correct=False,parsed=False,observed=None,category='context-overflow',executed=False,
     seconds=None,inference_seconds=None,prefill_seconds=None,decode_seconds=None,generated_token_count=0,
     backend=a.backend,backend_input_ids=ids)
   else:
    row=execute(j,backend.infer);row.update(executed=True,backend_input_ids=ids,extended_cpu_only=a.extended)
   dump(a.out/(j['id']+'.output.json'),row)
   with (a.out/'requests.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
   rows.append(row);progress=dict(stage='running',completed=len(rows),total=len(jobs),last_id=j['id'],
    correct=sum(r['correct'] for r in rows),executed=sum(r['executed'] for r in rows),
    overflow=sum(not r['executed'] for r in rows),full_sweep_started=False)
   dump(a.out/'status.json',progress);print(json.dumps(progress),flush=True)
   if i+1==len(jobs) or jobs[i+1]['case_id']!=j['case_id']:
    verify(a.work)
    if a.backend=='fpga':dump(a.out/(j['case_id']+'.fixture.json'),fixture(backend,a.package))
  if a.backend=='fpga':
   dump(a.out/'fixture-after.json',fixture(backend,a.package,True));after=inventory(a.package);validate(after)
   dump(a.out/'board-after.json',after);newident=package_identity(a.package);dump(a.out/'deployment-after.json',newident)
   if before!=after or ident!=newident:raise RuntimeError('Live candidate identity changed')
  verify(a.work);dump(a.out/'status.json',dict(progress,stage='complete',source_integrity_passed=True))
 except Exception as exc:
  dump(a.out/'status.json',dict(stage='attention',completed=len(rows),error=str(exc),full_sweep_started=False));raise
 finally:
  if backend is not None:backend.close()
  if lock is not None:lock.close()
if __name__=='__main__':main()
