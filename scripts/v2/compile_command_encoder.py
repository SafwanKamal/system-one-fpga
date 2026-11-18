"""Compile a command encoder with existing integer/image references, offline only."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np
import torch
from transformers import AutoConfig,AutoTokenizer

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.int_encoder import FloatEncoder,IntEncoder
from sysone.v2.ddr_image import compile_image,ImageMachine
from sysone.v2.command_codec import FIELDS,constrained_fields,decode
from sysone.v2.command_task import canonical,evaluate
from sysone.v2.command_metrics import process_memory


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--calibration-examples',type=int,default=32)
    ap.add_argument('--eval-examples',type=int,default=64)
    ap.add_argument('--exact-cases',type=int,default=2)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1)
    started=time.perf_counter()
    receipt=dict(stage='loading',execution='host_integer_simulation_only',board_contacted=False,
        checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()})
    dump(args.out/'receipt.json',receipt)
    saved=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
    if saved['fields']!=FIELDS:
        raise ValueError('checkpoint codec mismatch')
    fields=sorted(FIELDS)
    state={k:v for k,v in saved['state_dict'].items() if k.startswith('encoder.')}
    # All fields use the same pooled vector. Concatenating their matrix rows
    # preserves arithmetic and uses one head section rather than twelve.
    labels={'cmd':[field+':'+v for field in fields for v in FIELDS[field]]}
    names={}
    offset=0
    for field in fields:
        names[field]=dict(head='cmd',offset=offset,count=len(FIELDS[field]))
        offset+=len(FIELDS[field])
    for part in ('weight','bias'):
        state[f'intent.cmd.{part}']=torch.cat([saved['state_dict'][f'heads.{field}.{part}'] for field in fields],dim=0)
    cfg=AutoConfig.from_pretrained(args.model,local_files_only=True)
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    fe=FloatEncoder(state,cfg,{'intent':labels,'slots':{},'pair':{}})
    def rows(split):
        values=[json.loads(line) for line in (args.data/f'{split}.jsonl').read_text().splitlines()]
        random.Random(20261017).shuffle(values)
        return values
    calibration=rows('train')[:args.calibration_examples]
    fe.trace={}
    for row in calibration:
        tokens=tok.encode(row['text'])
        if len(tokens)>128:
            raise ValueError('oversize input')
        fe.hidden(np.asarray(tokens))
    trace=fe.trace
    fe.trace=None
    dump(args.out/'calibration.json',dict(source='train only',case_ids=[r['id'] for r in calibration],
        range_max={k:float(max(v)) for k,v in trace.items()}))
    ie=IntEncoder(fe,trace)
    image,manifest=compile_image(ie,'command-bert-pilot',{'intent':labels,'slots':{},'pair':{}},
                               base=0x60000000,tile_in=16,tile_out=32,max_tokens=128)
    (args.out/'candidate.img').write_bytes(image)
    manifest.update(checkpoint_sha256=receipt['checkpoint_sha256'],command_field_to_head=names,
                    deployment_status='OFFLINE ONLY; never load into current fixed buffer layout')
    dump(args.out/'manifest.json',manifest)
    end=0x60000000+len(image)
    next64=lambda x:(x+65535)//65536*65536
    ids=next64(end)
    hidden=next64(ids+128*2)
    mailbox=next64(hidden+128*cfg.hidden_size)
    layout=dict(image_end=hex(end),proposed_ids=hex(ids),proposed_hidden=hex(hidden),
        proposed_mailbox=hex(mailbox),mailbox_bytes=512*1024,
        fits_reserved_256MiB=mailbox+512*1024<=0x70000000,
        overlaps_deployed_ids=end>0x62100000,overlaps_deployed_hidden=end>0x62101000,
        status='sizing proposal only; firmware/module/client ABI must be rebuilt and qualified together')
    dump(args.out/'layout-proposal.json',layout)
    machine=ImageMachine(image)
    cases=rows('diagnostic')[:args.eval_examples]
    predictions=[]
    exact=[]
    for index,row in enumerate(cases):
        tokens=np.asarray(tok.encode(row['text']))
        start=time.perf_counter_ns()
        hidden_codes=ie.hidden(tokens)
        positions=np.arange(len(tokens))
        scores={}
        logits,scales=ie.head_logits(hidden_codes,'intent','cmd',positions)
        combined=logits*scales
        for field,info in names.items():
            scores[field]=combined[info['offset']:info['offset']+info['count']].tolist()
        prediction=dict(id=row['id'],output=canonical(decode(constrained_fields(scores))),
                        latency_ms=(time.perf_counter_ns()-start)/1e6)
        predictions.append(prediction)
        with (args.out/'requests.jsonl').open('a',encoding='utf-8') as journal:
            journal.write(json.dumps(prediction)+'\n')
        if index<args.exact_cases:
            actual=machine.hidden(tokens)
            if not np.array_equal(actual,hidden_codes):
                raise ValueError('ImageMachine hidden mismatch')
            checked=0
            reference,rs=ie.head_logits(hidden_codes,'intent','cmd',positions)
            value,vs=machine.head_logits(actual,'intent.cmd',positions)
            if not np.array_equal(value,reference) or not np.allclose(vs,rs,rtol=1e-6):
                raise ValueError('ImageMachine head mismatch')
            checked+=value.size
            exact.append(dict(id=row['id'],hidden_elements=actual.size,integer_logits=checked))
            dump(args.out/'exact-checks.json',exact)
        print(json.dumps(dict(case=index+1,total=len(cases),elapsed_seconds=time.perf_counter()-started)),flush=True)
    result=evaluate(cases,predictions)
    result.update(execution='host_integer_simulation_only',not_board_latency=True,calibration_examples=len(calibration))
    dump(args.out/'summary.json',result)
    receipt.update(stage='complete',elapsed_seconds=time.perf_counter()-started,memory=process_memory(),
                   image_sha256=manifest['sha256'],exact_cases=len(exact))
    dump(args.out/'receipt.json',receipt)


if __name__=='__main__':
    main()
