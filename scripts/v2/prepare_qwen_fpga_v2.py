"""Pinned Qwen Q8 metadata and one two-token block fixture for FPGA work."""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/qwen-fpga-decoder-v4';sys.path.insert(0,str(ROOT/'build/v2/qwen-fpga-decoder-v1/deps'))
from gguf import GGUFReader,GGMLQuantizationType
from gguf.quants import dequantize
MODEL=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
r=GGUFReader(MODEL);tensors={t.name:t for t in r.tensors}
manifest=dict(model='Qwen3-0.6B',weights='official pinned Q8_0',sha256='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031',bytes=MODEL.stat().st_size,hidden=1024,q_heads=16,kv_heads=8,head_dim=128,ffn=3072,layers=28,max_context=256,vocab=151936,embedding=int(tensors['token_embd.weight'].data_offset),output_norm=int(tensors['output_norm.weight'].data_offset),eos_ids=[151645,151643],layer_offsets=[])
names=['attn_q.weight','attn_k.weight','attn_v.weight','attn_output.weight','ffn_gate.weight','ffn_up.weight','ffn_down.weight','attn_norm.weight','ffn_norm.weight','attn_q_norm.weight','attn_k_norm.weight']
for i in range(28):manifest['layer_offsets'].append([int(tensors[f'blk.{i}.{n}'].data_offset) for n in names])
(OUT/'model-manifest.json').write_text(json.dumps(manifest,indent=2))
pos=np.arange(256,dtype=np.float32)[:,None];freq=(np.float32(1000000.)**(-np.arange(64,dtype=np.float32)/np.float32(64)))[None,:];angle=pos*freq
rope=np.stack([np.cos(angle),np.sin(angle)],axis=1).astype('<f4');(OUT/'rope.bin').write_bytes(rope.tobytes())
# A compact real first-layer model, including a scatter-segment boundary.
fixture=OUT/'block-fixture';fixture.mkdir(exist_ok=True);blob=bytearray(131072)
def append(raw):
 blob.extend(bytes((-len(blob))%32));off=len(blob);blob.extend(raw);return off
def raw(t):return np.asarray(t.data).tobytes()
ids=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v3/real-command-result.json').read_text())['prompt_ids'][:4];embed=tensors['token_embd.weight'];embedding=[append(np.asarray(embed.data[i]).tobytes()) for i in ids]
offsets=[append(raw(tensors['blk.0.'+n])) for n in names];final=append(raw(tensors['output_norm.weight']));head=append(np.asarray(embed.data[:32]).tobytes());blob.extend(bytes((-len(blob))%16));(fixture/'model.bin').write_bytes(blob)
def f(name):
 t=tensors[name]
 return dequantize(t.data,t.tensor_type).astype(np.float32) if t.tensor_type==GGMLQuantizationType.Q8_0 else np.asarray(t.data,dtype=np.float32)
w={n:f('blk.0.'+n) for n in names}
def rms(x,g):return x/np.sqrt(np.mean(x*x,axis=-1,keepdims=True)+np.float32(1e-6))*g
keys=[];vals=[];expected=[]
for p,token in enumerate(ids):
 x=dequantize(embed.data[token:token+1],GGMLQuantizationType.Q8_0)[0].astype(np.float32);u=rms(x,w['attn_norm.weight']);q=(w['attn_q.weight']@u).reshape(16,128);k=(w['attn_k.weight']@u).reshape(8,128);v=(w['attn_v.weight']@u).reshape(8,128)
 q=rms(q,w['attn_q_norm.weight']);k=rms(k,w['attn_k_norm.weight']);c=rope[p,0];s=rope[p,1]
 q=np.concatenate([q[:,:64]*c-q[:,64:]*s,q[:,64:]*c+q[:,:64]*s],axis=1);k=np.concatenate([k[:,:64]*c-k[:,64:]*s,k[:,64:]*c+k[:,:64]*s],axis=1);keys.append(k);vals.append(v);ctx=np.empty((16,128),dtype=np.float32)
 for h in range(16):
  scores=np.stack(keys)[:,h//2]@q[h]*np.float32(1/np.sqrt(128));prob=np.exp(scores-scores.max());prob/=prob.sum();ctx[h]=prob@np.stack(vals)[:,h//2]
 x=x+w['attn_output.weight']@ctx.reshape(2048);u=rms(x,w['ffn_norm.weight']);gate=w['ffn_gate.weight']@u;up=w['ffn_up.weight']@u;x=x+w['ffn_down.weight']@((gate/(1+np.exp(-gate)))*up);expected.append(x)
 normalized=rms(x,f('output_norm.weight'));(fixture/f'expected-{p}.bin').write_bytes(x.astype('<f4').tobytes());(fixture/f'normalized-{p}.bin').write_bytes(normalized.astype('<f4').tobytes())
headw=dequantize(embed.data[:32],GGMLQuantizationType.Q8_0).astype(np.float32);logits=headw@normalized;meta=dict(bytes=len(blob),embedding=embedding,offsets=offsets,output_norm=final,head=head,expected_token=int(logits.argmax()),expected_logit=float(logits.max()),ids=ids)
(fixture/'manifest.json').write_text(json.dumps(meta,indent=2));(fixture/'metadata.bin').write_bytes(struct.pack('<'+'I'*19,len(blob),*embedding,*offsets,final,head,int(logits.argmax())))
print(json.dumps(dict(model_bytes=manifest['bytes'],fixture_bytes=len(blob),fixture_token_ids=ids,first_layer_four_tokens=True,top32_head=meta['expected_token'])))
