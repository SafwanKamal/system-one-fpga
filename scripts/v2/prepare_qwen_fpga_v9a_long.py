"""v9a exact-order 40-position layer-0 reference (long-context fixture).

Exercises attention beyond the 16-row score padding and across five prefill
groups; otherwise identical arithmetic to prepare_qwen_fpga_v9a.py.

Same tensors, fixture blob and INT8 matrix arithmetic as prepare_qwen_fpga_v3.py
(the v8 reference). Only two FP32 summation orders change, mirroring v9a:
RMS sum of squares uses four lane partials combined (l0+l1)+(l2+l3), and the
attention score adds 16 chunk trees of eight products sequentially.
Writes only build/v2/qwen-fpga-decoder-v9a; the v8 fixture is read, not changed.
"""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/qwen-fpga-decoder-v9a';V8=ROOT/'build/v2/qwen-fpga-decoder-v8';sys.path.insert(0,str(ROOT/'build/v2/qwen-fpga-decoder-v1/deps'))
from gguf import GGUFReader,GGMLQuantizationType
from gguf.quants import dequantize
MODEL=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
r=GGUFReader(MODEL);tensors={t.name:t for t in r.tensors}
manifest=dict(model='Qwen3-0.6B',weights='official pinned Q8_0',sha256='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031',bytes=MODEL.stat().st_size,hidden=1024,q_heads=16,kv_heads=8,head_dim=128,ffn=3072,layers=28,max_context=256,vocab=151936,embedding=int(tensors['token_embd.weight'].data_offset),output_norm=int(tensors['output_norm.weight'].data_offset),eos_ids=[151645,151643],layer_offsets=[])
names=['attn_q.weight','attn_k.weight','attn_v.weight','attn_output.weight','ffn_gate.weight','ffn_up.weight','ffn_down.weight','attn_norm.weight','ffn_norm.weight','attn_q_norm.weight','attn_k_norm.weight']
for i in range(28):manifest['layer_offsets'].append([int(tensors[f'blk.{i}.{n}'].data_offset) for n in names])

pos=np.arange(256,dtype=np.float32)[:,None];freq=(np.float32(1000000.)**(-np.arange(64,dtype=np.float32)/np.float32(64)))[None,:];angle=pos*freq
rope=np.stack([np.cos(angle),np.sin(angle)],axis=1).astype('<f4');assert rope.tobytes()==(V8/'rope.bin').read_bytes()
# A compact real first-layer model, including a scatter-segment boundary.
fixture=OUT/'long-fixture';fixture.mkdir(exist_ok=True);blob=bytearray(131072)
def append(raw):
 blob.extend(bytes((-len(blob))%32));off=len(blob);blob.extend(raw);return off
def raw(t):return np.asarray(t.data).tobytes()
ids=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v3/real-command-result.json').read_text())['prompt_ids'][:40];embed=tensors['token_embd.weight'];embedding=[append(np.asarray(embed.data[i]).tobytes()) for i in ids]
offsets=[append(raw(tensors['blk.0.'+n])) for n in names];final=append(raw(tensors['output_norm.weight']));head=append(np.asarray(embed.data[:32]).tobytes());blob.extend(bytes((-len(blob))%16));(fixture/'model.bin').write_bytes(blob)
def f(name):
 t=tensors[name]
 return dequantize(t.data,t.tensor_type).astype(np.float32) if t.tensor_type==GGMLQuantizationType.Q8_0 else np.asarray(t.data,dtype=np.float32)
w={n:f('blk.0.'+n) for n in names}
# Independent scalar-block/NumPy integer reference, never used by board inference.
def qmat(name,x):
 t=tensors['blk.0.'+name] if name!='head' else None
 if t is None: raw=np.asarray(embed.data[:32]).reshape(32,-1,34)
 else: raw=np.asarray(t.data).reshape(len(w[name]),-1,34)
 values=x.astype(np.float32).reshape(-1,32)
 scale=np.max(np.abs(values),axis=1).astype(np.float32)/np.float32(127)
 inv=np.divide(np.float32(1),scale,out=np.zeros_like(scale),where=scale!=0)
 v=values*inv[:,None]
 q=np.clip(np.where(v>=0,np.floor(v+np.float32(.5)),np.ceil(v-np.float32(.5))),-127,127).astype(np.int32)
 weights=raw[:,:,2:].copy().view(np.int8).astype(np.int32)
 dots=np.sum(weights*q[None,:,:],axis=2,dtype=np.int32).astype(np.float32)
 ws=raw[:,:,:2].copy().view('<f2').reshape(raw.shape[:2]).astype(np.float32)
 terms=(dots*ws)*scale[None,:]
 partial=np.zeros((raw.shape[0],8),np.float32)
 for i in range(terms.shape[1]):partial[:,i%8]+=terms[:,i]
 return ((partial[:,0]+partial[:,1])+(partial[:,2]+partial[:,3]))+((partial[:,4]+partial[:,5])+(partial[:,6]+partial[:,7]))

