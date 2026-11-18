"""Tuning-only float/cache/quantized checks; no checkpoint selection."""
import argparse
import hashlib
from pathlib import Path
import torch
from maintenance_sft import DEFAULT,load,read_rows,serialize,cached_tail,token_loss,dump,sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',required=True,choices=['qwen','functiongemma'])
    ap.add_argument('--work',type=Path,default=DEFAULT)
    a=ap.parse_args(); tok,model=load(a.model,4)
    out=a.work/a.model
    saved=torch.load(out/'checkpoint.pt',weights_only=True)
    for i,state in saved['layers'].items(): model.model.layers[int(i)].load_state_dict(state)
    case=read_rows(a.work/'tuning.jsonl')[0]; job=serialize(tok,a.model,case,True)
    tensor=torch.tensor([job['input_ids'][:-1]])
    key=hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
    hidden=torch.load(out/'prefix-cache'/(key+'.pt'),weights_only=True)
    result=dict(case=case['id'],checkpoint_sha256=sha(out/'checkpoint.pt'),training_repeated=False,
        evaluation_cases_used=False,expected_first_id=job['target_ids'][0])
    with torch.inference_mode():
        states=model.model(input_ids=tensor,use_cache=False).last_hidden_state
        logits=model.lm_head(states[:,job['prompt_tokens']-1:,:])
        result['float32_completion_loss']=float(torch.nn.functional.cross_entropy(logits[0],torch.tensor(job['target_ids'])))
        result['cached_completion_loss']=float(token_loss(model,hidden,job,saved['cut']))
        result['float32_first_teacher_id']=int(logits[0,0].argmax())
        prefix=model.model(input_ids=torch.tensor([job['prompt_ids']]),use_cache=False).last_hidden_state
        result['float32_first_prompt_id']=int(model.lm_head(prefix[:,-1,:])[0].argmax())
        result['causal_prefix_max_error']=float((states[:,job['prompt_tokens']-1,:]-prefix[:,-1,:]).abs().max())
        ids=model.generate(torch.tensor([job['prompt_ids']]),max_new_tokens=16,do_sample=False,use_cache=True,
            pad_token_id=tok.pad_token_id or tok.eos_token_id)
        result['float32_generated_prefix']=tok.decode(ids[0,len(job['prompt_ids']):],skip_special_tokens=False)
    model=torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True)
    with torch.inference_mode():
        states=model.model(input_ids=tensor,use_cache=False).last_hidden_state
        logits=model.lm_head(states[:,job['prompt_tokens']-1:,:])
        result['dynamic_int8_completion_loss']=float(torch.nn.functional.cross_entropy(logits[0],torch.tensor(job['target_ids'])))
        result['dynamic_int8_first_teacher_id']=int(logits[0,0].argmax())
        prefix=model.model(input_ids=torch.tensor([job['prompt_ids']]),use_cache=False).last_hidden_state
        result['dynamic_int8_first_prompt_id']=int(model.lm_head(prefix[:,-1,:])[0].argmax())
    dump(out/'precision-diagnostic.json',result);print(result,flush=True)


if __name__=='__main__':main()
