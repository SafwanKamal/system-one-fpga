"""Owned localhost-only persistent CPU worker, raw token inputs and exact cache telemetry."""
import hashlib,json,os,socket,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Server:
 def __init__(self,out):
  self.out=out;self.number=0
  exe=ROOT/'build/v2/generation/windows/llama-server.exe';model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
  if sha(model)!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':raise RuntimeError('Model differs')
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  self.url=f'http://127.0.0.1:{port}';self.log=(out/'server.stderr').open('wb');self.stdout=(out/'server.stdout').open('wb')
  cmd=[str(exe),'-m',str(model),'-c','1024','-np','1','-ngl','0','--host','127.0.0.1','--port',str(port),
   '--no-context-shift','--cache-ram','0','--no-cache-idle-slots','--cache-reuse','0','--no-warmup']
  t=time.monotonic();self.proc=subprocess.Popen(cmd,stdout=self.stdout,stderr=self.log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  try:
   for _ in range(600):
    if self.proc.poll() is not None:raise RuntimeError('CPU server exited; inspect stderr')
    try:
     with urllib.request.urlopen(self.url+'/health',timeout=1) as r:
      if json.load(r).get('status')=='ok':break
    except OSError:pass
    time.sleep(.1)
   else:raise TimeoutError('CPU server startup')
  except Exception:self.close();raise
  self.setup=dict(startup_seconds=time.monotonic()-t,server_sha256=sha(exe),command=cmd,pid=self.proc.pid)
  (out/'server-startup.json').write_text(json.dumps(self.setup,indent=2)+'\n')
 def post(self,path,body):
  req=urllib.request.Request(self.url+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=300) as r:return json.load(r)
 def infer(self,j,cache):
  actual=self.post('/tokenize',dict(content=j['prompt'],add_special=False,parse_special=True))['tokens']
  if actual!=j['prompt_ids']:raise RuntimeError('Actual server tokenizer differs from frozen IDs')
  body=dict(prompt=actual,n_predict=j['output_tokens'],temperature=0,seed=0,repeat_penalty=1,
   cache_prompt=cache,id_slot=0,return_tokens=True,stream=False)
  t=time.monotonic();response=self.post('/completion',body);wall=time.monotonic()-t
  self.number+=1;(self.out/f'{j["id"]}.response.json').write_text(json.dumps(response,indent=2)+'\n')
  (self.out/f'{j["id"]}.request.json').write_text(json.dumps(body,indent=2)+'\n')
  tm=response['timings'];cached=tm['cache_n'];evaluated=tm['prompt_n']
  if response.get('truncated') or cached+evaluated!=len(actual):raise RuntimeError('CPU context/accounting mismatch')
  if not cache and cached:raise RuntimeError('CPU cold control reused cache')
  return dict(generated_text=response['content'],terminal_eos=response['stop_type']=='eos',generated_ids=response['tokens'],
   seconds=wall,prefill_seconds=tm['prompt_ms']/1000,decode_seconds=tm['predicted_ms']/1000,
   inference_seconds=(tm['prompt_ms']+tm['predicted_ms'])/1000,
   prefix_tokens_reused=cached,prefill_tokens_evaluated=evaluated,actual_cpu_prompt_ids=actual,
   generated_token_count=tm['predicted_n'],backend='cpu-persistent-server',cache_enabled=cache)
 def close(self):
  if hasattr(self,'proc') and self.proc.poll() is None:
   self.proc.terminate()
   try:self.proc.wait(timeout=15)
   except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=15)
  if hasattr(self,'log'):self.log.close();self.stdout.close()
  (self.out/'server-closed.json').write_text(json.dumps(dict(closed=True))+'\n')
