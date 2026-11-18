"""Compact typed FPGA tool calls; no CPU inference, argument repair or output replay."""
import argparse,fcntl,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_v3 import QwenFpga,execute_generated

SYSTEM='Tool: read_linux_file(path:string). Reply only with a compact JSON array ["read_linux_file","path"]. Copy the requested path exactly. No Markdown.'
def prompt_for(query):
    return '<|im_start|>system\n'+SYSTEM+'<|im_end|>\n<|im_start|>user\n'+query+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

class Vocabulary:
    def __init__(self,package):
        self.process=subprocess.Popen([str(package/'qwen_vocab_session'),'/home/ubuntu/sysone-generation/Qwen3-0.6B-Q8_0.gguf'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='ascii',bufsize=1)
        if self.process.stdout.readline().strip()!='READY':
            self.close();raise RuntimeError('Vocabulary session did not initialize')
    def ask(self,line):
        self.process.stdin.write(line+'\n');self.process.stdin.flush()
        result=self.process.stdout.readline()
        if not result:raise RuntimeError('Vocabulary helper exited')
        return result.strip()
    def encode(self,path):return json.loads(self.ask('E\t'+str(path)))
    def piece(self,token):return bytes.fromhex(self.ask('D\t'+str(token)))
    def close(self):
        process=self.process
        if process.poll() is None:
            try:process.stdin.write('Q\n');process.stdin.flush();process.wait(timeout=10)
            except (OSError,subprocess.TimeoutExpired):process.kill();process.wait()
        if process.stdin:process.stdin.close()
        if process.stdout:process.stdout.close()

def typed_value(raw):
    """Syntax-only completion, with no predicted or rewritten argument values."""
    try:text=raw.decode('utf-8').strip()
    except UnicodeDecodeError:return None
    for prefix in ('```json\n','```\n'):
        if text.startswith(prefix):text=text[len(prefix):].strip();break
    try:value=json.loads(text)
    except ValueError:return None
    if type(value) is not list or len(value)!=2 or any(type(v) is not str for v in value):
        raise ValueError('Generated value does not match the two-string tool-call type')
    return value

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--query',required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--max-tokens',type=int,default=64)
    ap.add_argument('--no-prefix-cache',action='store_true',help='Compatibility flag; compact profile always uses cold prefill')
    args=ap.parse_args()
    if not 1<=args.max_tokens<=128:raise ValueError('Output profile')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();started=time.monotonic()
    result=dict(complete=False,query=args.query,backend='Qwen3_0.6B_Q8_weights_FP32_activations_all_model_math_on_FPGA',ARM_model_inference=False,host_model_inference=False,linux_boot_id=boot,wire_format='JSON [function_name, path]',prefix_tokens_reused=0,generated_ids=[],tools_executed=False)
    def save():args.out.write_text(json.dumps(result,indent=2)+'\n')
    save();lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    engine=None;vocab=None
    try:
        setup=time.monotonic();vocab=Vocabulary(args.package)
        prompt=args.out.with_suffix('.prompt.txt');prompt.write_text(prompt_for(args.query),encoding='utf-8')
        ids=vocab.encode(prompt);result.update(prompt_ids=ids,vocabulary_setup_seconds=time.monotonic()-setup)
        if not ids or len(ids)+args.max_tokens>256:raise ValueError('Prompt plus output exceeds context256')
        engine=QwenFpga(args.package,preserve_prefix=False)
        result.update(model_verify_ms=engine.model_verify_ms,model_sha256=engine.manifest['sha256'],resident_weights_verified=True,prefill_batch_size=4)
        engine.begin_prefix(ids,enabled=False)
        prefill=time.monotonic()
        for pos in range(0,len(ids),4):
            group=ids[pos:pos+4];next_id=engine.prefill_batch(group,pos,logits=pos+len(group)==len(ids))
            print(json.dumps(dict(phase='FPGA_batched_prefill',tokens=pos+len(group),total=len(ids))),file=sys.stderr,flush=True)
        result['prefill_seconds']=time.monotonic()-prefill;decode=time.monotonic();raw=b'';value=None
        for index in range(args.max_tokens):
            result['generated_ids'].append(next_id);raw+=vocab.piece(next_id)
            print(json.dumps(dict(phase='FPGA_decode',index=index,token_id=next_id)),file=sys.stderr,flush=True)
            value=typed_value(raw)
            if value is not None:
                result['finish_reason']='typed_json_complete';break
            if next_id in engine.manifest['eos_ids']:raise RuntimeError('EOS without a complete typed call')
            if index+1<args.max_tokens:next_id=engine.step(next_id,len(ids)+index,logits=True)
        result['decode_seconds']=time.monotonic()-decode;result['generated_text']=raw.decode('utf-8')
        if value is None:raise RuntimeError('Output truncated; no tool executed')
        # A wire-format conversion only: both strings come verbatim from the FPGA.
        call,tool_result=execute_generated(json.dumps(dict(name=value[0],arguments=dict(path=value[1]))))
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:raise RuntimeError('Linux boot changed')
        result.update(complete=True,call=call,tool_result=tool_result,tools_executed=True,clock_hz=engine.clock_hz)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if engine is not None:
            result.update(decoder_commands=engine.commands,decoder_layer_calls=engine.layers,decoder_input_tokens=engine.tokens,vocabulary_rows_projected=engine.head_rows,command_timing=engine.command_timing,prefill_groups=engine.prefill_groups,prefill_tokens=engine.prefill_tokens,layer_weight_passes=engine.layer_weight_passes)
            engine.close()
        if vocab is not None:vocab.close()
        lock.close();result['elapsed_seconds']=time.monotonic()-started;save()
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
