"""Probability-output maintenance pilot. Local CPU only; immutable parent results.

Qwen uses a frozen pretrained backbone and a trainable shared candidate scorer.
This is NanoJev-inspired, not a reproduction of its candidate-conditioned backbone.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import pickle
import shutil
import sys
import time

_RUNTIME_SOURCE_BYTES=Path(__file__).read_bytes()
_RUNTIME_SOURCE_HASH=hashlib.sha256(_RUNTIME_SOURCE_BYTES).hexdigest()

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from maintenance_sft import check_seal, MODELS
from maintenance_pilot import read_rows, write_rows, dump, sha, verdict, summary
from sysone.v2.maintenance.baselines import features, flatten, unflatten
from sysone.v2.maintenance.dataset import public_input, make_case, STRATA
from sysone.v2.maintenance.revision2 import _replace, mention_order
from sysone.v2.maintenance.schema import encode

PARENT = ROOT/'build/v2/maintenance-sft-v3'
OLD = ROOT/'build/v2/maintenance-pilot-v2-context1024'
WORK = ROOT/'build/v2/maintenance-decisions-v4'
SPLITS = ('train','tuning','calibration','fresh','conditional')
LAYA_CONTRACT='Interpret a maintenance request as a plan of 1-3 steps, clarification, or rejection. A condition guards the requested action and additional history, not the initial sensor read. Evidence cites all earlier reads. A correction changes only the explicitly corrected asset, preserving the prior request. Unsupported operations: actuator control, Fahrenheit, history counts above 5, more than 3 steps. Clarify missing or ambiguous references and contradictory instructions.'


def probability_models(work):
    selection=work/'laya-runtime-selection.json'
    folder=json.loads(selection.read_text())['folder'] if selection.exists() else 'laya'
    if folder not in ('laya','laya-directml'):raise ValueError('Unknown Laya runtime folder')
    return ('tfidf','minilm','qwen-decision','qwen-decision-adapted',folder)


def active_fields(values):
    """Structural dependencies only. No natural-language or gold-dependent repair."""
    result=['outcome']
    if values['outcome']!='plan':
        return result+['reason']+(['field'] if values['outcome']=='clarify' else [])
    result += ['asset','length','pred_source']
    if values['pred_source']!='_': result += ['pred_op','pred_rhs']
    arguments={'read_metric':['metric'],'read_history':['metric','count'],
        'list_alarms':[],'read_status':[],'read_metadata':['field'],
        'lookup_procedure':['topic'],'draft_report':['priority','evidence'],
        'request_inspection':['priority','evidence']}
    try: length=int(values['length'])
    except ValueError: return result
    for i in range(min(length,3)):
        result += [f'{i}.tool',f'{i}.guard']
        try: tool=json.loads(values[f'{i}.tool'])
        except (ValueError,KeyError): continue
        result += [f'{i}.{k}' for k in arguments.get(tool,[])]
    return result


def field_question(field):
    main={'outcome':'Does the request require a plan, clarification, or rejection?',
        'reason':'What is the reason for clarification or rejection? Use not applicable for a plan.',
        'field':'Which field needs clarification? Use not applicable for a plan or rejection.',
        'asset':'Which entity index in the supplied catalog does the request target?',
        'length':'How many tool steps does the complete plan contain? Use zero for clarification or rejection.',
        'pred_source':'Which zero-based read step supplies the conditional comparison? Use not applicable if unconditional.',
        'pred_op':'Which comparison operator does the request specify? Use not applicable if unconditional.',
        'pred_rhs':'What threshold does the condition compare against? Use not applicable if unconditional.'}
    if field in main: return main[field]
    index,kind=field.split('.')
    names={'tool':'tool name','guard':'whether execution requires the condition to hold',
        'metric':'sensor metric','count':'number of history readings','field':'metadata field',
        'topic':'procedure topic','priority':'action priority','evidence':'zero-based read step indices cited as evidence'}
    return f'For plan step {int(index)+1}, choose {names[kind]}. Use not applicable if this step or argument is absent.'


def option_text(field,value):
    if value=='_': return 'not applicable (absent)'
    if field=='asset': return f'entity{value} in the catalog'
    if field=='pred_op':
        return {'"gt"':'strictly greater than (>)','"ge"':'greater than or equal to (>=)',
                '"lt"':'strictly less than (<)','"le"':'less than or equal to (<=)'}[value]
    try: decoded=json.loads(value)
    except ValueError: return value.replace('_',' ')
    if decoded=='limit': return 'the configured limit'
    if isinstance(decoded,bool): return 'conditional / guarded' if decoded else 'unconditional / unguarded'
    return str(decoded).replace('_',' ')


def prepare(work):
    # The downloader can create the directory first; an existing protocol is never overwritten.
    if (work/'protocol.json').exists(): raise FileExistsError('Campaign already prepared')
    work.mkdir(parents=True,exist_ok=True)
    parent=check_seal(PARENT); old=check_seal(OLD)
    for split in ('train','tuning','fresh','conditional'):
        shutil.copyfile(PARENT/(split+'.jsonl'),work/(split+'.jsonl'))
    calibration=[]
    for category in STRATA:
        for i in range(20):
            c=make_case('tuning',category,9000+i)
            mapping={a:f'{kind}{81+j}' for kind in 'PMF' for j,a in enumerate(x for x in c['catalog'] if x.startswith(kind))}
            c=_replace(c,mapping);c['catalog']=mention_order(public_input(c))
            c['id']=f'v4-calibration-{category}-{i:03d}'
            c['split']='calibration';c['semantic_signature']=json.dumps(c['gold'],sort_keys=True)
            calibration.append(c)
    write_rows(work/'calibration.jsonl',calibration)
    train=read_rows(work/'train.jsonl')
    labels=[flatten(c['gold'],c['catalog']) for c in train]
    classes={k:sorted({r[k] for r in labels}) for k in labels[0]}
    dump(work/'classes.json',classes)
    public_keys={s:{json.dumps(public_input(c),sort_keys=True) for c in read_rows(work/(s+'.jsonl'))} for s in SPLITS}
    for s in SPLITS:
        if s!='calibration': assert not public_keys[s]&public_keys['calibration'],s
    dump(work/'protocol.json',dict(parent=parent,older_parent=old,data_sha256={s:sha(work/(s+'.jsonl')) for s in SPLITS},
        classes_sha256=sha(work/'classes.json'),seed=0,context=1024,precision='float32 CPU',
        qwen='Original Qwen3-0.6B frozen token features; learned shared question-conditioned attention and candidate scorer. No LM projection or decode. Not the published NanoJev architecture/weights.',
        selection='80 head-only epochs maximum; highest tuning complete-plan correctness, then lowest active-field NLL; no evaluation selection',
        calibration='120 new-seed/new-asset authored-template requests. Scalar temperature fits active-field NLL; separate plan-level logistic calibration of minimum active predicted-field confidence. Same calibration records for existing ML controls.',
        laya='Pinned released typed-decisions model, zero maintenance weight updates; native sequential option layout and raw float32 choice logits; no silent state or option truncation.',
        limitations=['one seed','same authored templates','prior fresh/stress sets already inspected','closed field domains learned from training','frozen Qwen versus adapted encoder/generators','no hardware/energy qualification'],
        source_sha256=sha(Path(__file__))))
    shutil.copyfile(__file__,work/'initial-source.py')
    print('Prepared fixed training/tuning/calibration/evaluation roles',flush=True)


class CandidateHead(nn.Module):
    """Shared scorer over runtime candidate embeddings; no class-specific output weights."""
    def __init__(self,width,questions,candidates,dimension=96):
        super().__init__()
        self.register_buffer('questions',questions)
        self.register_buffer('candidates',candidates)
        self.state=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,dimension),nn.GELU())
        self.question=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,dimension))
        self.candidate=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,dimension))
        self.context=nn.Sequential(nn.Linear(dimension*3,dimension),nn.GELU(),nn.LayerNorm(dimension))
        self.scorer=nn.Sequential(nn.Linear(dimension*4,dimension),nn.GELU(),nn.Linear(dimension,1))

    def forward(self,hidden,mask):
        h=self.state(hidden);q=self.question(self.questions);c=self.candidate(self.candidates)
        attention=torch.einsum('btd,fd->bft',h,q)/math.sqrt(h.shape[-1])
        attention=attention.masked_fill(~mask[:,None,:],-1e4).softmax(-1)
        attended=torch.einsum('bft,btd->bfd',attention,h)
        last=h[torch.arange(len(h)),mask.sum(1)-1]
        x=self.context(torch.cat([attended,q[None].expand(len(h),-1,-1),last[:,None].expand(-1,len(q),-1)],-1))
        x=x[:,:,None,:].expand(-1,-1,c.shape[1],-1);c=c[None].expand(len(h),-1,-1,-1)
        return self.scorer(torch.cat([x,c,x*c,x-c],-1)).squeeze(-1)


def qwen_features(work,threads):
    from transformers import AutoModel,AutoTokenizer
    torch.set_num_threads(threads)
    tok=AutoTokenizer.from_pretrained(str(MODELS['qwen']),local_files_only=True)
    base=AutoModel.from_pretrained(str(MODELS['qwen']),local_files_only=True,dtype=torch.float32,attn_implementation='sdpa').eval()
    base.requires_grad_(False)
    folder=work/'qwen-features';folder.mkdir(exist_ok=True)
    classes=json.loads((work/'classes.json').read_text());names=list(classes)
    def encode_texts(texts):
        b=tok(texts,padding=True,return_tensors='pt',truncation=False)
        assert b['input_ids'].shape[1]<=1024
        with torch.inference_mode(): h=base(**b,use_cache=False).last_hidden_state
        return [h[i,:int(b['attention_mask'][i].sum())].clone() for i in range(len(texts))],b
    if not (folder/'choices.pt').exists():
        texts=[field_question(k) for k in names]+[field_question(k)+' Answer: '+option_text(k,v) for k in names for v in classes[k]]
        pooled=[]
        for start in range(0,len(texts),8):
            hs,_=encode_texts(texts[start:start+8]);pooled.extend([h[-1] for h in hs])
        q=torch.stack(pooled[:len(names)]);rest=pooled[len(names):]
        candidates=torch.zeros(len(names),max(map(len,classes.values())),q.shape[-1]);at=0
        for i,k in enumerate(names):
            candidates[i,:len(classes[k])]=torch.stack(rest[at:at+len(classes[k])]);at+=len(classes[k])
        torch.save(dict(questions=q,candidates=candidates),folder/'choices.pt')
    for split in SPLITS:
        path=folder/(split+'.pt')
        if path.exists(): continue
        rows=read_rows(work/(split+'.jsonl'));hidden=[];ids=[];tick=time.perf_counter()
        for start in range(0,len(rows),8):
            texts=[features(public_input(c))+'\nRepresent the complete maintenance request, preserving comparisons, corrections and actions.' for c in rows[start:start+8]]
            hs,b=encode_texts(texts);hidden.extend(hs)
            ids.extend([b['input_ids'][i,:len(h)].tolist() for i,h in enumerate(hs)])
            if (start+8)%80==0: print(json.dumps(dict(phase='features',split=split,completed=min(start+8,len(rows)),seconds=time.perf_counter()-tick)),flush=True)
        torch.save(dict(ids=[c['id'] for c in rows],hidden=hidden,token_ids=ids),path)
        print(json.dumps(dict(phase='features',split=split,count=len(rows),max_tokens=max(map(len,ids)),seconds=time.perf_counter()-tick)),flush=True)
    dump(folder/'base.json',dict(files_sha256={p.name:sha(p) for p in MODELS['qwen'].iterdir() if p.is_file()},frozen=True,dtype='float32'))


def padded(hidden,indices):
    hs=[hidden[i] for i in indices];length=max(len(h) for h in hs)
    out=torch.zeros(len(hs),length,hs[0].shape[-1]);mask=torch.zeros(len(hs),length,dtype=torch.bool)
    for i,h in enumerate(hs):out[i,:len(h)]=h;mask[i,:len(h)]=True
    return out,mask


def targets(rows,classes):
    values=[flatten(c['gold'],c['catalog']) for c in rows];names=list(classes)
    y=torch.tensor([[classes[k].index(r[k]) for k in names] for r in values])
    active=torch.tensor([[k in active_fields(r) for k in names] for r in values])
    return y,active


def mask_logits(logits,classes):
    for i,k in enumerate(classes):logits[:,i,len(classes[k]):]=-1e4
    return logits


def decode(case,logits,classes,seconds=0):
    values={k:vs[int(np.argmax(logits[k]))] for k,vs in classes.items()}
    try:raw=encode(unflatten(values,case['catalog']));error=None
    except (ValueError,TypeError,KeyError,IndexError) as exc:raw=json.dumps(values);error=str(exc)
    return verdict(case,raw,seconds,predicted_fields=values,field_logits=logits,decode_error=error)


def head_rows(head,hidden,cases,classes,tail=None):
    records=[];head.eval()
    with torch.no_grad():
        for start in range(0,len(cases),16):
            inds=range(start,min(start+16,len(cases)));h,m=padded(hidden,inds)
            if tail is not None:h=tail(h)
            logits=mask_logits(head(h,m),classes).tolist()
            for c,z in zip(cases[start:start+16],logits):
                records.append(decode(c,{k:row[:len(classes[k])] for k,row in zip(classes,z)},classes))
    return records


def qwen_prefix(work,threads):
    """Capture the frozen first26 blocks for the adapted decision-head variant."""
    from transformers import AutoModel
    torch.set_num_threads(threads)
    base=AutoModel.from_pretrained(str(MODELS['qwen']),local_files_only=True,dtype=torch.float32,attn_implementation='sdpa').eval()
    base.requires_grad_(False);cut=len(base.layers)-2
    folder=work/'qwen-prefix';folder.mkdir(exist_ok=True)
    class Captured(Exception):pass
    holder={}
    def hook(module,args,kwargs):
        holder['h']=args[0].detach().clone();raise Captured()
    handle=base.layers[cut].register_forward_pre_hook(hook,with_kwargs=True)
    for split in SPLITS:
        path=folder/(split+'.pt')
        if path.exists():continue
        data=torch.load(work/'qwen-features'/(split+'.pt'),weights_only=True);hidden=[];tick=time.perf_counter()
        for start in range(0,len(data['ids']),8):
            ids=data['token_ids'][start:start+8];length=max(map(len,ids))
            tokens=torch.tensor([v+[0]*(length-len(v)) for v in ids]);mask=torch.tensor([[1]*len(v)+[0]*(length-len(v)) for v in ids])
            try:
                with torch.no_grad():base(input_ids=tokens,attention_mask=mask,use_cache=False)
            except Captured:pass
            hidden.extend([h[:len(v)].clone() for h,v in zip(holder.pop('h'),ids)])
            if (start+8)%80==0:print(json.dumps(dict(phase='prefix',split=split,completed=min(start+8,len(data['ids'])),seconds=time.perf_counter()-tick)),flush=True)
        torch.save(dict(ids=data['ids'],hidden=hidden,token_ids=data['token_ids'],cut=cut),path)
        print(json.dumps(dict(phase='prefix',split=split,count=len(hidden),seconds=time.perf_counter()-tick)),flush=True)
    handle.remove()


def train_adapted(work,threads):
    from transformers import AutoModel
    from types import SimpleNamespace
    from maintenance_sft import cached_tail
    torch.set_num_threads(threads);torch.manual_seed(0)
    out=work/'qwen-decision-adapted';out.mkdir(exist_ok=False)
    classes=json.loads((work/'classes.json').read_text())
    bank=torch.load(work/'qwen-features/choices.pt',weights_only=True)
    base=AutoModel.from_pretrained(str(MODELS['qwen']),local_files_only=True,dtype=torch.float32,attn_implementation='sdpa').eval()
    base.requires_grad_(False);cut=len(base.layers)-2
    for layer in base.layers[cut:]:layer.requires_grad_(True)
    wrapper=SimpleNamespace(model=base,config=base.config)
    tail=lambda h:cached_tail(wrapper,h,cut)
    head=CandidateHead(bank['questions'].shape[-1],bank['questions'],bank['candidates'])
    train,tune=[read_rows(work/(s+'.jsonl')) for s in ('train','tuning')]
    train_h,tune_h=[torch.load(work/'qwen-prefix'/(s+'.pt'),weights_only=True)['hidden'] for s in ('train','tuning')]
    initialization=torch.load(work/'qwen-decision/checkpoint.pt',weights_only=True)
    head.load_state_dict(initialization['state'])
    y,active=targets(train,classes)
    trainable=[p for p in base.parameters() if p.requires_grad]
    optim=torch.optim.AdamW([dict(params=trainable,lr=1e-5),dict(params=head.parameters(),lr=1e-4)],weight_decay=.01)
    best=(-1,float('-inf'));history=[];tick=time.perf_counter()
    for epoch in range(6):
        base.eval();head.train();order=np.random.default_rng(epoch).permutation(len(train));losses=[]
        for start in range(0,len(order),8):
            inds=order[start:start+8].tolist();h,m=padded(train_h,inds)
            logits=mask_logits(head(tail(h),m),classes)
            ce=nn.functional.cross_entropy(logits.flatten(0,1),y[inds].flatten(),reduction='none').reshape(len(inds),-1)
            weights=active[inds].float()+.05*(~active[inds]).float();loss=(ce*weights).sum()/weights.sum()
            optim.zero_grad();loss.backward();nn.utils.clip_grad_norm_(trainable+list(head.parameters()),1);optim.step();losses.append(float(loss.detach()))
        rows=head_rows(head,tune_h,tune,classes,tail)
        nll=field_metrics(rows,tune,classes,1)['nll'];correct=sum(r['correct'] for r in rows)
        history.append(dict(epoch=epoch+1,loss=float(np.mean(losses)),tuning_correct=correct,tuning_active_field_nll=nll))
        if (correct,-nll)>best:
            best=(correct,-nll)
            torch.save(dict(state=head.state_dict(),layers={str(i):base.layers[i].state_dict() for i in range(cut,len(base.layers))},
                cut=cut,epoch=epoch+1,width=bank['questions'].shape[-1]),out/'checkpoint.pt')
        dump(out/'history.json',history);print(json.dumps(history[-1]),flush=True)
    saved=torch.load(out/'checkpoint.pt',weights_only=True);head.load_state_dict(saved['state'])
    for i,state in saved['layers'].items():base.layers[int(i)].load_state_dict(state)
    dump(out/'model.json',dict(base=str(MODELS['qwen']),last_trainable_layers=2,
        trainable_parameters=sum(p.numel() for p in trainable)+sum(p.numel() for p in head.parameters()),
        selected_epoch=saved['epoch'],epochs=6,seed=0,checkpoint_sha256=sha(out/'checkpoint.pt'),training_seconds=time.perf_counter()-tick,
        initialization_head_sha256=sha(work/'qwen-decision/checkpoint.pt'),head_lr=1e-4,decoder_lr=1e-5,
        selection='tuning exact plan correctness then active-field NLL',source_sha256=_RUNTIME_SOURCE_HASH))
    for split in ('tuning','calibration','fresh','conditional'):
        cases=read_rows(work/(split+'.jsonl'));data=torch.load(work/'qwen-prefix'/(split+'.pt'),weights_only=True)
        assert data['ids']==[c['id'] for c in cases]
        rows=head_rows(head,data['hidden'],cases,classes,tail)
        write_rows(out/(split+'-predictions.jsonl'),rows)
        print(json.dumps(dict(model='qwen-decision-adapted',split=split,**summary(rows))),flush=True)


def train_qwen(work,threads):
    torch.set_num_threads(threads);torch.manual_seed(0)
    out=work/'qwen-decision';out.mkdir(exist_ok=False)
    classes=json.loads((work/'classes.json').read_text());names=list(classes)
    folder=work/'qwen-features'
    bank=torch.load(folder/'choices.pt',weights_only=True)
    head=CandidateHead(bank['questions'].shape[-1],bank['questions'],bank['candidates'])
    train,tune=[read_rows(work/(s+'.jsonl')) for s in ('train','tuning')]
    train_h,tune_h=[torch.load(folder/(s+'.pt'),weights_only=True)['hidden'] for s in ('train','tuning')]
    y,active=targets(train,classes);optim=torch.optim.AdamW(head.parameters(),lr=0.001,weight_decay=0.01)
    history=[];best=(-1,float('-inf'));tick=time.perf_counter()
    for epoch in range(80):
        head.train();order=np.random.default_rng(epoch).permutation(len(train));losses=[]
        for start in range(0,len(order),16):
            inds=order[start:start+16].tolist();h,m=padded(train_h,inds)
            logits=mask_logits(head(h,m),classes)
            ce=nn.functional.cross_entropy(logits.flatten(0,1),y[inds].flatten(),reduction='none').reshape(len(inds),-1)
            weight=active[inds].float()+0.05*(~active[inds]).float()
            loss=(ce*weight).sum()/weight.sum()
            optim.zero_grad();loss.backward();nn.utils.clip_grad_norm_(head.parameters(),1);optim.step();losses.append(float(loss.detach()))
        rows=head_rows(head,tune_h,tune,classes);tuning_nll=field_metrics(rows,tune,classes,1)['nll']
        correct=sum(r['correct'] for r in rows);criterion=(correct,-tuning_nll)
        history.append(dict(epoch=epoch+1,loss=float(np.mean(losses)),tuning_correct=correct,tuning_active_field_nll=tuning_nll))
        if criterion>best:
            best=criterion;torch.save(dict(state=head.state_dict(),epoch=epoch+1,width=bank['questions'].shape[-1]),out/'checkpoint.pt')
        dump(out/'history.json',history)
        if (epoch+1)%10==0:print(json.dumps(history[-1]),flush=True)
    saved=torch.load(out/'checkpoint.pt',weights_only=True);head.load_state_dict(saved['state'])
    dump(out/'model.json',dict(frozen_backbone=str(MODELS['qwen']),trainable_parameters=sum(p.numel() for p in head.parameters()),
        selected_epoch=saved['epoch'],epochs=80,seed=0,checkpoint_sha256=sha(out/'checkpoint.pt'),training_seconds=time.perf_counter()-tick,
        selection='tuning exact plan correctness then active-field NLL',source_sha256=_RUNTIME_SOURCE_HASH))
    for split in ('tuning','calibration','fresh','conditional'):
        cases=read_rows(work/(split+'.jsonl'));data=torch.load(folder/(split+'.pt'),weights_only=True)
        assert data['ids']==[c['id'] for c in cases]
        rows=head_rows(head,data['hidden'],cases,classes);write_rows(out/(split+'-predictions.jsonl'),rows)
        print(json.dumps(dict(model='qwen-decision',split=split,**summary(rows))),flush=True)


def laya_run(work,threads):
    import laya
    from laya.common import build_sequence,collate_items,QTYPES
    torch.set_num_threads(threads)
    out=work/'laya';out.mkdir(exist_ok=True)
    agent=laya.load(str(ROOT/'models/laya-typed-decisions'),device='cpu',compile=False,fast=False)
    agent.model.float().eval()
    bf16=(work/'laya-precision-amendment.json').exists()
    if bf16:
        if not json.loads((work/'laya-precision-probe.json').read_text())['passed']:raise RuntimeError('Unqualified precision amendment')
        agent.dtype=torch.bfloat16;agent.amp_enabled=True
    classes=json.loads((work/'classes.json').read_text());variable=[k for k,v in classes.items() if len(v)>1]
    contract=LAYA_CONTRACT
    questions={k:dict(t='choice',ins=field_question(k),criteria={f'v{i}':option_text(k,v) for i,v in enumerate(classes[k])}) for k in variable}
    # API normalization uses internal choice dictionaries with keys, not a new output parser.
    internal={k:dict(t=q['t'],ins=q['ins'],crit=q['criteria']) for k,q in questions.items()}
    def api_parity(case,logits):
        previous_t,previous_map=agent.temperature,agent.temperature_by_options
        agent.temperature=[1.,1.,1.];agent.temperature_by_options={};agent.amp_enabled=bf16
        native_questions={k:dict(type='choice',instructions=field_question(k),
            criteria={f'v{i}':option_text(k,v) for i,v in enumerate(classes[k])}) for k in (variable if bf16 else ('outcome','pred_op'))}
        native=agent.system_one(contract+'\n'+features(public_input(case)),native_questions)
        answers=native.get('answers',native);errors={}
        for k in native_questions:
            p=softmax(logits[k]);actual=np.array(list(answers[k]['probabilities'].values()))
            errors[k]=float(np.abs(actual-p).max())
            tolerance=.001 if bf16 else .0002
            if not np.allclose(actual,p,atol=tolerance,rtol=0) or int(actual.argmax())!=int(p.argmax()):
                dump(out/'native-api-parity-failure.json',dict(field=k,error=errors[k],native=actual.tolist(),adapter=p.tolist(),bfloat16=bf16))
                raise RuntimeError('Native Laya API/logit adapter mismatch')
        dump(out/'native-api-parity.json',dict(calibration_id=case['id'],max_probability_errors=errors,
            raw_temperature=1,rounded_native_probabilities=True,gold_labels_used=False,bfloat16=bf16))
        agent.temperature,agent.temperature_by_options=previous_t,previous_map
    existing=out/'calibration-predictions.jsonl'
    if existing.exists():api_parity(read_rows(work/'calibration.jsonl')[0],read_rows(existing)[0]['field_logits'])
    max_tokens=0;decisions=0
    for split in ('calibration','fresh','conditional'):
        path=out/(split+'-predictions.jsonl')
        done=read_rows(path) if path.exists() else []
        cases=read_rows(work/(split+'.jsonl'))
        assert [r['id'] for r in done]==[c['id'] for c in cases[:len(done)]]
        for index,case in enumerate(cases[len(done):],len(done)):
            state=contract+'\n'+features(public_input(case));items=[]
            for k in variable:
                ids,markers,stats,trunc=build_sequence(agent.tok,state,internal[k],max_len=1024,head_max_len=256,return_stats=True,return_truncation_stats=True)
                if trunc['truncated'] or stats['options_distinct']!=len(classes[k]) or len(markers)!=len(classes[k]):
                    raise RuntimeError('Laya input/options would be truncated')
                max_tokens=max(max_tokens,len(ids))
                items.append(dict(ids=ids,markers=markers,qtype=QTYPES['choice']))
            all_logits={k:[0.] for k in classes if len(classes[k])==1};tick=time.perf_counter()
            for start in range(0,len(items),24):
                b=collate_items([items[start:start+24]],agent.tok.pad_token_id)
                with torch.inference_mode(),torch.autocast('cpu',dtype=torch.bfloat16,enabled=bf16,cache_enabled=False):
                    z,_=agent.model(**{k:b[k] for k in ('input_ids','attention_mask','marker_pos','marker_mask','qtype')})
                for k,row in zip(variable[start:start+24],z.tolist()):all_logits[k]=row[:len(classes[k])]
            row=decode(case,all_logits,classes,time.perf_counter()-tick)
            if split=='calibration' and index==0:api_parity(case,all_logits)
            row.update(input_tokens_max=max(map(lambda x:len(x['ids']),items)),input_tokens_sum=sum(len(x['ids']) for x in items),
                question_count=len(items),native_choice_logits=True,question_batch_size=24,threads=threads,
                precision='bfloat16 CPU autocast, float32 logits' if bf16 else 'float32 CPU')
            with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            done.append(row);decisions+=len(items)
            if (index+1)%10==0:print(json.dumps(dict(model='laya',split=split,completed=index+1,correct=sum(r['correct'] for r in done))),flush=True)
        dump(out/(split+'-summary.json'),summary(done))
    dump(out/'model.json',dict(package_version=laya.__version__,source_revision='a478221bcad24d1a9c47b361c79328ebd2b100c6',
        model_download=json.loads((work/'laya-download.json').read_text()),max_tokens=max_tokens,raw_logits=True,
        maintenance_finetuned=False,precision='bfloat16 CPU autocast, float32 logits' if bf16 else 'float32 CPU',native_sequential_layout=True,questions_scored_this_invocation=decisions,
        files_sha256={p.relative_to(ROOT/'models/laya-typed-decisions').as_posix():sha(p) for p in (ROOT/'models/laya-typed-decisions').rglob('*') if p.is_file() and '.cache' not in p.parts}))


def controls(work,threads):
    from transformers import AutoModel,AutoTokenizer
    torch.set_num_threads(threads)
    classes=json.loads((work/'classes.json').read_text())
    for name in ('tfidf','minilm'):
        out=work/name;out.mkdir(exist_ok=False)
        if name=='tfidf':vectorizer,heads=pickle.loads((OLD/'tfidf/model.pkl').read_bytes())
        else:
            saved=torch.load(OLD/'minilm/checkpoint.pt',weights_only=True);assert saved['classes']==classes
            base=AutoModel.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'),local_files_only=True)
            base.load_state_dict(saved['base']);base.eval()
            tok=AutoTokenizer.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'),local_files_only=True)
            heads=nn.ModuleList([nn.Linear(base.config.hidden_size,len(v)) for v in classes.values()]);heads.load_state_dict(saved['heads']);heads.eval()
        for split in ('calibration','fresh','conditional'):
            cases=read_rows(work/(split+'.jsonl'));records=[]
            for case in cases:
                if name=='tfidf':
                    x=vectorizer.transform([features(public_input(case))]);z={}
                    for k,h in heads.items():
                        if isinstance(h,str):z[k]=[0.]
                        else:
                            assert list(h.classes_)==classes[k]
                            z[k]=np.log(np.clip(h.predict_proba(x)[0],1e-30,1)).tolist()
                else:
                    b=tok(features(public_input(case)),return_tensors='pt',truncation=False)
                    assert b['input_ids'].shape[1]<=256
                    with torch.inference_mode():
                        h=base(**b).last_hidden_state;m=b['attention_mask'].unsqueeze(-1);pooled=(h*m).sum(1)/m.sum(1)
                        z={k:head(pooled)[0].tolist() for k,head in zip(classes,heads)}
                records.append(decode(case,z,classes))
            if split!='calibration':
                previous=read_rows(PARENT/name/(split+'-predictions.jsonl'))
                assert [r['raw_output'] for r in records]==[r['raw_output'] for r in previous], 'Control predictions changed'
            write_rows(out/(split+'-predictions.jsonl'),records)
            print(json.dumps(dict(model=name,split=split,**summary(records))),flush=True)


def selected_token_logps(model,prompt,generated,prefix=None,prefix_cache=None):
    if not generated:return []
    with torch.inference_mode():
        ids=prompt+generated[:-1];offset=0
        if prefix_cache is None:h=model.model(input_ids=torch.tensor([ids]),use_cache=False).last_hidden_state
        else:
            offset=len(prefix);assert prompt[:offset]==prefix and len(prompt)>offset
            h=model.model(input_ids=torch.tensor([ids[offset:]]),past_key_values=copy.deepcopy(prefix_cache),use_cache=True).last_hidden_state
        h=h[:,len(prompt)-1-offset:,:]
        z=model.lm_head(h);cap=getattr(model.config,'final_logit_softcapping',None)
        if cap:z=torch.tanh(z/cap)*cap
        return z[0].log_softmax(-1).gather(1,torch.tensor(generated)[:,None])[:,0].tolist()


def generator_confidence(work,name,threads):
    """Same selected generators; calibrate a token-confidence surrogate at plan level."""
    from maintenance_sft import load,serialize,unwrap
    tok,model=load(name,threads)
    saved=torch.load(PARENT/name/'checkpoint.pt',weights_only=True)
    for i,state in saved['layers'].items():model.model.layers[int(i)].load_state_dict(state)
    model.eval();tok.padding_side='left'
    if tok.pad_token_id is None:tok.pad_token_id=tok.eos_token_id
    eos=[151645] if name=='qwen' else [1,50,tok.convert_tokens_to_ids('<end_of_turn>'),tok.convert_tokens_to_ids('<start_function_response>')]
    eos=sorted(set(eos));out=work/(name+'-generative');out.mkdir(exist_ok=True)
    calpath=out/'calibration-native.jsonl'
    done=read_rows(calpath) if calpath.exists() else []
    cases=read_rows(work/'calibration.jsonl')
    assert [r['id'] for r in done]==[c['id'] for c in cases[:len(done)]]
    for start in range(len(done),len(cases),4):
        group=cases[start:start+4]
        jobs=[serialize(tok,name,dict(public_input(c),id=c['id'])) for c in group]
        maximum=max(len(j['prompt_ids']) for j in jobs)
        ids=torch.tensor([[tok.pad_token_id]*(maximum-len(j['prompt_ids']))+j['prompt_ids'] for j in jobs])
        mask=torch.tensor([[0]*(maximum-len(j['prompt_ids']))+[1]*len(j['prompt_ids']) for j in jobs])
        with torch.inference_mode():
            outputs=model.generate(input_ids=ids,attention_mask=mask,max_new_tokens=256,do_sample=False,use_cache=True,
                eos_token_id=eos,pad_token_id=tok.pad_token_id,repetition_penalty=1.)
        for i,c in enumerate(group):
            generated=outputs[i,maximum:].tolist();stop=next((j for j,v in enumerate(generated) if v in eos),len(generated));generated=generated[:stop]
            native=tok.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
            try:raw=unwrap(name,native);error=None
            except ValueError as exc:raw='';error=str(exc)
            row=verdict(c,raw,0,actual_prompt_ids=jobs[i]['prompt_ids'],generated_ids=generated,native_output=native,native_parse_error=error)
            with calpath.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(dict(model=name,phase='calibration-generation',completed=min(start+4,len(cases)))),flush=True)
    scoring_sources={split:read_rows(calpath if split=='calibration' else PARENT/name/(split+'-predictions.jsonl')) for split in ('calibration','fresh','conditional')}
    prefix=list(scoring_sources['calibration'][0]['actual_prompt_ids'])
    for rows in scoring_sources.values():
        for row in rows:
            other=row['actual_prompt_ids'];limit=min(len(prefix),len(other))
            end=next((i for i in range(limit) if prefix[i]!=other[i]),limit);prefix=prefix[:end]
    with torch.inference_mode():cache=model.model(input_ids=torch.tensor([prefix]),use_cache=True).past_key_values
    first=scoring_sources['calibration'][0]
    direct=selected_token_logps(model,first['actual_prompt_ids'],first['generated_ids'])
    cached=selected_token_logps(model,first['actual_prompt_ids'],first['generated_ids'],prefix,cache)
    difference=max((abs(a-b) for a,b in zip(direct,cached)),default=0.)
    enabled=difference<.001
    dump(out/'prefix-cache-qualification.json',dict(prefix_tokens=len(prefix),maximum_selected_log_probability_difference=difference,enabled=enabled,calibration_only=True))
    for split in ('calibration','fresh','conditional'):
        path=out/(split+'-predictions.jsonl')
        completed=read_rows(path) if path.exists() else []
        source=scoring_sources[split]
        assert [r['id'] for r in completed]==[r['id'] for r in source[:len(completed)]]
        for index,row in enumerate(source[len(completed):],len(completed)):
            prompt=row['actual_prompt_ids'];generated=row['generated_ids']
            assert len(prompt)+len(generated)<=1024
            if generated:
                logp=selected_token_logps(model,prompt,generated,prefix if enabled else None,cache if enabled else None)
                minimum=math.exp(min(logp));geomean=math.exp(float(np.mean(logp)))
            else:logp=[];minimum=0.;geomean=0.
            savedrow=dict(row,selected_token_log_probabilities=logp,token_min_probability=minimum,token_geometric_mean_probability=geomean)
            with path.open('a',encoding='utf-8') as f:f.write(json.dumps(savedrow)+'\n')
            if (index+1)%20==0:print(json.dumps(dict(model=name,phase='confidence',split=split,completed=index+1)),flush=True)
    dump(out/'model.json',dict(checkpoint_sha256=sha(PARENT/name/'checkpoint.pt'),precision='float32 CPU',
        maintenance_weights_unchanged=True,fresh_stress_outputs_reused_bytewise_semantics=True,
        confidence='minimum selected-token probability excluding EOS; separate plan-level calibration. Not a choice distribution or a sequence correctness probability.',
        calibration_generated=True,context=1024,greedy=True,grammar=False,repair=False))


def softmax(z,temperature=1):
    z=np.asarray(z,dtype=float)/temperature;z-=z.max();p=np.exp(z);return p/p.sum()


def field_metrics(rows,cases,classes,temperature):
    nll=[];brier=[];confidence=[];correct=[];operator=[]
    for r,c in zip(rows,cases):
        assert r['id']==c['id'];gold=flatten(c['gold'],c['catalog'])
        for k in active_fields(gold):
            t=temperature[k] if isinstance(temperature,dict) else temperature
            p=softmax(r['field_logits'][k],t)
            target=classes[k].index(gold[k])
            if len(p)==1: continue
            nll.append(-math.log(max(p[target],1e-30)))
            one=np.zeros(len(p));one[target]=1;brier.append(float(((p-one)**2).sum()))
            confidence.append(float(p.max()));correct.append(int(p.argmax()==target))
            if k=='pred_op':operator.append(dict(id=r['id'],probabilities=p.tolist(),target=target))
    return dict(count=len(nll),nll=float(np.mean(nll)),brier=float(np.mean(brier)),
        accuracy=float(np.mean(correct)),ece=ece(confidence,correct),operator=operator)


def ece(confidence,correct,bins=10):
    p=np.asarray(confidence);y=np.asarray(correct);result=0.
    for i in range(bins):
        m=(p>=i/bins)&((p<(i+1)/bins) if i+1<bins else (p<=1))
        if m.any():result+=float(m.mean()*abs(p[m].mean()-y[m].mean()))
    return result


def plan_score(row,temperature):
    if not row['valid']:return 0.
    keys=active_fields(row['predicted_fields'])
    return min(float(softmax(row['field_logits'][k],temperature).max()) for k in keys)


def fit_plan_map(rows,scores):
    from sklearn.linear_model import LogisticRegression
    y=np.array([r['correct'] for r in rows],dtype=int)
    def xscore(scores):
        p=np.clip(scores,1e-6,1-1e-6);return np.log(p/(1-p))[:,None]
    if len(set(y))==2:
        model=LogisticRegression(C=1,random_state=0).fit(xscore(scores),y)
        slope=float(model.coef_[0,0]);intercept=float(model.intercept_[0])
        if slope<0:slope=0.;intercept=float(math.log((y.sum()+1)/(len(y)-y.sum()+1)))
    else:slope=0.;intercept=float(math.log((y.sum()+1)/(len(y)-y.sum()+1)))
    def calibrated(score):
        z=slope*xscore(np.array([score]))[0,0]+intercept
        return float(1/(1+math.exp(-np.clip(z,-50,50))))
    p=np.array([calibrated(s) if r['valid'] else 0. for s,r in zip(scores,rows)])
    thresholds={str(c):float(np.quantile(p,1-c)) for c in (.25,.5,.75)}
    return dict(plan_calibration_slope=slope,plan_calibration_intercept=intercept,coverage_thresholds=thresholds),calibrated


def uncertainty_metrics(rows,plan_p,thresholds):
    from scipy.stats import beta
    correct=[int(r['correct']) for r in rows]
    metrics=dict(brier=float(np.mean((np.array(plan_p)-correct)**2)),ece=ece(plan_p,correct),
        nll=float(np.mean([-math.log(max(p if y else 1-p,1e-30)) for p,y in zip(plan_p,correct)])))
    for label,key in (('valid_only','valid'),('accepted_plans_only','accepted')):
        indices=[i for i,r in enumerate(rows) if r[key]]
        if indices:
            pp=[plan_p[i] for i in indices];yy=[correct[i] for i in indices]
            metrics[label]=dict(count=len(indices),brier=float(np.mean((np.array(pp)-yy)**2)),ece=ece(pp,yy),
                nll=float(np.mean([-math.log(max(p if y else 1-p,1e-30)) for p,y in zip(pp,yy)])))
        else:metrics[label]=dict(count=0,brier=None,ece=None,nll=None)
    risk={}
    for label,threshold in thresholds.items():
        chosen=[r for r,p in zip(rows,plan_p) if r['valid'] and p>=threshold]
        wrong=sum(not r['correct'] for r in chosen);chosen_plans=[r for r in chosen if r['accepted']]
        risk[label]=dict(threshold=threshold,selected=len(chosen),coverage=len(chosen)/len(rows),
            wrong=wrong,error_rate=wrong/len(chosen) if chosen else None,
            one_sided_95_percent_error_upper=float(beta.ppf(.95,wrong+1,len(chosen)-wrong)) if len(chosen)>wrong else 1.,
            selected_plans=len(chosen_plans),wrong_selected_plans=sum(not r['correct'] for r in chosen_plans),
            correct_actionable_completion=sum(r['correct'] and r['accepted'] for r in chosen)/sum(r['actionable'] for r in rows))
    return metrics,risk


def report(work):
    from scipy.optimize import minimize_scalar
    classes=json.loads((work/'classes.json').read_text());result={}
    for name in probability_models(work):
        folder=work/name
        cal=read_rows(folder/'calibration-predictions.jsonl');calcases=read_rows(work/'calibration.jsonl')
        opt=minimize_scalar(lambda x:field_metrics(cal,calcases,classes,math.exp(x))['nll'],bounds=(-3,4),method='bounded')
        temperature=math.exp(float(opt.x))
        scores=np.array([plan_score(r,temperature) for r in cal])
        mapping,calibrated=fit_plan_map(cal,scores);thresholds=mapping['coverage_thresholds']
        params=dict(temperature=temperature,**mapping,calibration_records=len(cal),calibration_sha256=sha(work/'calibration.jsonl'))
        dump(folder/'calibration.json',params);result[name]={'calibration':params,'splits':{}}
        for split in ('fresh','conditional'):
            rows=read_rows(folder/(split+'-predictions.jsonl'));cases=read_rows(work/(split+'.jsonl'))
            for r,c in zip(rows,cases):
                v=verdict(c,r['raw_output'],0)
                assert all(v[k]==r[k] for k in ('correct','valid','accepted'))
            scales=[('raw',1),('temperature_scaled',temperature)]
            if name.startswith('laya'):
                cfg=json.loads((ROOT/'models/laya-typed-decisions/rl_agent_config.json').read_text())
                vendor={}
                for k,vs in classes.items():
                    size=len(vs);bucket='2' if size<=2 else ('3-5' if size<=5 else ('6-10' if size<=10 else '11+'))
                    vendor[k]=float(np.clip(cfg.get('temperature_by_options',{}).get('choice:'+bucket,cfg['temperature'][0]),.5,5))
                scales.append(('vendor_temperature',vendor))
            metrics={label:field_metrics(rows,cases,classes,t) for label,t in scales}
            for m in metrics.values():
                operators=m.pop('operator')
                if operators:
                    pp=[np.array(x['probabilities']) for x in operators];yy=[x['target'] for x in operators]
                    m['conditional_operator']=dict(count=len(pp),accuracy=float(np.mean([p.argmax()==i for p,i in zip(pp,yy)])),
                        nll=float(np.mean([-math.log(max(p[i],1e-30)) for p,i in zip(pp,yy)])),
                        brier=float(np.mean([sum((p-np.eye(len(p))[i])**2) for p,i in zip(pp,yy)])),ece=ece([p.max() for p in pp],[p.argmax()==i for p,i in zip(pp,yy)]))
            plan_p=[calibrated(plan_score(r,temperature)) if r['valid'] else 0. for r in rows]
            plan_metrics,risk=uncertainty_metrics(rows,plan_p,thresholds)
            s=summary(rows);s.update(field_calibration=metrics,plan_calibration=plan_metrics,risk_coverage=risk)
            if not name.startswith('laya'):
                s['inference_seconds']=None
                s['timing_scope']='End-to-end timing not collected; zero row times are placeholders, not zero-cost inference.'
            else:s['timing_scope']='Observed complete choice-query loop; no controlled device comparison or energy measurement.'
            result[name]['splits'][split]=s
            write_rows(folder/(split+'-calibrated.jsonl'),[dict(id=r['id'],plan_correct_probability=p,valid=r['valid'],correct=r['correct'],
                field_probabilities={k:{v:float(prob) for v,prob in zip(classes[k],softmax(z,temperature))} for k,z in r['field_logits'].items()}) for r,p in zip(rows,plan_p)])
    for name in ('qwen-generative','functiongemma-generative'):
        folder=work/name;cal=read_rows(folder/'calibration-predictions.jsonl')
        mapping,calibrated=fit_plan_map(cal,np.array([r['token_min_probability'] for r in cal]))
        params=dict(**mapping,calibration_records=len(cal),calibration_sha256=sha(work/'calibration.jsonl'),
            surrogate='minimum selected-token probability excluding EOS; not a typed choice distribution')
        dump(folder/'calibration.json',params);result[name]={'calibration':params,'splits':{}}
        for split in ('fresh','conditional'):
            rows=read_rows(folder/(split+'-predictions.jsonl'));cases=read_rows(work/(split+'.jsonl'))
            for r,c in zip(rows,cases):
                v=verdict(c,r['raw_output'],0);assert all(v[k]==r[k] for k in ('correct','valid','accepted'))
            p=[calibrated(r['token_min_probability']) if r['valid'] else 0. for r in rows]
            metrics,risk=uncertainty_metrics(rows,p,mapping['coverage_thresholds'])
            s=summary(rows);s.update(plan_calibration=metrics,risk_coverage=risk,field_calibration=None)
            s['timing_scope']='Archived greedy decoding durations only; excludes new confidence scoring; not matched device benchmarking.'
            result[name]['splits'][split]=s
            write_rows(folder/(split+'-calibrated.jsonl'),[dict(id=r['id'],plan_correct_probability=v,valid=r['valid'],correct=r['correct']) for r,v in zip(rows,p)])
    historical=json.loads((PARENT/'comparison.json').read_text())['results']
    result['historical_accuracy']={k:{s:historical[k][s] for s in ('fresh','conditional')} for k in ('rules','qwen','functiongemma')}
    dump(work/'comparison.json',result)
    lines=['# Maintenance probability-output pilot','',
        'Qwen shared candidate head with frozen and final-two-block-adapted variants; released Laya without maintenance adaptation. The selected Laya runtime is recorded in laya-runtime-selection.json; other models use float32 CPU. New calibration records have distinct raw public inputs across splits, with normalized template overlap detailed in overlap-audit.json. Evaluation remains previously inspected development evidence.','',
        '| Model | Fresh correct /120 | Fresh conditional /20 | Stress correct /64 | Stress accepted /64 | Stress wrong accepted | Stress operator accuracy | Stress operator NLL, raw → scaled | Stress accepted-plan Brier |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name in probability_models(work):
        f=result[name]['splits']['fresh'];s=result[name]['splits']['conditional']
        raw=s['field_calibration']['raw']['conditional_operator'];scaled=s['field_calibration']['temperature_scaled']['conditional_operator']
        brier=s['plan_calibration']['accepted_plans_only']['brier'];brier_text=f'{brier:.3f}' if brier is not None else 'N/A'
        lines.append(f"| {name} | {f['correct']} | {f['strata']['conditional']['correct']} | {s['correct']} | {s['accepted']} | {s['incorrect_accepted']} | {scaled['accuracy']:.3f} | {raw['nll']:.3f} → {scaled['nll']:.3f} | {brier_text} |")
    for name in ('qwen-generative','functiongemma-generative'):
        f=result[name]['splits']['fresh'];s=result[name]['splits']['conditional']
        brier=s['plan_calibration']['accepted_plans_only']['brier'];brier_text=f'{brier:.3f}' if brier is not None else 'N/A'
        lines.append(f"| {name} | {f['correct']} | {f['strata']['conditional']['correct']} | {s['correct']} | {s['accepted']} | {s['incorrect_accepted']} | N/A | N/A | {brier_text} |")
    lines+=['','## Existing generation controls','',
        'Rules: fresh120/120, stress64/64. Generator weights and fresh/stress outputs remain unchanged. New calibration outputs are generated with the same float32 greedy setup. Whole-plan confidence uses a separately calibrated minimum selected-token probability, measured by teacher-forced logits; this is a surrogate, not a typed choice distribution. Operator choice NLL is therefore unavailable for generators.',
        '', '## Scope and interpretation','',
        'All probability models use the original training-derived categorical field domains and the same unflatten/validator. Constants are fixed from training, not inferred from evaluation. No semantic repairs, fallback rules or gold-conditioned candidate pruning are used.',
        'Qwen encodes the public state once and scores candidate text embeddings with a shared question-conditioned head. The frozen variant updates only the head; the adapted variant additionally trains the final two decoder blocks for six epochs. Both differ from NanoJev’s per-candidate state/question encoding. Laya receives human-readable field questions and candidate descriptions; it has no maintenance weight updates.',
        'Field metrics use gold-active fields solely for scoring; predictions and plan confidence use predicted structural dependencies. Plan confidence is separately calibrated from minimum predicted-field probability; field probabilities are not multiplied as if independent.',
        'Temperature and plan calibration are fitted on the same120 calibration records. ECE uses10 equal-width bins. Fixed thresholds come from calibration confidence quantiles; actual evaluation coverage and errors are in comparison.json. No low-error guarantee follows from this sample size or from observing zero errors.',
        'The table uses accepted-plan Brier, with N/A when no plans are accepted. Full-pipeline, valid-decision and accepted-plan calibration metrics are retained separately: invalid outputs receive known correctness probability0, which can trivially improve full-pipeline Brier for a model that fails to produce useful decisions.',
        'Calibration under conditional recombination may degrade even when it looks good on familiar templates. A typed output distribution alone does not establish semantic correctness. One seed, unequal adaptation budgets, and no FPGA speed/energy or quantization qualification.']
    (work/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=['prepare','features','prefix','train','train-adapted','laya','controls','generators','report'])
    ap.add_argument('--work',type=Path,default=WORK);ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--generator',choices=['qwen','functiongemma'],default='qwen')
    a=ap.parse_args()
    if a.phase!='prepare':
        ledger=a.work/'invocations';ledger.mkdir(exist_ok=True)
        stem=f'{a.phase}-{time.time_ns()}';(ledger/(stem+'.py')).write_bytes(_RUNTIME_SOURCE_BYTES)
        dump(ledger/(stem+'.json'),dict(phase=a.phase,source_sha256=_RUNTIME_SOURCE_HASH,protocol_sha256=sha(a.work/'protocol.json'),
            arguments=dict(phase=a.phase,threads=a.threads,generator=a.generator,work=str(a.work))))
    if a.phase=='prepare':prepare(a.work)
    elif a.phase=='features':qwen_features(a.work,a.threads)
    elif a.phase=='prefix':qwen_prefix(a.work,a.threads)
    elif a.phase=='train':train_qwen(a.work,a.threads)
    elif a.phase=='train-adapted':train_adapted(a.work,a.threads)
    elif a.phase=='laya':laya_run(a.work,a.threads)
    elif a.phase=='controls':controls(a.work,a.threads)
    elif a.phase=='generators':generator_confidence(a.work,a.generator,a.threads)
    else:report(a.work)


if __name__=='__main__':main()
