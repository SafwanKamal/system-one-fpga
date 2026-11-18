"""CPU task fine-tuning pilot. No board access or hard deadline claim.

Shares task/codec with FunctionGemma; all-head predictions are validated strictly.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from sysone.v2.command_codec import FIELDS, encode, decode, constrained_fields
from sysone.v2.command_task import canonical, evaluate
from sysone.v2.checkpoint_io import write_checkpoint
from sysone.v2.command_metrics import process_memory


class CommandEncoder(nn.Module):
    def __init__(self, path):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(path, local_files_only=True)
        self.heads = nn.ModuleDict({k:nn.Linear(self.encoder.config.hidden_size,len(v)) for k,v in FIELDS.items()})

    def forward(self, tokens):
        hidden = self.encoder(**tokens).last_hidden_state
        mask = tokens['attention_mask'].unsqueeze(-1)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
        return {k:h(pooled) for k,h in self.heads.items()}


def read(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--model',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--epochs',type=int,default=1)
    ap.add_argument('--batch-size',type=int,default=8)
    ap.add_argument('--max-train',type=int,default=0)
    ap.add_argument('--max-eval',type=int,default=0)
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--quantize',action='store_true')
    ap.add_argument('--checkpoint',type=Path,help='Evaluate a saved checkpoint without further training')
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(20261017)
    rng=random.Random(20261017)
    manifest=dict(arguments=vars(args).copy(), seed=20261017, stage='starting',
                  scope='synthetic_pipeline_pilot_not_model_selection', device='cpu',
                  schema_sha256=hashlib.sha256((args.data/'schema.json').read_bytes()).hexdigest(),
                  data_hashes={s:hashlib.sha256((args.data/f'{s}.jsonl').read_bytes()).hexdigest()
                               for s in ('train','dev','diagnostic')})
    manifest['arguments']={k:str(v) if isinstance(v,Path) else v for k,v in manifest['arguments'].items()}
    dump(args.out/'run.json',manifest)
    source_files=[Path(__file__), ROOT/'src/sysone/v2/command_task.py', ROOT/'src/sysone/v2/command_codec.py', ROOT/'src/sysone/v2/command_metrics.py']
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    (args.out/'sources').mkdir()
    for p in source_files:
        (args.out/'sources'/p.name).write_bytes(p.read_bytes())
    start=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    model=CommandEncoder(args.model)
    if args.checkpoint:
        saved=torch.load(args.checkpoint,map_location='cpu',weights_only=False)
        if saved['fields'] != FIELDS:
            raise ValueError('checkpoint field schema differs')
        model.load_state_dict(saved['state_dict'],strict=True)
        manifest['parent_checkpoint_sha256']=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        manifest['parent_training_manifest']=saved['manifest']
    manifest.update(load_seconds=time.perf_counter()-start,parameters=sum(p.numel() for p in model.parameters()))
    manifest['memory_after_load']=process_memory()
    train=read(args.data/'train.jsonl')
    rng.shuffle(train)
    if args.max_train:
        train=train[:args.max_train]
    def tokens(rows):
        result=tok([r['text'] for r in rows],padding=True,truncation=False,return_tensors='pt')
        if result['input_ids'].shape[1]>128:
            raise ValueError('input exceeds encoder profile; no silent truncation')
        return result
    opt=torch.optim.AdamW(model.parameters(),lr=3e-5)
    steps=0
    train_start=time.perf_counter()
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as journal:
        for epoch in range(0 if args.checkpoint else args.epochs):
            model.train()
            rng.shuffle(train)
            for offset in range(0,len(train),args.batch_size):
                batch=train[offset:offset+args.batch_size]
                opt.zero_grad(set_to_none=True)
                logits=model(tokens(batch))
                labels=[encode(r['gold']) for r in batch]
                loss=sum(nn.functional.cross_entropy(logits[k],torch.tensor([choices.index(y[k]) for y in labels]))
                         for k,choices in FIELDS.items()) / len(FIELDS)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
                opt.step()
                steps+=1
                entry=dict(epoch=epoch,step=steps,loss=loss.item(),elapsed_seconds=time.perf_counter()-train_start)
                journal.write(json.dumps(entry)+'\n'); journal.flush()
                if steps%10==0:
                    print(json.dumps(entry),flush=True)
    manifest.update(training_seconds=time.perf_counter()-train_start,training_examples=0 if args.checkpoint else len(train),steps=steps,stage='trained')
    dump(args.out/'run.json',manifest)
    write_checkpoint(dict(state_dict=model.state_dict(),fields=FIELDS,manifest=manifest),args.out/'checkpoint.pt',torch.save)
    manifest['checkpoint_sha256']=hashlib.sha256((args.out/'checkpoint.pt').read_bytes()).hexdigest()
    del opt
    def score(current, split, variant):
        cases=read(args.data/f'{split}.jsonl')
        if args.max_eval:
            # Deterministic stratified subset, not just first API/asset in file.
            local_rng=random.Random(20261017)
            local_rng.shuffle(cases)
            cases=cases[:args.max_eval]
        predictions=[]
        current.eval()
        # Batch=1 so each resident per-request latency is directly measured.
        with (args.out/f'{variant}-{split}-requests.jsonl').open('w',encoding='utf-8') as journal:
            for case in cases:
                row={'id':case['id']}
                t=time.perf_counter_ns()
                try:
                    with torch.inference_mode():
                        logits=current(tokens([case]))
                    row['unconstrained_fields']={k:FIELDS[k][int(v.argmax(-1)[0])] for k,v in logits.items()}
                    fields=constrained_fields({k:v[0].tolist() for k,v in logits.items()})
                    row['fields']=fields
                    row['output']=canonical(decode(fields))
                except ValueError as exc:
                    row.update(decode_error=str(exc),output=json.dumps(row.get('fields',{})))
                except Exception as exc:
                    row.update(error=type(exc).__name__,output='')
                row['latency_ms']=(time.perf_counter_ns()-t)/1e6
                journal.write(json.dumps(row)+'\n');journal.flush()
                predictions.append(row)
        result=evaluate(cases,predictions)
        result.update(variant=variant,split=split,latency_boundary='resident tokenization + encoder + heads + strict decode; first request included',
                      startup_seconds=manifest['load_seconds'],energy_joules=None,execution='host_CPU_only',blind_test=False,
                      output_policy='shared canonical field grammar; validity by construction does not imply semantic correctness')
        dump(args.out/f'{variant}-{split}-summary.json',result)
        print(json.dumps(dict(variant=variant,split=split,accuracy=result['full_command_accuracy'],latency_ms=result['latency_ms'])),flush=True)
    for split in ('dev','diagnostic'):
        score(model,split,'fp32')
    if args.quantize:
        start=time.perf_counter()
        quantized=torch.ao.quantization.quantize_dynamic(model.eval(),{nn.Linear},dtype=torch.qint8,inplace=False)
        manifest['quantization_seconds']=time.perf_counter()-start
        manifest['quantization']='PyTorch CPU dynamic INT8 Linear; embeddings and other operators remain FP32; not FPGA arithmetic'
        for split in ('dev','diagnostic'):
            score(quantized,split,'dynamic-int8')
    manifest['stage']='complete'
    manifest['memory_at_end']=process_memory()
    dump(args.out/'run.json',manifest)


if __name__=='__main__':
    main()
