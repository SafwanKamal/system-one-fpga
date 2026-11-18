"""Simulate isolated 6/7/8-bit row unpacking; no board or deployed RTL changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from safetensors import safe_open

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_packed_weights import PackedWeights,pack_codes


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    compiler=shutil.which('iverilog');runtime=shutil.which('vvp')
    if not compiler or not runtime:raise RuntimeError('Icarus iverilog/vvp required')
    args.out.mkdir(parents=True,exist_ok=False)
    source_paths=[Path(__file__),ROOT/'rtl/v2/common/packed_weight_row16.sv',
        ROOT/'rtl/v2/test/packed_weight_row16_tb.sv',ROOT/'src/sysone/v2/functiongemma_packed_weights.py']
    model_sha=digest(args.model/'model.safetensors')
    reference=json.loads((ROOT/'build/v2/functiongemma-storage-v2/storage-plan.json').read_text(encoding='utf-8'))
    if model_sha!=reference['model_sha256']:raise ValueError('official weight parent differs')
    real=[]
    with safe_open(str(args.model/'model.safetensors'),framework='pt',device='cpu') as tensors:
        embedding=tensors.get_slice('model.embed_tokens.weight')
        for row in [0,31,32,262143]:
            real.append(embedding[row:row+1,:].float().numpy().astype(np.float64).reshape(40,16))
    results=[]
    for bits in [6,7,8]:
        rng=np.random.default_rng(29320+bits);limit=1<<(bits-1)
        # Exhaust every representable signed code plus mixed signs and extremes.
        rows=[np.resize(np.arange(-limit,limit,dtype=np.int16),16*((2*limit+15)//16)).reshape(-1,16),
            np.tile(np.array([-limit,-1,0,limit-1]*4,dtype=np.int16),(8,1)),
            rng.integers(-limit,limit,size=(1024,16),dtype=np.int16)]
        for values in real:
            scales=np.maximum(np.max(np.abs(values),axis=1,keepdims=True)/(limit-1),1e-12)
            rows.append(np.clip(np.rint(values/scales),-limit,limit-1).astype(np.int16))
        records=[]
        for row in np.concatenate(rows):records.append((pack_codes(row,bits),row))
        # Read actual serialized tile bytes, including padded rows/columns and
        # the row31/32 output-tile boundary, instead of only direct row packing.
        codes=rng.integers(-limit,limit,size=(37,19),dtype=np.int16)
        matrix=PackedWeights.from_codes(codes,bits);row_bytes=2*bits
        for nt in range(matrix.output_tiles):
            for kt in range(matrix.input_tiles):
                for within in range(32):
                    start=(nt*matrix.input_tiles+kt)*matrix.tile_bytes+within*row_bytes
                    expected=np.zeros(16,dtype=np.int16);row=nt*32+within;col=kt*16
                    if row<37:expected[:max(0,min(16,19-col))]=codes[row,col:col+16]
                    records.append((matrix.data[start:start+row_bytes],expected))
        vectors=args.out/f'rows-{bits}.hex'
        with vectors.open('w',encoding='ascii') as stream:
            for packed,expected in records:
                payload=int.from_bytes(packed,'little')
                # Nonzero unused high input bits must never enter decoded codes.
                payload|=(int.from_bytes(rng.bytes(16),'little')>>(16*bits))<<(16*bits)
                golden=int.from_bytes(expected.astype(np.int8).tobytes(),'little')
                stream.write(f'{golden:032x}{payload:032x}\n')
        executable=args.out/f'unpack-{bits}.vvp'
        command=[compiler,'-g2012','-s','packed_weight_row16_tb',
            f'-Ppacked_weight_row16_tb.BITS={bits}','-o',str(executable),
            str(source_paths[1]),str(source_paths[2])]
        compile_run=subprocess.run(command,capture_output=True,text=True,check=True)
        simulation=subprocess.run([runtime,str(executable),f'+vectors={vectors.resolve()}',
            f'+count={len(records)}'],capture_output=True,text=True,check=True,timeout=60)
        (args.out/f'simulation-{bits}.log').write_text(compile_run.stdout+compile_run.stderr+
            simulation.stdout+simulation.stderr,encoding='utf-8')
        if f'PASS bits={bits} rows={len(records)}' not in simulation.stdout:raise ValueError('missing pass marker')
        results.append(dict(bits=bits,rows=len(records),passed=True,output=simulation.stdout.strip(),
            vectors_sha256=digest(vectors),executable_sha256=digest(executable)))
    result=dict(stage='complete',scope='isolated RTL simulation only',board_contacted=False,
        deployed_design_changed=False,synthesis_or_timing_qualified=False,model_sha256=model_sha,
        quantization_quality_qualified=False,source_sha256={str(p.relative_to(ROOT)):digest(p) for p in source_paths},
        tools=dict(iverilog=compiler,vvp=runtime),checks=results,
        remaining=['DDR byte alignment and fetch','dot-product/requantization integration',
            'whole-model integer accuracy','synthesis/timing','compiler/R5 ABI and board qualification'])
    (args.out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(stage='complete',checks=results)))


if __name__=='__main__':main()