def rms(x,g):
 lanes=np.zeros(x.shape[:-1]+(4,),np.float32)
 for i in range(0,x.shape[-1],4):lanes=np.float32(lanes+x[...,i:i+4]*x[...,i:i+4])
 squares=np.float32(np.float32(lanes[...,0]+lanes[...,1])+np.float32(lanes[...,2]+lanes[...,3]))
 inverse=np.float32(1)/np.sqrt(squares/np.float32(x.shape[-1])+np.float32(1e-6))
 return (x*inverse[...,None])*g
keys=[];vals=[];expected=[]
for p,token in enumerate(ids):
 x=dequantize(embed.data[token:token+1],GGMLQuantizationType.Q8_0)[0].astype(np.float32);u=rms(x,w['attn_norm.weight']);q=(qmat('attn_q.weight',u)).reshape(16,128);k=(qmat('attn_k.weight',u)).reshape(8,128);v=(qmat('attn_v.weight',u)).reshape(8,128)
 q=rms(q,w['attn_q_norm.weight']);k=rms(k,w['attn_k_norm.weight']);c=rope[p,0];s=rope[p,1]
 q=np.concatenate([q[:,:64]*c-q[:,64:]*s,q[:,64:]*c+q[:,:64]*s],axis=1);k=np.concatenate([k[:,:64]*c-k[:,64:]*s,k[:,64:]*c+k[:,:64]*s],axis=1);keys.append(k);vals.append(v);ctx=np.empty((16,128),dtype=np.float32)
 for h in range(16):
  kh=np.stack(keys)[:,h//2];vh=np.stack(vals)[:,h//2];scores=np.zeros(len(keys),np.float32)
  for c in range(16):
   pr=kh[:,c*8:c*8+8]*q[h,c*8:c*8+8]
   tree=np.float32(np.float32(np.float32(pr[:,0]+pr[:,1])+np.float32(pr[:,2]+pr[:,3]))+np.float32(np.float32(pr[:,4]+pr[:,5])+np.float32(pr[:,6]+pr[:,7])))
   scores=np.float32(scores+tree)
  scores=scores*np.float32(0.08838834764831845)
  mass=np.exp(scores-scores.max());total=np.float32(0);acc=np.zeros(128,np.float32)
  for t in range(len(keys)):total=np.float32(total+mass[t]);acc=np.float32(acc+mass[t]*vh[t])
  ctx[h]=acc*(np.float32(1)/total)
 x=x+qmat('attn_output.weight',ctx.reshape(2048));u=rms(x,w['ffn_norm.weight']);gate=qmat('ffn_gate.weight',u);up=qmat('ffn_up.weight',u);x=x+qmat('ffn_down.weight',((gate/(1+np.exp(-gate)))*up));expected.append(x)
 normalized=rms(x,f('output_norm.weight'));(fixture/f'expected-{p}.bin').write_bytes(x.astype('<f4').tobytes());(fixture/f'normalized-{p}.bin').write_bytes(normalized.astype('<f4').tobytes())
headw=dequantize(embed.data[:32],GGMLQuantizationType.Q8_0).astype(np.float32);logits=qmat('head',normalized);meta=dict(bytes=len(blob),embedding=embedding,offsets=offsets,output_norm=final,head=head,expected_token=int(logits.argmax()),expected_logit=float(logits.max()),ids=ids)
(fixture/'manifest.json').write_text(json.dumps(meta,indent=2));(fixture/'metadata.bin').write_bytes(struct.pack('<'+'I'*(len(embedding)+16),len(embedding),len(blob),*embedding,*offsets,final,head,int(logits.argmax())))
print(json.dumps(dict(model_bytes=manifest['bytes'],fixture_bytes=len(blob),fixture_token_ids=ids,first_layer_eight_tokens=True,activation_quantization='symmetric INT8 block32, round ties away, weights unchanged',top32_head=meta['expected_token'])))
