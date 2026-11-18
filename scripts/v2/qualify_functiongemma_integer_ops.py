"""Arithmetic qualification of RMS and long-row Q16 attention primitives.

Synthetic vectors and official norm coefficients, not task calibration or a
quantized full model. No board, image, RTL or deadline qualification.
"""
import os
for variable in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[variable]='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch
from safetensors import safe_open

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_integer_ops import RMSPlan,SoftmaxPlan,attention_context


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def nearest(value):return np.sign(value)*np.floor(np.abs(value)+.5)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    rng=np.random.default_rng(2026101805);norms=[]
    with safe_open(args.model/'model.safetensors',framework='pt',device='cpu') as store:
        names=[n for n in store.keys() if n.startswith(('model.layers.0.','model.layers.5.')) and 'norm.weight' in n]
        for name in names:
            weight=store.get_tensor(name).float().numpy().astype(np.float64);width=len(weight)
            for dtype,scale,limit in [(np.int8,.02,127),(np.int16,.0004,32767)]:
                x=rng.integers(-limit,limit+1,size=(16,width),dtype=dtype)
                x[0]=0;x[1]=limit;x[2]=0;x[2,0]=-limit
                real=x.astype(np.float64)*scale
                expected=real/np.sqrt(np.mean(real*real,axis=-1,keepdims=True)+1e-6)*(1+weight)
                output_scale=max(float(np.max(np.abs(expected)))/120,1e-8)
                plan=RMSPlan.compile(weight,scale,output_scale)
                output=plan.run(x).astype(np.int16)
                target=np.clip(nearest(expected/output_scale),-127,127).astype(np.int16)
                error=int(np.max(np.abs(output-target)))
                norms.append(dict(weight=name,input_dtype=np.dtype(dtype).name,channels=width,
                    rows=len(x),input_scale=scale,synthetic_fixture_output_scale=output_scale,
                    max_code_error=error,tolerance_codes=1,passed=error<=1))
                if error>1:raise ValueError('RMS primitive accuracy failure')
    keys=rng.integers(-127,128,size=(2048,256),dtype=np.int16).astype(np.int8)
    query=rng.integers(-127,128,size=(4,256),dtype=np.int16).astype(np.int8)
    values=rng.integers(-127,128,size=(2048,256),dtype=np.int16).astype(np.int8)
    scores=query.astype(np.int32)@keys.astype(np.int32).T
    plan=SoftmaxPlan.compile(.04*.05/16)
    attention=[]
    for i,count in enumerate([2048,512,17,1]):
        mask=np.zeros(2048,dtype=bool);mask[-count:]=True
        p=plan.run(scores[i],mask)
        real=scores[i,mask]*(.04*.05/16);p_float=np.exp(real-real.max());p_float/=p_float.sum()
        expected=np.zeros(2048);expected[mask]=p_float
        probability_error=float(np.max(np.abs(p.astype(np.float64)/65536-expected)))
        context=attention_context(p,values).astype(np.int16)
        target=np.clip(nearest(expected@values.astype(np.float64)),-127,127).astype(np.int16)
        context_error=int(np.max(np.abs(context-target)))
        passed=probability_error<.002 and context_error<=2 and not p[~mask].any()
        attention.append(dict(head_dim=256,keys=2048,allowed=count,probability_bits=16,
            probability_sum_codes=int(p.astype(np.int64).sum()),max_probability_error=probability_error,
            max_context_code_error=context_error,probability_tolerance=.002,context_tolerance_codes=2,passed=passed))
        if not passed:raise ValueError('attention primitive accuracy failure')
    uniform=plan.run(np.zeros(2048,dtype=np.int32),np.ones(2048,dtype=bool))
    assert np.all(uniform==32)
    paths=[Path(__file__),ROOT/'src/sysone/v2/functiongemma_integer_ops.py']
    result=dict(stage='complete',scope='isolated host integer primitives; not full decoder, task accuracy, RTL or board qualification',
        model_sha256=digest(args.model/'model.safetensors'),norm_fixtures=norms,attention_fixtures=attention,
        uniform_2048_preserved=True,runtime_arithmetic='integer sums, isqrt, fixed-point multipliers, integer reciprocal, exponential LUT',
        quantization_calibration='NONE; scales above are synthetic arithmetic fixtures only',
        source_sha256={str(p):digest(p) for p in paths},board_contacted=False,paid_compute=False)
    (args.out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(stage='complete',norm_fixtures=len(norms),max_norm_code_error=max(n['max_code_error'] for n in norms),
        attention_fixtures=len(attention),max_context_code_error=max(a['max_context_code_error'] for a in attention))))


if __name__=='__main__':main()
