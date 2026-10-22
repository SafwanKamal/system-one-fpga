"""v9e eight-token block fixture derived from the v9e long reference.

BF16 K/V changes every attention output, so v9c's block expectations no longer
apply. Positions 0-7 of the v9e long reference use the same eight tokens as the
block fixture, so their expected and normalized outputs are copied. The top-32
head argmax for normalized-7 is recomputed with the same INT8 matrix arithmetic
(prepare_qwen_fpga_v3.py qmat). The block blob and layer offsets are reused
unchanged from v9c's block fixture (byte-identical to v8's).
"""
import json,shutil,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
V9C=ROOT/'build/v2/qwen-fpga-decoder-v9c/block-fixture'
LONG=ROOT/'build/v2/qwen-fpga-decoder-v9e/long-fixture'
OUT=ROOT/'build/v2/qwen-fpga-decoder-v9e/block-fixture'
sys.path.insert(0,str(ROOT/'build/v2/qwen-fpga-decoder-v1/deps'))
from gguf import GGUFReader
r=GGUFReader(ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf');embed={t.name:t for t in r.tensors}['token_embd.weight']


def qmat_head(x):
    raw=np.asarray(embed.data[:32]).reshape(32,-1,34)
    values=x.astype(np.float32).reshape(-1,32)
    scale=np.max(np.abs(values),axis=1).astype(np.float32)/np.float32(127)
    inv=np.divide(np.float32(1),scale,out=np.zeros_like(scale),where=scale!=0)
    v=values*inv[:,None]
    q=np.clip(np.where(v>=0,np.floor(v+np.float32(.5)),np.ceil(v-np.float32(.5))),-127,127).astype(np.int32)
    weights=raw[:,:,2:].copy().view(np.int8).astype(np.int32)
    dots=np.sum(weights*q[None,:,:],axis=2,dtype=np.int32).astype(np.float32)
    ws=raw[:,:,:2].copy().view('<f2').reshape(raw.shape[:2]).astype(np.float32)
    terms=(dots*ws)*scale[None,:]
    partial=np.zeros((32,8),np.float32)
    for i in range(terms.shape[1]):partial[:,i%8]+=terms[:,i]
    return ((partial[:,0]+partial[:,1])+(partial[:,2]+partial[:,3]))+((partial[:,4]+partial[:,5])+(partial[:,6]+partial[:,7]))


def main():
    old=json.loads((V9C/'manifest.json').read_text());long=json.loads((LONG/'manifest.json').read_text())
    if long['ids'][:8]!=old['ids']:raise RuntimeError('Long fixture does not start with the block tokens')
    OUT.mkdir(exist_ok=True)
    for name in ['model.bin']:shutil.copyfile(V9C/name,OUT/name)
    for p in range(8):
        for kind in ['expected','normalized']:shutil.copyfile(LONG/f'{kind}-{p}.bin',OUT/f'{kind}-{p}.bin')
    logits=qmat_head(np.frombuffer((OUT/'normalized-7.bin').read_bytes(),'<f4'))
    meta=list(struct.unpack('<23I',(V9C/'metadata.bin').read_bytes()))
    meta[22]=int(logits.argmax());(OUT/'metadata.bin').write_bytes(struct.pack('<23I',*meta))
    old.update(expected_token=int(logits.argmax()),expected_logit=float(logits.max()),source='v9e long reference positions 0-7 (BF16 K/V)')
    (OUT/'manifest.json').write_text(json.dumps(old,indent=2))
    print(json.dumps(dict(expected_token=old['expected_token'],v9c_expected_token=json.loads((V9C/'manifest.json').read_text())['expected_token'])))


if __name__=='__main__':main()
