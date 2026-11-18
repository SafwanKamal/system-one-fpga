"""Calibration-only CPU precision/runtime qualification; never reads gold labels."""
import json
import time
from contextlib import nullcontext
from pathlib import Path
import numpy as np
import torch
import laya
from laya.common import build_sequence,collate_items,QTYPES
from maintenance_decisions import WORK,ROOT,LAYA_CONTRACT,read_rows,features,public_input,field_question,option_text,softmax,dump,sha

torch.set_num_threads(4)
classes=json.loads((WORK/'classes.json').read_text());variable=[k for k in classes if len(classes[k])>1]
cases=read_rows(WORK/'calibration.jsonl')
# A completed FP32 reference is archived before a BF16 fallback resumes.
reference=WORK/('laya-float32-qualification' if (WORK/'laya-float32-qualification').exists() else 'laya')
archived=read_rows(reference/'calibration-predictions.jsonl')
agent=laya.load(str(ROOT/'models/laya-typed-decisions'),device='cpu',compile=False,fast=False)
agent.model.float().eval()
results=[];fp32_seconds=None;bf16_seconds=None
for index in (0,20,40,60,80,100):
    if index>=len(archived):continue
    case=cases[index];assert case['id']==archived[index]['id'];items=[]
    for k in variable:
        q=dict(t='choice',ins=field_question(k),crit={f'v{i}':option_text(k,v) for i,v in enumerate(classes[k])})
        ids,markers,stats,trunc=build_sequence(agent.tok,LAYA_CONTRACT+'\n'+features(public_input(case)),q,
            max_len=1024,head_max_len=256,return_stats=True,return_truncation_stats=True)
        assert not trunc['truncated'] and stats['options_distinct']==len(classes[k])
        items.append(dict(ids=ids,markers=markers,qtype=QTYPES['choice']))
    b=collate_items([items],agent.tok.pad_token_id)
    kwargs={k:b[k] for k in ('input_ids','attention_mask','marker_pos','marker_mask','qtype')}
    if index==0:
        tick=time.perf_counter()
        with torch.inference_mode():fp,_=agent.model(**kwargs)
        fp32_seconds=time.perf_counter()-tick
        for k,z in zip(variable,fp.tolist()):assert np.allclose(softmax(z[:len(classes[k])]),softmax(archived[index]['field_logits'][k]),atol=.0002,rtol=0)
    tick=time.perf_counter()
    with torch.inference_mode(),torch.autocast('cpu',dtype=torch.bfloat16):z,_=agent.model(**kwargs)
    elapsed=time.perf_counter()-tick
    if index==0:bf16_seconds=elapsed
    error=0.;agreement=True
    for k,logits in zip(variable,z.float().tolist()):
        p=softmax(logits[:len(classes[k])]);reference=softmax(archived[index]['field_logits'][k])
        error=max(error,float(np.abs(p-reference).max()));agreement=agreement and int(p.argmax())==int(reference.argmax())
    results.append(dict(id=case['id'],max_probability_error=error,all_choice_argmaxes_identical=agreement,bf16_seconds=elapsed))
    print(json.dumps(results[-1]),flush=True)
    if not agreement or error>=.01 or fp32_seconds/bf16_seconds<1.5:break
passed=len(results)>=5 and all(x['all_choice_argmaxes_identical'] and x['max_probability_error']<.01 for x in results) and fp32_seconds/bf16_seconds>=1.5
dump(WORK/'laya-precision-probe.json',dict(passed=passed,gate='at least5 calibration cases, all variable choice argmaxes identical, max probability error<.01; first-case runtime speedup>=1.5',
    fp32_seconds=fp32_seconds,bf16_seconds=bf16_seconds,cpu_capability=torch.backends.cpu.get_cpu_capability(),cases=results,
    gold_labels_used=False,evaluation_cases_used=False,source_sha256=sha(Path(__file__))))
print(json.dumps(dict(passed=passed,speedup=fp32_seconds/bf16_seconds)),flush=True)
