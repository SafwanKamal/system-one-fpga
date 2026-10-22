"""v9e exact-order 2048-position layer-0 reference (BF16 K/V cache, eight tiles).

Arithmetic equals prepare_qwen_fpga_v9c_long.py (tiled online softmax, every exp
from hls::expf) except that K (after RoPE) and V are rounded to BF16, round to
nearest even with NaN kept quiet, before attention reads them, exactly as v9e
stores them in DDR. The sequential FP32 sums use np.add.accumulate, which keeps
the same left-to-right order as the hardware loops. RoPE covers 2048 positions;
its first 1024 rows equal the v9c table bit for bit.
"""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/qwen-fpga-decoder-v9e';V9C=ROOT/'build/v2/qwen-fpga-decoder-v9c';OUT.mkdir(parents=True,exist_ok=True);V8=ROOT/'build/v2/qwen-fpga-decoder-v8';sys.path.insert(0,str(ROOT/'build/v2/qwen-fpga-decoder-v1/deps'))
from gguf import GGUFReader,GGMLQuantizationType
from gguf.quants import dequantize
MODEL=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
r=GGUFReader(MODEL);tensors={t.name:t for t in r.tensors}
manifest=dict(model='Qwen3-0.6B',weights='official pinned Q8_0',sha256='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031',bytes=MODEL.stat().st_size,hidden=1024,q_heads=16,kv_heads=8,head_dim=128,ffn=3072,layers=28,max_context=256,vocab=151936,embedding=int(tensors['token_embd.weight'].data_offset),output_norm=int(tensors['output_norm.weight'].data_offset),eos_ids=[151645,151643],layer_offsets=[])
names=['attn_q.weight','attn_k.weight','attn_v.weight','attn_output.weight','ffn_gate.weight','ffn_up.weight','ffn_down.weight','attn_norm.weight','ffn_norm.weight','attn_q_norm.weight','attn_k_norm.weight']
for i in range(28):manifest['layer_offsets'].append([int(tensors[f'blk.{i}.{n}'].data_offset) for n in names])

pos=np.arange(2048,dtype=np.float32)[:,None];freq=(np.float32(1000000.)**(-np.arange(64,dtype=np.float32)/np.float32(64)))[None,:];angle=pos*freq
rope=np.stack([np.cos(angle),np.sin(angle)],axis=1).astype('<f4');assert rope[:256].tobytes()==(V8/'rope.bin').read_bytes();assert rope[:1024].tobytes()==(V9C/'rope.bin').read_bytes();(OUT/'rope.bin').write_bytes(rope.tobytes())
# A compact real first-layer model, including a scatter-segment boundary.
fixture=OUT/'long-fixture';fixture.mkdir(exist_ok=True);blob=bytearray(131072)
def append(raw):
 blob.extend(bytes((-len(blob))%32));off=len(blob);blob.extend(raw);return off
def raw(t):return np.asarray(t.data).tobytes()
ids=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v3/real-command-result.json').read_text())['prompt_ids']*40;ids=ids[:2048];embed=tensors['token_embd.weight'];embedding=[append(np.asarray(embed.data[i]).tobytes()) for i in ids]
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
import os,subprocess
def hls_exp(values):
 """Every exponential comes from hls::expf in HLS C simulation (bit-exact to the
 kernel's csim): NumPy exp differs by 1 ulp on some inputs and keeps subnormals."""
 x=np.ascontiguousarray(np.concatenate([np.asarray(v,np.float32).ravel() for v in values]),dtype='<f4')
 src=OUT/'oracle-in.f32';dst=OUT/'oracle-out.f32';x.tofile(src)
 if dst.exists():dst.unlink()
 env=dict(os.environ,ORACLE_IN='S:/'+src.relative_to(ROOT).as_posix(),ORACLE_OUT='S:/'+dst.relative_to(ROOT).as_posix())
 run=subprocess.run(['C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat','--mode','hls','--tcl','S:/hls/hls_expf_oracle/run.tcl'],env=env,capture_output=True,text=True)
 if run.returncode or 'ORACLE expf n='+str(len(x)) not in run.stdout:raise RuntimeError('expf oracle failed: '+run.stdout[-2000:])
 y=np.fromfile(dst,'<f4')
 if len(y)!=len(x):raise RuntimeError('expf oracle length')
 return y
def f32(v):return np.float32(v)
def bf16(a):
 # Round to nearest even to BF16 and widen back, as v9e's append_kv/attention do.
 u=np.ascontiguousarray(a,dtype=np.float32).view(np.uint32)
 nan=((u&0x7f800000)==0x7f800000)&((u&0x007fffff)!=0)
 r=np.where(nan,(u>>16)|0x40,(u+np.uint32(0x7fff)+((u>>16)&1))>>16).astype(np.uint32)
 return (r<<16).astype(np.uint32).view(np.float32)
