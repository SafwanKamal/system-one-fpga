"""Offline FPGA-arithmetic adapter for the general BERT parser.

Pair token types are folded into two vocabulary banks; no existing RTL or deployed
image is changed. This doubles word rows, fitting uint16 IDs only for this vocab.
"""
import hashlib
import json
import time
import numpy as np
import torch
from torch import nn
from .int_encoder import FloatEncoder,IntEncoder
from .ddr_image import compile_image,ImageMachine
from .general_tool_encoder import KINDS


def fold_type_vocabulary(word,types):
    if len(types)!=2 or 2*len(word)>65536:
        raise ValueError('two type banks must fit uint16 token IDs')
    return torch.cat([word,word+(types[1]-types[0])],dim=0)


def bank_ids(ids,types,vocab):
    ids=np.asarray(ids,dtype=np.int64)
    types=np.asarray(types,dtype=np.int64)
    if ids.shape!=types.shape or np.any(ids<0) or np.any(ids>=vocab) or np.any((types!=0)&(types!=1)):
        raise ValueError('invalid base token ID/type')
    return ids+types*vocab


class IntegerToolEncoder(nn.Module):
    def __init__(self,model,jobs,out,calibration_jobs=32):
        super().__init__()
        started=time.perf_counter()
        state={k:v for k,v in model.state_dict().items() if k.startswith('encoder.')}
        word=state['encoder.embeddings.word_embeddings.weight']
        self.base_vocab=len(word)
        self.count_classes=model.count.out_features
        types=state['encoder.embeddings.token_type_embeddings.weight']
        state['encoder.embeddings.word_embeddings.weight']=fold_type_vocabulary(word,types)
        for part in ('weight','bias'):
            state['intent.meta.'+part]=torch.cat([model.state_dict()['count.'+part],model.state_dict()['kind.'+part]],dim=0)
            state['slots.span.'+part]=model.state_dict()['span.'+part]
        labels={'intent':{'meta':['count_'+str(i) for i in range(self.count_classes)]+list(KINDS)},'slots':{'span':['start','end']},'pair':{}}
        fe=FloatEncoder(state,model.encoder.config,{k:labels[k] for k in labels})
        model.eval()
        checks=[]
        calibration=jobs[:calibration_jobs]
        if not calibration:
            raise ValueError('training calibration jobs required')
        fe.trace={}
        for i,job in enumerate(calibration):
            tokens=job['tokens']
            ids=bank_ids(tokens['input_ids'],tokens['token_type_ids'],self.base_vocab)
            value=fe.hidden(ids)
            if i<2:
                with torch.inference_mode():
                    actual=model.encoder(**{k:torch.tensor([v]) for k,v in tokens.items()}).last_hidden_state[0].numpy()
                error=float(np.max(np.abs(value-actual)))
                checks.append(dict(job=job['id'],max_abs_error=error,tolerance=0.001))
                if error>0.001:
                    raise ValueError('folded FloatEncoder differs from original pair encoding')
        trace=fe.trace;fe.trace=None
        self.ie=IntEncoder(fe,trace)
        image,manifest=compile_image(self.ie,'general-bert-pilot',labels,base=0x60000000,tile_in=16,tile_out=32,max_tokens=128)
        (out/'candidate.img').write_bytes(image)
        manifest.update(deployment_status='offline only; requires relocated buffers and H768 R5 firmware',
            token_type_fold=dict(base_vocab=self.base_vocab,derived_vocab=2*self.base_vocab,
                rule='hardware_id = tokenizer_id + token_type_id * base_vocab; type0 constant remains in embedding operator'),
            classifier_rows=dict(count=[0,self.count_classes],argument_kind=[self.count_classes,self.count_classes+len(KINDS)]),
            pooling='meta uses CLS row zero; span applies to every token',
            calibration_job_ids=[j['id'] for j in calibration])
        (out/'integer-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        machine=ImageMachine(image)
        exact=[]
        for job in calibration[:2]:
            tokens=job['tokens']
            ids=bank_ids(tokens['input_ids'],tokens['token_type_ids'],self.base_vocab)
            expected=self.ie.hidden(ids);actual=machine.hidden(ids)
            if not np.array_equal(expected,actual):
                raise ValueError('image-interpreter hidden mismatch')
            checked=0
            for kind,name,rows in [('intent','meta',np.array([0])),('slots','span',np.arange(len(ids)))]:
                reference,rs=self.ie.head_logits(expected,kind,name,rows)
                value,vs=machine.head_logits(actual,kind+'.'+name,rows)
                if not np.array_equal(reference,value) or not np.allclose(rs,vs,rtol=1e-6):
                    raise ValueError('image-interpreter head mismatch')
                checked+=value.size
            exact.append(dict(job=job['id'],hidden_elements=actual.size,integer_logits=checked))
        end=0x60000000+len(image)
        align=lambda value:(value+65535)//65536*65536
        ids=align(end);hidden=align(ids+128*2);mailbox=align(hidden+128*768)
        (out/'integer-qualification.json').write_text(json.dumps(dict(
            float_type_fold_checks=checks,exact_image_checks=exact,image_sha256=manifest['sha256'],
            image_bytes=len(image),derived_vocab=2*self.base_vocab,elapsed_seconds=time.perf_counter()-started,
            proposed_layout=dict(ids=hex(ids),hidden=hex(hidden),mailbox=hex(mailbox),
                fits_reserved=mailbox+512*1024<=0x70000000,overlaps_current_buffers=end>0x62100000),
            scope='host references only, not hardware qualification or board latency'),indent=2)+'\n')

    def forward(self,tokens):
        if tokens['input_ids'].shape[0]!=1 or not torch.all(tokens['attention_mask']==1):
            raise ValueError('integer adapter requires one unpadded request')
        ids=bank_ids(tokens['input_ids'][0].numpy(),tokens['token_type_ids'][0].numpy(),self.base_vocab)
        hidden=self.ie.hidden(ids)
        meta,scale=self.ie.head_logits(hidden,'intent','meta',np.array([0]))
        meta=meta*np.asarray(scale,dtype=np.float32).astype(np.float64)
        span,scale=self.ie.head_logits(hidden,'slots','span',np.arange(len(ids)))
        span=span*np.asarray(scale,dtype=np.float32).astype(np.float64)
        return torch.from_numpy(meta[:self.count_classes][None]),torch.from_numpy(meta[self.count_classes:][None]),torch.from_numpy(span[None])
