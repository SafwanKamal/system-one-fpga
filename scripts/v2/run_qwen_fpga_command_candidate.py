"""v9e candidate: compact typed FPGA tool calls; no CPU inference, argument repair or output replay.

Identical prompt, parser and timing boundaries to run_qwen_fpga_command_v7.py.
"""
import argparse,fcntl,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.qwen_fpga_runtime_candidate import QwenFpga,execute_generated

SYSTEM='Tool: read_linux_file(path:string). Reply only with a compact JSON array ["read_linux_file","path"]. Copy the requested path exactly. No Markdown.'
def prompt_for(query):
    return '<|im_start|>system\n'+SYSTEM+'<|im_end|>\n<|im_start|>user\n'+query+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

from sysone.v2.qwen_tokenizer_v1 import Vocabulary

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
    result=dict(complete=False,query=args.query,backend='Qwen_Q8_weights_block32_INT8_dots_FP32_norm_attention_all_NN_on_FPGA',ARM_model_inference=False,host_model_inference=False,linux_boot_id=boot,wire_format='JSON [function_name, path]',prefix_tokens_reused=0,generated_ids=[],tools_executed=False)
    def save():args.out.write_text(json.dumps(result,indent=2)+'\n')
    save();lock=Path('/run/lock/sysone-inference.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    engine=None;vocab=None
    try:
        # Independent startup operations overlap inside the cold-call timer.
        # The engine verifies every resident weight byte before any NN command.
        setup=time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as startup:
            engine_future=startup.submit(QwenFpga,args.package,preserve_prefix=False)
            try:
                vocab=Vocabulary(args.package)
                prompt=args.out.with_suffix('.prompt.txt');prompt.write_text(prompt_for(args.query),encoding='utf-8')
                ids=vocab.encode(prompt);result.update(prompt_ids=ids,vocabulary_setup_seconds=time.monotonic()-setup)
            finally:
                engine=engine_future.result()
        if not ids or len(ids)+args.max_tokens>engine.context:raise ValueError('Prompt plus output exceeds FPGA context')
        result['startup_wall_seconds']=time.monotonic()-setup
        result['command_poll_interval_seconds']=0.00005
        result.update(dma_abi=engine.dma_abi,rope_copy_ms=engine.rope_copy_ms,rope_copy_mode=engine.rope_copy_mode,model_verify_ms=engine.model_verify_ms,model_verify_method=engine.model_verify_method,model_sha256=engine.manifest['sha256'],resident_weights_verified=True,prefill_batch_size=engine.prefill_batch_size)
        engine.begin_prefix(ids,enabled=False)
        prefill=time.monotonic()
        for pos in range(0,len(ids),engine.prefill_batch_size):
            group=ids[pos:pos+engine.prefill_batch_size];next_id=engine.prefill_batch(group,pos,logits=pos+len(group)==len(ids))
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
        result.update(complete=True,call=call,tool_result=tool_result,tools_executed=True,clock_hz=engine.clock_hz,memory_clock_hz=engine.memory_clock_hz)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        if engine is not None:
            result.update(decoder_commands=engine.commands,decoder_layer_calls=engine.layers,decoder_input_tokens=engine.tokens,vocabulary_rows_projected=engine.head_rows,command_timing=engine.command_timing,prefill_groups=engine.prefill_groups,prefill_tokens=engine.prefill_tokens,layer_weight_passes=engine.layer_weight_passes)
            engine.close()
        if vocab is not None:vocab.close()
        lock.close();result['elapsed_seconds']=time.monotonic()-started;save()
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
