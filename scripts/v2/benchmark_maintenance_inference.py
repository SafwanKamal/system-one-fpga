"""Choose CPU threads on tuning inputs; no task-score or evaluation feedback."""
import argparse
import json
from pathlib import Path
import time
import torch
from maintenance_sft import DEFAULT, load, serialize, public_input, read_rows, sha, dump


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work',type=Path,default=DEFAULT)
    ap.add_argument('--model',choices=['qwen','functiongemma'],required=True)
    a=ap.parse_args()
    tok,model=load(a.model,4)
    saved=torch.load(a.work/a.model/'checkpoint.pt',weights_only=True)
    for i,state in saved['layers'].items(): model.model.layers[int(i)].load_state_dict(state)
    model=torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True)
    cases=read_rows(a.work/'tuning.jsonl')[:4]
    jobs=[serialize(tok,a.model,dict(public_input(c),id=c['id'])) for c in cases]
    maximum=max(len(j['prompt_ids']) for j in jobs)
    pad=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    ids=torch.tensor([[pad]*(maximum-len(j['prompt_ids']))+j['prompt_ids'] for j in jobs])
    mask=torch.tensor([[0]*(maximum-len(j['prompt_ids']))+[1]*len(j['prompt_ids']) for j in jobs])
    rows=[]; reference=None
    for threads in (4,1,2,4,1,2):
        torch.set_num_threads(threads)
        tick=time.perf_counter()
        with torch.inference_mode():
            result=model.generate(input_ids=ids,attention_mask=mask,max_new_tokens=16,min_new_tokens=16,
                do_sample=False,use_cache=True,pad_token_id=pad,repetition_penalty=1.0)
        seconds=time.perf_counter()-tick; generated=result[:,maximum:].tolist()
        if reference is None: reference=generated
        if generated!=reference: raise RuntimeError('Thread settings changed the tuning token prefix')
        row=dict(threads=threads,seconds=seconds);rows.append(row)
        print(json.dumps(row),flush=True)
    means={t:sum(r['seconds'] for r in rows if r['threads']==t)/2 for t in (1,2,4)}
    selected=min(means,key=means.get)
    dump(a.work/a.model/'inference-thread-selection.json',dict(rows=rows,means=means,selected=selected,
        criterion='minimum mean time on fixed four tuning prompts, six 16-token trials',
        prefix_ids_identical=True,tuning_ids=[c['id'] for c in cases],
        checkpoint_sha256=sha(a.work/a.model/'checkpoint.pt'),evaluation_scores_used=False,
        controlled_latency_comparison=False,source_sha256=sha(Path(__file__))))
    print(json.dumps(dict(selected=selected,means=means)),flush=True)


if __name__=='__main__':main()