# Phase 1: per-position Q/K/V (layer 0 K/V depend only on the embeddings).
X=[];Qs=[];Ks=[];Vs=[]
for p,token in enumerate(ids):
 x=dequantize(embed.data[token:token+1],GGMLQuantizationType.Q8_0)[0].astype(np.float32);u=rms(x,w['attn_norm.weight']);q=(qmat('attn_q.weight',u)).reshape(16,128);k=(qmat('attn_k.weight',u)).reshape(8,128);v=(qmat('attn_v.weight',u)).reshape(8,128)
 q=rms(q,w['attn_q_norm.weight']);k=rms(k,w['attn_k_norm.weight']);c=rope[p,0];s=rope[p,1]
 q=np.concatenate([q[:,:64]*c-q[:,64:]*s,q[:,64:]*c+q[:,:64]*s],axis=1);k=np.concatenate([k[:,:64]*c-k[:,64:]*s,k[:,64:]*c+k[:,:64]*s],axis=1)
 X.append(x);Qs.append(q);Ks.append(bf16(k));Vs.append(bf16(v))
Ks=np.stack(Ks);Vs=np.stack(Vs)
# Phase 2: scores, per-tile maxima and every attention exp input, in kernel order.
plans=[];inputs=[]
for p in range(len(ids)):
 for h in range(16):
  kh=Ks[:p+1,h//2];scores=np.zeros(p+1,np.float32)
  for c in range(16):
   pr=kh[:,c*8:c*8+8]*Qs[p][h,c*8:c*8+8]
   tree=f32(f32(f32(pr[:,0]+pr[:,1])+f32(pr[:,2]+pr[:,3]))+f32(f32(pr[:,4]+pr[:,5])+f32(pr[:,6]+pr[:,7])))
   scores=f32(scores+tree)
  scores=scores*np.float32(0.08838834764831845);m_run=None;tiles=[]
  for tile in range(0,p+1,256):
   sc=scores[tile:tile+256];m=f32(sc.max());ci=None
   if m_run is not None:
    m=max(m,m_run);ci=f32(m_run-m)
   tiles.append((tile,len(sc),m,ci));inputs.append(f32(sc-m))
   if ci is not None:inputs.append([ci])
   m_run=m
  plans.append(tiles)
E=hls_exp(inputs);cursor=0
def take(n):
 global cursor
 out=E[cursor:cursor+n];cursor+=n;return out
# Phase 3: tiled online-softmax context, output projection and FFN inputs.
X2=[];G=[];U=[]
for p in range(len(ids)):
 ctx=np.empty((16,128),dtype=np.float32)
 for h in range(16):
  vh=Vs[:p+1,h//2];first=True
  for tile,n,m,ci in plans[p*16+h]:
   mass=take(n);corr=take(1)[0] if ci is not None else None;tt=np.float32(0)
   start=np.zeros(128,np.float32) if first else (acc_run*corr).astype(np.float32)
   rows_=np.concatenate([start[None,:],(mass[:,None]*vh[tile:tile+n]).astype(np.float32)],axis=0)
   acc=np.add.accumulate(rows_,axis=0,dtype=np.float32)[-1]
   tt=np.add.accumulate(np.concatenate([[np.float32(0)],mass]).astype(np.float32),dtype=np.float32)[-1]
   total=tt if first else f32(f32(total_run*corr)+tt)
   acc_run,total_run,first=acc,total,False
  ctx[h]=acc*(np.float32(1)/total)
 x=X[p]+qmat('attn_output.weight',ctx.reshape(2048));u=rms(x,w['ffn_norm.weight'])
 X2.append(x);G.append(qmat('ffn_gate.weight',u));U.append(qmat('ffn_up.weight',u))
assert cursor==len(E)
S=hls_exp([-g for g in G]).reshape(len(ids),-1)
for p in range(len(ids)):
 x=X2[p]+qmat('ffn_down.weight',((G[p]/(np.float32(1)+S[p]))*U[p]))
 normalized=rms(x,f('output_norm.weight'));(fixture/f'expected-{p}.bin').write_bytes(x.astype('<f4').tobytes());(fixture/f'normalized-{p}.bin').write_bytes(normalized.astype('<f4').tobytes())
headw=dequantize(embed.data[:32],GGMLQuantizationType.Q8_0).astype(np.float32);logits=qmat('head',normalized);meta=dict(bytes=len(blob),embedding=embedding,offsets=offsets,output_norm=final,head=head,expected_token=int(logits.argmax()),expected_logit=float(logits.max()),ids=ids)
(fixture/'manifest.json').write_text(json.dumps(meta,indent=2));(fixture/'metadata.bin').write_bytes(struct.pack('<'+'I'*(len(embedding)+16),len(embedding),len(blob),*embedding,*offsets,final,head,int(logits.argmax())))
print(json.dumps(dict(model_bytes=manifest['bytes'],fixture_bytes=len(blob),fixture_token_ids=ids,first_layer_eight_tokens=True,activation_quantization='symmetric INT8 block32, round ties away, weights unchanged',top32_head=meta['expected_token'])))
