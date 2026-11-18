"""Greedy FP32 batching without vocabulary masks or task-label access."""
import time
import torch
from transformers import GenerationConfig


def generate_ids(model,prompts,stops,pad_id=0,output_cap=256):
    if not prompts or any(not p for p in prompts) or not 1<=output_cap<=256:
        raise ValueError('invalid generation work profile')
    width=max(map(len,prompts))
    ids=torch.full((len(prompts),width),pad_id,dtype=torch.long)
    mask=torch.zeros_like(ids)
    for index,prompt in enumerate(prompts):
        ids[index,-len(prompt):]=torch.tensor(prompt,dtype=torch.long)
        mask[index,-len(prompt):]=1
    config=GenerationConfig(max_new_tokens=output_cap,do_sample=False,num_beams=1,
        use_cache=True,pad_token_id=pad_id,eos_token_id=list(stops),
        repetition_penalty=1.,no_repeat_ngram_size=0,
        forced_bos_token_id=None,forced_eos_token_id=None)
    start=time.perf_counter_ns()
    with torch.inference_mode():
        outputs=model.generate(input_ids=ids,attention_mask=mask,generation_config=config,
            logits_to_keep=1,return_dict_in_generate=False)
    elapsed=(time.perf_counter_ns()-start)/1e6
    result=[]
    for row in outputs[:,width:].tolist():
        emitted=[]
        for value in row:
            emitted.append(value)
            if value in stops:break
        result.append(emitted)
    return result,elapsed
