"""Qualify isolated offline blocks against pinned official Gemma3 weights.

Float reference only: no quantized arithmetic, FPGA image or board interaction.
"""
import os
for variable in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch
from safetensors import safe_open
from transformers.models.gemma3.configuration_gemma3 import Gemma3TextConfig
from transformers.models.gemma3.modeling_gemma3 import Gemma3DecoderLayer,Gemma3RotaryEmbedding
from transformers.cache_utils import DynamicCache
from transformers.masking_utils import causal_mask_function,sliding_window_overlay
import transformers.models.gemma3.modeling_gemma3 as upstream
import transformers.masking_utils as upstream_masks

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.functiongemma_float_ops import FloatGemmaBlock,attention_allowed


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def metrics(actual,expected):
    actual=np.asarray(actual);expected=np.asarray(expected)
    return dict(max_abs_error=float(np.max(np.abs(actual-expected))),
        rms_error=float(np.sqrt(np.mean((actual-expected)**2))),
        passed=bool(np.allclose(actual,expected,atol=.001,rtol=.0001)))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1)
    config=json.loads((args.model/'config.json').read_text())
    cfg=Gemma3TextConfig(**config);cfg._attn_implementation='eager'
    weights_path=args.model/'model.safetensors'
    source_paths=[Path(__file__),ROOT/'src/sysone/v2/functiongemma_float_ops.py',
        Path(upstream.__file__),Path(upstream_masks.__file__)]
    source_hashes={str(p):digest(p) for p in source_paths}
    receipt=dict(stage='starting',scope='isolated float blocks; not full decoder, integer arithmetic, FPGA or deadline proof',
        model_path=str(args.model),model_sha256=digest(weights_path),config_sha256=digest(args.model/'config.json'),
        source_sha256=source_hashes,oracle='installed Transformers Gemma3DecoderLayer eager FP32',
        reference='independent NumPy float64 with official float32 RoPE phase semantics',
        tolerances=dict(atol=.001,rtol=.0001),board_contacted=False,paid_compute=False)
    def save():
        (args.out/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (args.out/'sources').mkdir()
    for p in source_paths:(args.out/'sources'/p.name).write_bytes(p.read_bytes())
    save()
    # Check mask semantics independently against the installed mask helpers.
    qs=torch.tensor([0,511,512,513])[:,None]
    ks=torch.tensor([0,1,510,511,512,513])[None,:]
    official=causal_mask_function(0,0,qs,ks)&sliding_window_overlay(512)(0,0,qs,ks)
    assert np.array_equal(attention_allowed(qs.numpy().ravel(),ks.numpy().ravel(),512),official.numpy())
    receipt['mask_boundary_check']=True
    fixtures=[];all_shapes={}
    with safe_open(weights_path,framework='pt',device='cpu') as store:
        for key in store.keys():all_shapes[key]=store.get_slice(key).get_shape()
        for layer_index in (0,5):
            prefix=f'model.layers.{layer_index}.'
            state={k[len(prefix):]:store.get_tensor(k).float() for k in store.keys() if k.startswith(prefix)}
            torch_layer=Gemma3DecoderLayer(cfg,layer_index).float().eval().requires_grad_(False)
            torch_layer.load_state_dict(state,strict=True)
            weights={k:v.numpy() for k,v in state.items()}
            reference=FloatGemmaBlock(weights,config,layer_index)
            rotary=Gemma3RotaryEmbedding(cfg)
            for name,length,position_start,chunks in (
                ('short-prefill-decode',35,0,[32,1,1,1]),
                ('window-boundary',515,0,[510,3,1,1]),
                ('large-rotary-position',7,8192,[4,1,2])):
                rng=np.random.default_rng(2026101800+layer_index+length)
                hidden=rng.normal(0,1,size=(length,config['hidden_size'])).astype(np.float32)
                full,state_ref,trace=reference(hidden,position_start=position_start)
                captures={}
                hooks=[]
                def capture(name):
                    def hook(module,inputs,output):
                        value=output[0] if isinstance(output,tuple) else output
                        captures[name]=value.detach().float().numpy()[0]
                    return hook
                for field,module in [('input_norm',torch_layer.input_layernorm),
                    ('attention',torch_layer.self_attn),('ff_input',torch_layer.pre_feedforward_layernorm),
                    ('feedforward',torch_layer.mlp),('output',torch_layer)]:
                    hooks.append(module.register_forward_hook(capture(field)))
                def torch_chunk(chunk,seen,cache):
                    tensor=torch.from_numpy(chunk)[None]
                    positions=torch.arange(position_start+seen,position_start+seen+len(chunk))[None]
                    past=0
                    if cache is not None:
                        past_keys=cache.layers[layer_index].keys
                        if past_keys is not None:past=past_keys.shape[2]
                    key_pos=np.arange(position_start+seen-past,position_start+seen+len(chunk))
                    allowed=attention_allowed(positions.numpy()[0],key_pos,reference.window)
                    mask=torch.where(torch.from_numpy(allowed),0.,torch.finfo(torch.float32).min)[None,None]
                    embeddings=rotary(tensor,positions,torch_layer.self_attn.layer_type)
                    with torch.inference_mode():
                        return torch_layer(tensor,position_embeddings=embeddings,attention_mask=mask,
                            position_ids=positions,past_key_values=cache).numpy()[0]
                expected=torch_chunk(hidden,0,None)
                stage_checks={field:metrics(trace[field],captures[field]) for field in captures}
                for hook in hooks:hook.remove()
                parts=[];torch_parts=[];state=None;cache=DynamicCache(config=cfg);seen=0
                for count in chunks:
                    chunk=hidden[seen:seen+count]
                    value,state,_=reference(chunk,state,position_start=position_start if state is None else 0)
                    parts.append(value);torch_parts.append(torch_chunk(chunk,seen,cache));seen+=count
                assert seen==length
                checks=dict(stages=stage_checks,output_vs_torch=metrics(full,expected),
                    numpy_cached_vs_prefill=metrics(np.concatenate(parts),full),
                    torch_cached_vs_prefill=metrics(np.concatenate(torch_parts),expected),
                    cached_numpy_vs_torch=metrics(np.concatenate(parts),np.concatenate(torch_parts)))
                passed=all(v['passed'] for k,v in checks.items() if k!='stages') and all(v['passed'] for v in stage_checks.values())
                fixtures.append(dict(layer=layer_index,kind=config['layer_types'][layer_index],fixture=name,
                    tokens=length,position_start=position_start,chunks=chunks,retained_kv_tokens=len(state.keys),
                    head_dim=config['head_dim'],checks=checks,passed=passed))
                receipt['fixtures']=fixtures;save()
                print(json.dumps(dict(layer=layer_index,fixture=name,passed=passed,max_abs_error=checks['output_vs_torch']['max_abs_error'])),flush=True)
                if not passed:raise ValueError('float block qualification failed')
    parameter_count=sum(int(np.prod(s)) for s in all_shapes.values())
    embedding_count=int(np.prod(all_shapes['model.embed_tokens.weight']))
    # Shared embedding/projection weight is present once in safetensors.
    assert 'lm_head.weight' not in all_shapes
    global_layers=sum(t=='full_attention' for t in config['layer_types'])
    local_layers=len(config['layer_types'])-global_layers
    kv_bytes=2*config['head_dim']*config['num_key_value_heads']*(global_layers*2048+local_layers*(config['sliding_window']-1))
    receipt.update(stage='complete',parameter_storage=dict(unique_elements=parameter_count,
        embedding_projection_tied=True,embedding_elements=embedding_count,
        int8_weights_only_lower_bound_bytes=parameter_count,reserved_current_bytes=256*1024*1024,
        weights_alone_fit_current_reserved=parameter_count<=256*1024*1024,
        int8_kv_2048_context_bytes=kv_bytes,
        int8_weights_plus_kv_lower_bound_bytes=parameter_count+kv_bytes,
        weights_and_kv_fit_current_reserved=parameter_count+kv_bytes<=256*1024*1024,
        excluded='scales, norm storage wider than int8, RoPE tables, scratch, firmware, mailbox, alignment'),
        shape_manifest=all_shapes,board_contacted=False)
    save()
    print(json.dumps(dict(stage='complete',fixtures=len(fixtures),parameter_storage=receipt['parameter_storage'])))


if __name__=='__main__':main()
