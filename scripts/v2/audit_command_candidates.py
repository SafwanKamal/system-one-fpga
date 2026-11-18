"""Static checkpoint/layout and prompt-cap audit; never probes board registers."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.command_codec import encode,tool
from sysone.v2.command_task import percentile


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    args=ap.parse_args()
    from transformers import AutoTokenizer
    inventory=json.loads((args.data/'inventory.json').read_text())
    out=dict(kind='static_software_audit_not_hardware_qualification',models={},board_contacted=False)
    models={}
    for role,record in inventory['models'].items():
        snapshot=next(r for r in record['requests'] if r.get('operation')=='snapshot_download' and r['status']=='ok')
        path=Path(snapshot['path'])
        models[role]=path
        tensors={}
        for f in path.glob('*.safetensors'):
            with f.open('rb') as stream:
                size=struct.unpack('<Q',stream.read(8))[0]
                metadata=json.loads(stream.read(size))
            for name,tensor in metadata.items():
                if name!='__metadata__':
                    tensors[name]=tensor
        count=sum(math.prod(t['shape']) for t in tensors.values())
        out['models'][role]=dict(repo=record['repo'],revision=record['revision'],
            stored_tensor_parameters=count,stored_tensor_payload_bytes=sum(t['data_offsets'][1]-t['data_offsets'][0] for t in tensors.values()),
            ideal_homogeneous_W8_bytes=count,ideal_homogeneous_W4_bytes=(count+1)//2,
            storage_note='Arithmetic sizing only; not a quantized image; excludes scale/padding/workspaces/firmware',
            hidden_size=record['config']['hidden_size'],
            head_dim=record['config'].get('head_dim',record['config']['hidden_size']//record['config']['num_attention_heads']),
            vocab_size=record['config']['vocab_size'])
    enc=AutoTokenizer.from_pretrained(models['encoder'],local_files_only=True)
    gen=AutoTokenizer.from_pretrained(models['generator'],local_files_only=True)
    prompt_counts=[]
    completion_counts=[]
    enc_counts=[]
    for split in ('train','dev','diagnostic'):
        for line in (args.data/f'{split}.jsonl').read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            enc_counts.append(len(enc.encode(row['text'])))
            messages=[dict(role='developer',content='You are a model that can do function calling with the following functions'),
                      dict(role='user',content=row['text'])]
            prompt=gen.apply_chat_template(messages,tools=[tool()],add_generation_prompt=True,tokenize=False)
            full=gen.apply_chat_template(messages+[dict(role='assistant',tool_calls=[dict(type='function',
                function=dict(name='publish_command',arguments=encode(row['gold'])))])],tools=[tool()],tokenize=False)
            prompt_counts.append(len(gen.encode(prompt,add_special_tokens=False)))
            completion_counts.append(len(gen.encode(full[len(prompt):],add_special_tokens=False)))
    def stats(values):
        return dict(min=min(values),p50=percentile(values,.5),p95=percentile(values,.95),max=max(values))
    out['token_counts']=dict(cases=len(enc_counts),encoder_input=stats(enc_counts),generator_prompt=stats(prompt_counts),
        generator_completion=stats(completion_counts),generator_prompt_plus_gold_max=max(p+c for p,c in zip(prompt_counts,completion_counts)),
        encoder_inputs_exceeding_128=sum(x>128 for x in enc_counts),
        generator_prompts_exceeding_512=sum(x>512 for x in prompt_counts),
        generator_prompt_plus_160_exceeding_1280=sum(x+160>1280 for x in prompt_counts),
        note='Sizing on public synthetic diagnostic labels; no human blind test exists')
    out['existing_layout']=dict(base='0x60000000',reserved_bytes=256*1024**2,
        token_ids='0x62100000',hidden='0x62101000',mailbox='0x62400000',
        bytes_before_first_fixed_buffer=0x62100000-0x60000000,
        encoder_ideal_W8_overlaps_fixed_buffers=out['models']['encoder']['ideal_homogeneous_W8_bytes']>0x2100000,
        note='Successor images require explicit relocation and source-qualified R5 ABI; no files were loaded')
    out['generator_KV_arithmetic']=dict(
        fp16_all_layers_512_tokens_bytes=18*2*1*256*512*2,
        fp16_all_layers_1280_tokens_bytes=18*2*1*256*1280*2,
        fp16_15_local512_3_global1280_bytes=(15*512+3*1280)*2*1*256*2,
        note='Shape arithmetic, not a measured cache allocation or supported hardware capacity')
    out['software_sources_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),ROOT/'src/sysone/v2/command_codec.py')}
    path=args.data/'candidate-audit.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
