"""Write the audit's metadata (tensor offsets, token ids) and a pre-run receipt."""
import hashlib,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/schedule-invariance-audit';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'build/v2/qwen-fpga-decoder-v1/deps'))
from gguf import GGUFReader
MODEL=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
N=24
names=['attn_q.weight','attn_k.weight','attn_v.weight','attn_output.weight','ffn_gate.weight','ffn_up.weight','ffn_down.weight','attn_norm.weight','ffn_norm.weight','attn_q_norm.weight','attn_k_norm.weight']


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<24),b''):h.update(chunk)
    return h.hexdigest()


def main():
    tensors={t.name:t for t in GGUFReader(MODEL).tensors}
    layers=[[int(tensors[f'blk.{i}.{n}'].data_offset) for n in names] for i in range(28)]
    embedding=int(tensors['token_embd.weight'].data_offset);norm=int(tensors['output_norm.weight'].data_offset)
    offsets=[embedding,norm]+[o for layer in layers for o in layer]
    if any(o%32 for o in offsets):raise RuntimeError('tensor offsets must be 32-byte aligned')
    prompt=json.loads((ROOT/'build/v2/qwen-fpga-decoder-v3/real-command-result.json').read_text())['prompt_ids']
    ids=prompt[:N];wrong=prompt[N:2*N]
    if len(wrong)!=N or any(a==b for a,b in zip(ids,wrong)):raise RuntimeError('need N distinct wrong tokens')
    meta=[MODEL.stat().st_size,embedding,norm]+[o for layer in layers for o in layer]+[N]+ids+wrong
    (OUT/'meta.bin').write_bytes(struct.pack(f'<{len(meta)}I',*meta))
    source={p:sha(ROOT/p) for p in ['hls/qwen_decoder_v9e/qwen_decoder.cpp','hls/qwen_decoder_v9e/matrix_q8.hpp','hls/qwen_decoder_v9e/model_profile.hpp','experiments/schedule_invariance/testbench.cpp','experiments/schedule_invariance/run.tcl','experiments/schedule_invariance/PROTOCOL.md','build/v2/qwen-fpga-decoder-v9e/rope.bin']}
    receipt=dict(written_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),model_sha256=sha(MODEL),model_bytes=MODEL.stat().st_size,positions=N,ids=ids,wrong_ids=wrong,source_sha256=source)
    (OUT/'prereg.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(dict(meta_words=len(meta),model_sha256=receipt['model_sha256']),indent=1))


if __name__=='__main__':main()
