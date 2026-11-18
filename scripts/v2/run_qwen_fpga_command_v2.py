"""Run one real Qwen3-0.6B FPGA-generated tool command. No CPU model fallback."""
import argparse,fcntl,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v2 import QwenFpga,prompt_for,execute_generated

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--query',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--max-tokens',type=int,default=64);p.add_argument('--no-prefix-cache',action='store_true');args=p.parse_args()
 if not 1<=args.max_tokens<=128:raise ValueError('Output profile')
 args.out.parent.mkdir(parents=True,exist_ok=True);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();started=time.monotonic();helper=args.package/'qwen_vocab';model='/home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf';prompt=args.out.with_suffix('.prompt.txt');prompt.write_text(prompt_for(args.query),encoding='utf-8');ids=json.loads(subprocess.check_output([str(helper),model,'--encode',str(prompt)]))
 if not ids or len(ids)+args.max_tokens>256:raise ValueError('Prompt plus output exceeds FPGA context256')
 result=dict(complete=False,query=args.query,backend='Qwen3_0.6B_Q8_weights_FP32_activations_all_model_math_on_FPGA',ARM_model_inference=False,host_model_inference=False,prompt_ids=ids,generated_ids=[],linux_boot_id=boot)
 def save():args.out.write_text(json.dumps(result,indent=2)+'\n')
 save();lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX);engine=None
 try:
  engine=QwenFpga(args.package,preserve_prefix=True);result['model_verify_ms']=engine.model_verify_ms
  reused=engine.begin_prefix(ids,enabled=not args.no_prefix_cache);result['prefix_tokens_reused']=reused
  print(json.dumps(dict(phase='FPGA_prefix',tokens_reused=reused,prompt_tokens=len(ids))),file=sys.stderr,flush=True)
  for pos in range(reused,len(ids)):
   token=ids[pos]
   next_id=engine.step(token,pos,logits=pos==len(ids)-1)
   if (pos+1)%8==0:print(json.dumps(dict(phase='FPGA_prefill',tokens=pos+1,total=len(ids))),file=sys.stderr,flush=True)
  generated=[]
  for i in range(args.max_tokens):
   generated.append(next_id);result['generated_ids']=generated;save()
   print(json.dumps(dict(phase='FPGA_decode',index=i,token_id=next_id)),file=sys.stderr,flush=True)
   if next_id in engine.manifest['eos_ids']:break
   if i+1<args.max_tokens:next_id=engine.step(next_id,len(ids)+i,logits=True)
  if generated[-1] not in engine.manifest['eos_ids']:raise RuntimeError('Output truncated; no tool executed')
  text=subprocess.check_output([str(helper),model,'--decode',*map(str,generated)]).decode('utf-8');result['generated_text']=text;call,tool_result=execute_generated(text);result.update(complete=True,call=call,tool_result=tool_result,tools_executed=True,decoder_commands=engine.commands,decoder_layer_calls=engine.layers,decoder_input_tokens=engine.tokens,vocabulary_rows_projected=engine.head_rows,clock_hz=engine.clock_hz)
  if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:raise RuntimeError('Linux boot changed')
  if not args.no_prefix_cache:engine.commit_prefix()
 except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
 finally:
  if engine is not None:
   result.update(decoder_commands=engine.commands,decoder_layer_calls=engine.layers,decoder_input_tokens=engine.tokens,vocabulary_rows_projected=engine.head_rows,command_timing=engine.command_timing)
   engine.close()
  lock.close();result['elapsed_seconds']=time.monotonic()-started;save()
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
