"""Export the existing sealed adapted Qwen checkpoint; perform no training."""
import gc
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import capability_comparison_20261102 as r
from audit_capability_gguf_20261102 import audit

ROOT=r.ROOT
WORK=ROOT/'build/v2/model-capability-20261102-adapted-controls'
MAIN=ROOT/'build/v2/model-capability-20261102-r3'
PARENT=ROOT/'build/v2/maintenance-sft-v3'

def main():
    WORK.mkdir(exist_ok=True)
    checkpoint=PARENT/'qwen/checkpoint.pt'
    seal=r.rows_json(PARENT/'final-seal.json')['files_sha256']
    expected=seal['qwen/checkpoint.pt']
    if r.digest(checkpoint)!=expected:raise RuntimeError('Parent checkpoint seal mismatch')
    cache=r.CACHE/'adapted-qwen06';cache.mkdir(exist_ok=True)
    hf=cache/'HF-float32'
    if not (hf/'config.json').exists():
        from maintenance_sft import load
        import torch
        tok,model=load('qwen',2)
        saved=torch.load(checkpoint,weights_only=True,map_location='cpu')
        for i,state in saved['layers'].items():model.model.layers[int(i)].load_state_dict(state,strict=True)
        hf.mkdir(exist_ok=True)
        model.save_pretrained(hf,safe_serialization=True,max_shard_size='2GB')
        tok.save_pretrained(hf)
        r.dump(WORK/'export-receipt.json',dict(checkpoint_sha256=expected,existing_training_only=True,
            new_training=False,layers=list(saved['layers']),epoch=saved.get('epoch'),dtype='float32',
            base_source=str(ROOT/'models/Qwen3-0.6B-HF'),base_safetensors={p.name:r.digest(p) for p in (ROOT/'models/Qwen3-0.6B-HF').glob('*.safetensors')},
            exported_files={p.name:r.digest(p) for p in hf.glob('*') if p.is_file()},source_sha256=r.digest(Path(__file__))))
        del model,tok,saved;gc.collect()
    # The checkpoint changes only weights. Retain the original architecture and
    # tokenizer descriptions instead of relying on a newer HF serialization of
    # RoPE fields that the pinned converter may interpret differently.
    base=ROOT/'models/Qwen3-0.6B-HF'
    config=r.rows_json(base/'config.json');config['torch_dtype']='float32';config['dtype']='float32'
    r.dump(hf/'config.json',config)
    for name in ['tokenizer.json','tokenizer_config.json','merges.txt','vocab.json','chat_template.jinja']:
        if (base/name).exists():shutil.copyfile(base/name,hf/name)
    r.dump(WORK/'serialization-compatibility.json',dict(original_config_sha256=r.digest(base/'config.json'),
        exported_config_sha256=r.digest(hf/'config.json'),reason='Preserve original architecture/RoPE and tokenizer metadata; only tensor values were adapted.',
        tokenizer_files_sha256={p.name:r.digest(p) for p in hf.glob('*') if p.name in ['tokenizer.json','tokenizer_config.json','merges.txt','vocab.json','chat_template.jinja']}))
    fp32=cache/'Qwen3-0.6B-maintenance-sft-v3-F32.gguf'
    converter=ROOT/'build/v2/model-capability-export-b11540/source/convert_hf_to_gguf.py'
    if not fp32.exists():
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT/'build/v2/model-capability-export-b11540/python-deps')+os.pathsep+env.get('PYTHONPATH','')
        with (WORK/'conversion.log').open('ab') as out:
            subprocess.run([sys.executable,str(converter),str(hf),'--outtype','f32','--outfile',str(fp32)],check=True,stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,env=env)
    quantizer=ROOT/'build/v2/generation/windows/llama-quantize.exe'
    models=[]
    for label,kind in [('q4','Q4_0'),('q8','Q8_0')]:
        target=cache/f'Qwen3-0.6B-maintenance-sft-v3-{kind}.gguf'
        if not target.exists():
            with (WORK/f'quantize-{label}.log').open('ab') as out:
                subprocess.run([str(quantizer),str(fp32),str(target),kind,'2'],check=True,stdout=out,stderr=subprocess.STDOUT,cwd=ROOT)
        item=dict(key='qwen06-sft-'+label,base_key='qwen06-q4',repo='local/maintenance-sft-v3-qwen',revision='checkpoint-sha256:'+expected,
            filename=target.name,path=str(target),bytes=target.stat().st_size,sha256=r.digest(target),quantization=kind,
            adaptation='Existing final-two-block maintenance SFT on 720 authored examples. Not matched adaptation budget to pretrained candidates.')
        models.append(item)
        r.dump(WORK/'gguf-audits'/f'{item["key"]}.json',audit(target))
    for name in ['development.jsonl','evaluation.jsonl','screen-ids.json','demonstrations.jsonl']:
        if not (WORK/name).exists():shutil.copyfile(MAIN/name,WORK/name)
    r.dump(WORK/'models.json',models)
    protocol=r.rows_json(MAIN/'protocol.json')
    protocol.update(candidates=models,pretrained_weights=False,fine_tuning='Existing sealed checkpoint only; no new training.',
        selection='Adapted capability controls, separate from the eight pretrained candidates. Same fixed prompts, development route budget and 104-task screen.',
        adapted_control=dict(checkpoint_sha256=expected,parent=str(PARENT),historical_float32_results='Fresh111/120; conditional22/64. Different backend/precision/framing, not substituted for new results.'))
    r.dump(WORK/'protocol.json',protocol)
    r.dump(WORK/'preparation-complete.json',dict(models=models,F32_GGUF_sha256=r.digest(fp32),quantizer_sha256=r.digest(quantizer),
        conversion_source_sha256=r.digest(converter),source_sha256=r.digest(Path(__file__)),no_weight_updates=True))
    print(json.dumps(dict(adapted_control_prepared=True,models=[(m['key'],m['bytes']) for m in models])),flush=True)

if __name__=='__main__':main()
