"""Compare independent streamed float decoder with official eager PyTorch.

One authored function-call fixture; token-prefix/numerical evidence only.
Do not describe this as BFCL scoring, integer accuracy or FPGA qualification.
"""
import os
for variable in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[variable]='1'
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_streaming_float import StreamingFloatGemma


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--tokens',type=int,default=32)
    args=ap.parse_args()
    if not 1<=args.tokens<=256:raise ValueError('invalid work cap')
    args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    tools=[dict(type='function',function=dict(name='sum_values',description='Return the sum of two integers.',
        parameters=dict(type='object',properties=dict(left=dict(type='integer'),right=dict(type='integer')),
        required=['left','right'])))]
    messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),
        dict(role='user',content='Use sum_values to add 2 and 3.')]
    text=tok.apply_chat_template(messages,tools=tools,add_generation_prompt=True,tokenize=False)
    prompt=tok.encode(text,add_special_tokens=False)
    result=dict(stage='starting',scope='one authored fixture, complete floating decoder with all 18 blocks and full vocabulary; no task or hardware qualification',
        model_sha256=digest(args.model/'model.safetensors'),oracle='official AutoModelForCausalLM eager FP32',
        reference='independent layer-streamed NumPy float64 with float32 rotary phases',
        tolerance=dict(atol=.02,rtol=.002,exact_greedy_tokens_required=True),
        prompt_tokens=prompt,token_cap=args.tokens,board_contacted=False)
    def save():(args.out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    save()
    model=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,dtype=torch.float32,attn_implementation='eager').eval().requires_grad_(False)
    stops=set(list(model.config.eos_token_id)+[tok.convert_tokens_to_ids('<end_of_turn>')])
    oracle=[];cache=None;inputs=prompt
    with torch.inference_mode():
        for index in range(args.tokens):
            output=model.model(input_ids=torch.tensor([inputs]),past_key_values=cache,use_cache=True)
            cache=output.past_key_values
            logits=model.lm_head(output.last_hidden_state[:,-1,:])[0]
            token=int(logits.argmax())
            oracle.append(dict(token=token,hidden=output.last_hidden_state[0,-1].numpy().copy(),logits=logits.numpy().copy()))
            if token in stops:break
            inputs=[token]
    del output,logits,cache,model;gc.collect()
    print(json.dumps(dict(stage='official_reference_captured',tokens=len(oracle))),flush=True)
    reference=StreamingFloatGemma(args.model);states=None;inputs=prompt;checks=[]
    for index,expected in enumerate(oracle):
        logits,states,hidden=reference.step(inputs,states)
        token=int(logits.argmax())
        hidden_pass=bool(np.allclose(hidden,expected['hidden'],atol=.02,rtol=.002))
        logits_pass=bool(np.allclose(logits,expected['logits'],atol=.02,rtol=.002))
        check=dict(index=index,token=token,expected_token=expected['token'],exact_token=token==expected['token'],
            hidden_max_abs_error=float(np.max(np.abs(hidden-expected['hidden']))),
            logits_max_abs_error=float(np.max(np.abs(logits-expected['logits']))),
            hidden_pass=hidden_pass,logits_pass=logits_pass)
        checks.append(check);result['checks']=checks;save();print(json.dumps(check),flush=True)
        if token!=expected['token'] or not hidden_pass or not logits_pass:
            result['stage']='failed';save();raise ValueError('whole float decoder qualification failed')
        inputs=[token]
    sources=[Path(__file__),ROOT/'src/sysone/v2/functiongemma_streaming_float.py',
        ROOT/'src/sysone/v2/functiongemma_float_ops.py',ROOT/'src/sysone/v2/functiongemma_profile.py']
    (args.out/'sources').mkdir()
    for path in sources:(args.out/'sources'/path.name).write_bytes(path.read_bytes())
    result.update(stage='complete',generated_ids=[r['token'] for r in checks],
        raw_output=tok.decode([r['token'] for r in checks],skip_special_tokens=False),
        ended_on_stop=checks[-1]['token'] in stops,full_vocabulary_rows=reference.config['vocab_size'],
        source_sha256={str(p):digest(p) for p in sources})
    save();print(json.dumps(dict(stage='complete',tokens=len(checks),ended_on_stop=result['ended_on_stop'])))


if __name__=='__main__':main()
