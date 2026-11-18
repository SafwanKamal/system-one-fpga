"""Offline whole-model float reference with layer-streamed official weights.

One unpadded stream. No quantization, export, FPGA I/O or performance claim.
Embedding lookup and full vocabulary projection share the same weight tensor.
"""
import json
from pathlib import Path
import numpy as np
from safetensors import safe_open
from .functiongemma_float_ops import FloatGemmaBlock,rms_norm
from .functiongemma_profile import validate_prompt_ids


class StreamingFloatGemma:
    def __init__(self,model_path,max_context=2048):
        self.path=Path(model_path)
        self.config=json.loads((self.path/'config.json').read_text(encoding='utf-8'))
        self.max_context=max_context
        if self.config.get('final_logit_softcapping') is not None:
            raise ValueError('unsupported final softcap')
        if self.config.get('model_type')!='gemma3_text':
            raise ValueError('expected Gemma3 text model')

    def step(self,ids,states=None):
        ids=list(ids)
        validate_prompt_ids(ids,self.config['vocab_size'],self.max_context,256 if states is None else 1)
        if states is not None and len(states)!=self.config['num_hidden_layers']:
            raise ValueError('cache layer extent')
        with safe_open(self.path/'model.safetensors',framework='pt',device='cpu') as store:
            embedding=store.get_slice('model.embed_tokens.weight')
            rows={value:embedding[value:value+1,:].float().numpy()[0] for value in set(ids)}
            # Match the checkpoint's explicitly FP32 embedding scale constant.
            scale=np.float32(np.sqrt(self.config['hidden_size']))
            hidden=np.stack([rows[i] for i in ids]).astype(np.float64)*float(scale)
            updated=[]
            for layer in range(self.config['num_hidden_layers']):
                prefix=f'model.layers.{layer}.'
                weights={name[len(prefix):]:store.get_tensor(name).float().numpy()
                    for name in store.keys() if name.startswith(prefix)}
                block=FloatGemmaBlock(weights,self.config,layer,self.max_context)
                hidden,state,_=block(hidden,None if states is None else states[layer])
                updated.append(state)
            gamma=store.get_tensor('model.norm.weight').float().numpy().astype(np.float64)
            hidden=rms_norm(hidden,gamma,self.config['rms_norm_eps'])
            # Every vocabulary row is projected. No answer-derived mask or
            # vocabulary reduction; stream rows to avoid duplicating the model.
            logits=np.empty(self.config['vocab_size'],dtype=np.float64)
            for start in range(0,len(logits),4096):
                weights=embedding[start:start+4096,:].float().numpy().astype(np.float64)
                logits[start:start+len(weights)]=weights@hidden[-1]
        return logits,tuple(updated),hidden[-1]
