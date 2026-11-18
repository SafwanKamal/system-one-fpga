"""CPU-only maintenance decoder fine-tuning and frozen-baseline comparison.

Train final decoder blocks with completion-only loss, selecting by tuning loss.
Frozen-prefix caching is checked against the unmodified backbone before training.
All decoding uses the full vocabulary without grammar, repair, or tool execution.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import pickle
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from maintenance_pilot import dump, read_rows, write_rows, sha, verdict, summary
from sysone.v2.maintenance.dataset import public_input, make_case, STRATA
from sysone.v2.maintenance.revision2 import prompt, SYSTEM_V2, mention_order, _replace, calibration_subset
from sysone.v2.maintenance.schema import encode, parse, node, plan
from sysone.v2.maintenance.baselines import features, unflatten, rules

PARENT = ROOT / 'build/v2/maintenance-pilot-v2-context1024'
DEFAULT = ROOT / 'build/v2/maintenance-sft-v3'
FG = Path.home() / '.cache/huggingface/hub/models--google--functiongemma-270m-it/snapshots/39eccb091651513a5dfb56892d3714c1b5b8276c'
MODELS = {'qwen': ROOT / 'models/Qwen3-0.6B-HF', 'functiongemma': FG}
PREFIX = '<start_function_call>call:submit_maintenance_plan{plan_json:<escape>'
SUFFIX = '<escape>}<end_function_call>'
TOOLS = [dict(type='function', function=dict(name='submit_maintenance_plan',
    description='Submit the complete typed maintenance decision, including clarification or rejection.',
    parameters=dict(type='object', properties=dict(plan_json=dict(type='string',
        description='The exact maintenance outcome JSON array specified in the developer instructions.')),
        required=['plan_json'])))]


def check_seal(folder):
    sealed = json.loads((folder / 'final-seal.json').read_text())['files_sha256']
    for name, digest in sealed.items():
        if sha(folder / name) != digest:
            raise RuntimeError('Sealed input changed: ' + name)
    return dict(files=len(sealed), seal_sha256=sha(folder / 'final-seal.json'))


def prepare(work):
    parent = check_seal(PARENT)
    work.mkdir(parents=True, exist_ok=False)
    for split in ('train', 'tuning', 'audit'):
        shutil.copyfile(PARENT / (split + '.jsonl'), work / (split + '.jsonl'))
    fresh = []
    for category in STRATA:
        for i in range(20):
            case = make_case('audit', category, 6000 + i)
            mapping = {old: f'{kind}{n}' for kind in 'PMF' for old, n in
                zip([a for a in case['catalog'] if a.startswith(kind)], range(61, 65))}
            case = _replace(case, mapping)
            case['id'] = f'v3-fresh-{category}-{i:03d}'
            case['catalog'] = mention_order(public_input(case))
            case['semantic_signature'] = json.dumps(case['gold'], sort_keys=True)
            fresh.append(case)
    write_rows(work / 'fresh.jsonl', fresh)
    sources = [Path(__file__)] + list((ROOT / 'src/sysone/v2/maintenance').glob('*.py')) + [ROOT / 'scripts/v2/maintenance_pilot.py']
    hashes = {}
    for p in sources:
        rel = p.relative_to(ROOT); target = work / 'sources' / rel
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, target)
        hashes[rel.as_posix()] = sha(p)
    dump(work / 'protocol.json', dict(parent=parent, source_sha256=hashes,
        data_sha256={s: sha(work / (s + '.jsonl')) for s in ('train', 'tuning', 'audit', 'fresh')},
        train_count=720, tuning_count=120, regression_count=120, fresh_count=120,
        seed=0, epochs=6, last_trainable_blocks=2, learning_rate=0.00005,
        batch_size=1, accumulation=4, checkpoint_selection='minimum tuning completion-token cross entropy; earlier epoch wins ties',
        context=1024, output_reservation=256, training_dtype='float32',
        inference='CPU float32 reference, full vocabulary, greedy, batch4; same for both trained generators',
        qwen_format='existing full contract, zero demonstrations, fixed nonthinking prefix',
        functiongemma_format='official native function template; one submit_maintenance_plan(plan_json:string) call; exact lossless wrapper around same payload',
        evaluation='fresh is same-template development replication; audit is previously inspected regression, neither is a sealed publication test',
        fresh_data_policy='new seeded values and asset identifiers; no independent authorship or structural holdout',
        tuning_weight_updates=False, audit_weight_updates=False, fresh_weight_updates=False,
        grammar=False, repair=False, board_access=False, energy_measured=False))
    print(json.dumps({'prepared': str(work), 'parent': parent}), flush=True)


def conditional_cases():
    import itertools
    catalog=[f'{kind}{i}' for kind in 'PMF' for i in range(71,75)]
    phrases=dict(gt='is greater than',ge='is at least',lt='is below',le='is at most')
    rows=[]
    for i,(op,rhs,action,history,priority) in enumerate(itertools.product(
            ('gt','ge','lt','le'),(70,'limit'),('draft_report','request_inspection'),(False,True),('normal','high'))):
        asset=catalog[i%len(catalog)]
        steps=[node('read_metric',asset,metric='temperature')]
        if history: steps.append(node('read_history',asset,guard=True,metric='temperature',count=3))
        steps.append(node(action,asset,guard=True,priority=priority,evidence=list(range(len(steps)))))
        target=plan(*steps,predicate=dict(source=0,op=op,rhs=rhs))
        threshold='70 C' if rhs==70 else 'its configured limit'
        extra='fetch 3 recent temperature readings and ' if history else ''
        action_text='draft a report' if action=='draft_report' else 'request an inspection'
        request=f"Read {asset}'s temperature. If it {phrases[op]} {threshold}, {extra}{action_text} with {priority} priority citing all readings."
        case=dict(id=f'v3-conditional-{i:03d}',split='conditional',stratum='conditional',request=request,
            context={},catalog=list(catalog),gold=target,provenance='authored_counterbalanced_development_stress',
            template_family='crossed_condition_action_threshold_history_priority')
        case['catalog']=mention_order(public_input(case)); rows.append(case)
    return rows


def prepare_conditional(work):
    path=work/'conditional.jsonl'
    if path.exists(): raise FileExistsError(path)
    if any(work.glob('*/audit-predictions.jsonl')) or any(work.glob('qwen*/fresh-predictions.jsonl')) or any(work.glob('functiongemma*/fresh-predictions.jsonl')):
        raise RuntimeError('Conditional stress set must be frozen before generator evaluation')
    rows=conditional_cases()
    for c in rows: assert parse(encode(c['gold']),c['catalog'])==c['gold']
    write_rows(path,rows)
    dump(work/'conditional-protocol.json',dict(count=64,data_sha256=sha(path),created_before_generator_evaluation=True,
        factors=dict(operators=4,threshold_types=2,actions=2,history=2,priorities=2),
        weight_updates=False,checkpoint_selection=False,independently_authored=False,
        purpose='Break condition/action/threshold correlations in the original templates; development stress only',
        source_sha256=sha(Path(__file__))))
    print(json.dumps(dict(conditional_cases=len(rows),sha256=sha(path))),flush=True)


def prepare_references(work):
    path=work/'pretrained-reference-ids.json'
    if path.exists(): raise FileExistsError(path)
    if any(work.glob('qwen*/fresh-predictions.jsonl')) or any(work.glob('functiongemma*/fresh-predictions.jsonl')):
        raise RuntimeError('Reference subset must be frozen before generator evaluation')
    chosen=calibration_subset(read_rows(work/'fresh.jsonl'))
    dump(path,dict(ids=[c['id'] for c in chosen],count=24,per_stratum=4,
        selection='first four distinct public inputs per stratum; no model predictions or correctness used',
        purpose='bounded matched-backend before/after reference; main adapted evaluation remains all 120 fresh + 64 stress + 120 regression',
        selected_before_generator_evaluation=True))
    print(json.dumps(dict(pretrained_reference_cases=len(chosen),sha256=sha(path))),flush=True)


def serialize(tok, name, case, training=False):
    if name == 'qwen':
        text = prompt(public_input(case))
        target = encode(case['gold']) + '<|im_end|>' if training else None
    else:
        messages = [dict(role='developer', content='You are a model that can do function calling with the following functions. ' +
            SYSTEM_V2 + ' Return exactly one submit_maintenance_plan call with the outcome array as plan_json.'),
            dict(role='user', content=json.dumps(public_input(case), separators=(',', ':')))]
        text = tok.apply_chat_template(messages, tools=TOOLS, add_generation_prompt=True, tokenize=False)
        target = None
        if training:
            reply = dict(role='assistant', tool_calls=[dict(type='function', function=dict(
                name='submit_maintenance_plan', arguments=dict(plan_json=encode(case['gold']))))])
            full = tok.apply_chat_template(messages + [reply], tools=TOOLS, tokenize=False)
            if not full.startswith(text):
                raise RuntimeError('Training/inference prefix mismatch')
            target = full[len(text):]
            if target != PREFIX + encode(case['gold']) + SUFFIX + '<start_function_response>':
                raise RuntimeError('Unexpected official function target: ' + repr(target))
    ids = tok.encode(text, add_special_tokens=False)
    if len(ids) + 256 > 1024:
        raise RuntimeError('Prompt exceeds 1024 total reserved context')
    result = dict(id=case['id'], prompt=text, prompt_ids=ids)
    if training:
        completion = tok.encode(target, add_special_tokens=False)
        if len(ids) + len(completion) > 1024:
            raise RuntimeError('Training sequence exceeds context')
        result.update(target=target, input_ids=ids + completion, prompt_tokens=len(ids), target_ids=completion)
    return result


def unwrap(name, raw):
    if name == 'qwen':
        return raw
    if not raw.startswith(PREFIX) or not raw.endswith(SUFFIX):
        raise ValueError('Expected exactly one native submit_maintenance_plan call')
    payload = raw[len(PREFIX):-len(SUFFIX)]
    if '<escape>' in payload:
        raise ValueError('Unexpected native string delimiter inside payload')
    return payload


def load(name, threads):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(threads); torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(str(MODELS[name]), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(str(MODELS[name]), local_files_only=True,
        dtype=torch.float32, attn_implementation='sdpa')
    model.eval(); model.requires_grad_(False)
    return tok, model


def cached_tail(model, hidden, cut):
    import torch
    from transformers.masking_utils import create_causal_mask, create_sliding_window_causal_mask
    base = model.model; config = model.config
    positions = torch.arange(hidden.shape[1]).unsqueeze(0)
    args = dict(config=config, inputs_embeds=hidden, attention_mask=None, past_key_values=None, position_ids=positions)
    masks = {'full_attention': create_causal_mask(**args)}
    if 'sliding_attention' in config.layer_types:
        masks['sliding_attention'] = create_sliding_window_causal_mask(**args)
    if config.model_type == 'gemma3_text':
        rotary = {kind: base.rotary_emb(hidden, positions, kind) for kind in set(config.layer_types)}
    else:
        rotary = {kind: base.rotary_emb(hidden, positions) for kind in set(config.layer_types)}
    for i in range(cut, len(base.layers)):
        kind = config.layer_types[i]
        hidden = base.layers[i](hidden, attention_mask=masks[kind], position_ids=positions,
            position_embeddings=rotary[kind], past_key_values=None)
    return base.norm(hidden)


def cache_prefix(model, records, folder, cut):
    import torch
    from transformers.cache_utils import DynamicCache
    folder.mkdir(exist_ok=True)
    class Captured(Exception): pass
    holder = {}
    def hook(module, args, kwargs):
        holder['hidden'] = args[0].detach().clone()
        raise Captured()
    cache = {}; index = []
    tick = time.perf_counter()
    common = list(records[0]['input_ids'][:-1])
    for record in records[1:]:
        other = record['input_ids'][:-1]
        limit = min(len(common),len(other))
        mismatch = next((i for i in range(limit) if common[i]!=other[i]),limit)
        common = common[:mismatch]
    shared_cache = DynamicCache(config=model.config)
    handle = model.model.layers[cut].register_forward_pre_hook(hook,with_kwargs=True)
    try:
        with torch.no_grad():
            model.model(input_ids=torch.tensor([common]),use_cache=True,past_key_values=shared_cache)
    except Captured: pass
    finally: handle.remove()
    common_hidden = holder.pop('hidden')
    dump(folder.parent/'shared-prefix.json',dict(common_tokens=len(common),exact_KV_reuse=True))
    for i, record in enumerate(records):
        tensor = torch.tensor([record['input_ids'][:-1]])
        key = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
        path = folder / (key + '.pt')
        if key not in cache:
            if path.exists():
                hidden = torch.load(path,weights_only=True)
            else:
                handle = model.model.layers[cut].register_forward_pre_hook(hook, with_kwargs=True)
                try:
                    with torch.no_grad():
                        model.model(input_ids=tensor[:,len(common):], use_cache=True,
                            past_key_values=copy.deepcopy(shared_cache))
                except Captured: pass
                finally: handle.remove()
                hidden = torch.cat([common_hidden,holder.pop('hidden')],dim=1)
            if i == 0:
                with torch.no_grad():
                    direct = model.model(input_ids=tensor, use_cache=False).last_hidden_state
                    replay = cached_tail(model, hidden, cut)
                error = float((direct - replay).abs().max())
                if error > 0.0001: raise RuntimeError('Cached-tail parity failure: ' + str(error))
                dump(folder.parent / 'cache-parity.json', dict(max_hidden_error=error, tolerance=0.0001,
                    prefix_dtype='float32', tail_layers=len(model.model.layers)-cut))
            if not path.exists(): torch.save(hidden, path)
            cache[key] = path
        index.append(dict(id=record['id'], cache=cache[key].name))
        if (i+1) % 40 == 0 or i+1 == len(records):
            print(json.dumps(dict(phase='cache', completed=i+1, total=len(records), unique=len(cache), seconds=time.perf_counter()-tick)), flush=True)
    dump(folder.parent / 'cache-index.json', index)
    return [cache[hashlib.sha256(torch.tensor([r['input_ids'][:-1]]).numpy().tobytes()).hexdigest()] for r in records]


def token_loss(model, hidden, record, cut):
    import torch
    # Shift once: the final prompt state predicts the first completion token.
    states = cached_tail(model, hidden, cut)[:, record['prompt_tokens']-1:, :]
    logits = model.lm_head(states)
    if getattr(model.config, 'final_logit_softcapping', None) is not None:
        cap = model.config.final_logit_softcapping; logits = torch.tanh(logits/cap)*cap
    targets = torch.tensor(record['target_ids'])
    if logits.shape[1] != len(targets): raise RuntimeError('Shifted target mismatch')
    return torch.nn.functional.cross_entropy(logits[0], targets)


class TailKV:
    """Differentiable shared-prefix KV: no detachment or stale trainable state."""
    def __init__(self, values=None): self.values={} if values is None else dict(values)
    def update(self, keys, values, layer_idx, *args, **kwargs):
        import torch
        if layer_idx in self.values:
            old_k,old_v=self.values[layer_idx]
            keys=torch.cat([old_k.expand(keys.shape[0],-1,-1,-1),keys],dim=-2)
            values=torch.cat([old_v.expand(values.shape[0],-1,-1,-1),values],dim=-2)
        self.values[layer_idx]=(keys,values)
        return keys,values


def tail_segment(model, hidden, cut, cache, offset):
    import torch
    base=model.model; config=model.config
    positions=torch.arange(offset,offset+hidden.shape[1]).unsqueeze(0)
    keys=torch.arange(offset+hidden.shape[1])
    allowed=keys[None,:]<=positions[0,:,None]
    masks={'full_attention':allowed[None,None,:,:]}
    if 'sliding_attention' in config.layer_types:
        masks['sliding_attention']=(allowed & (keys[None,:]>positions[0,:,None]-config.sliding_window))[None,None,:,:]
    if config.model_type=='gemma3_text':
        rotary={kind:base.rotary_emb(hidden,positions,kind) for kind in set(config.layer_types)}
    else: rotary={kind:base.rotary_emb(hidden,positions) for kind in set(config.layer_types)}
    for i in range(cut,len(base.layers)):
        kind=config.layer_types[i]
        hidden=base.layers[i](hidden,attention_mask=masks[kind],position_ids=positions,
            position_embeddings=rotary[kind],past_key_values=cache)
    return base.norm(hidden)


def shared_batch_loss(model, hidden_rows, records, cut, shared):
    import torch
    cache=TailKV()
    tail_segment(model,hidden_rows[0][:,:shared,:],cut,cache,0)
    maximum=max(h.shape[1]-shared for h in hidden_rows)
    suffix=torch.cat([torch.nn.functional.pad(h[:,shared:,:],(0,0,0,maximum-(h.shape[1]-shared))) for h in hidden_rows])
    states=tail_segment(model,suffix,cut,TailKV(cache.values),shared)
    losses=[]
    for i,record in enumerate(records):
        start=record['prompt_tokens']-1-shared
        logits=model.lm_head(states[i,start:start+len(record['target_ids']),:])
        if getattr(model.config,'final_logit_softcapping',None) is not None:
            cap=model.config.final_logit_softcapping; logits=torch.tanh(logits/cap)*cap
        losses.append(torch.nn.functional.cross_entropy(logits,torch.tensor(record['target_ids'])))
    return torch.stack(losses).mean()


def train(work, name, threads):
    import torch
    out = work / name; out.mkdir(exist_ok=True)
    if (out/'training-history.json').exists() or (out/'checkpoint.pt').exists():
        raise RuntimeError('Training already started; use a new campaign rather than overwrite updates')
    policy = json.loads((work / 'protocol.json').read_text())
    tok, model = load(name, threads)
    cut = len(model.model.layers)-policy['last_trainable_blocks']
    for block in model.model.layers[cut:]: block.requires_grad_(True)
    train_rows = read_rows(work / 'train.jsonl'); tune_rows = read_rows(work / 'tuning.jsonl')
    train_jobs = [serialize(tok, name, c, True) for c in train_rows]
    tune_jobs = [serialize(tok, name, c, True) for c in tune_rows]
    write_rows(out / 'training-jobs.jsonl', train_jobs); write_rows(out / 'tuning-jobs.jsonl', tune_jobs)
    dump(out / 'model.json', dict(model_path=str(MODELS[name]),
        files_sha256={p.name: sha(p) for p in MODELS[name].glob('*') if p.is_file() and p.suffix in ('.json', '.safetensors', '.jinja')},
        total_parameters=sum(p.numel() for p in model.parameters()),
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
        cut=cut, blocks=2, precision='float32', vocabulary_mask=False,
        max_train_tokens=max(len(j['input_ids']) for j in train_jobs),
        max_tuning_tokens=max(len(j['input_ids']) for j in tune_jobs)))
    paths = cache_prefix(model, train_jobs + tune_jobs, out / 'prefix-cache', cut)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=policy['learning_rate'], weight_decay=0.01)
    best = float('inf'); history = []; start = time.perf_counter()
    shared=json.loads((out/'shared-prefix.json').read_text())['common_tokens']
    for epoch in range(1, policy['epochs']+1):
        model.eval()  # Both models have no attention dropout; deterministic frozen-prefix equivalence.
        order = list(range(len(train_jobs))); random.Random(epoch).shuffle(order)
        total = 0.; optimizer.zero_grad(set_to_none=True)
        for batch_start in range(0,len(order),policy['accumulation']):
            selected_indices=order[batch_start:batch_start+policy['accumulation']]
            step=batch_start+len(selected_indices)
            hidden_rows=[torch.load(paths[i],weights_only=True) for i in selected_indices]
            loss=shared_batch_loss(model,hidden_rows,[train_jobs[i] for i in selected_indices],cut,shared)
            if not torch.isfinite(loss): raise RuntimeError('Non-finite loss')
            total += float(loss.detach())*len(selected_indices); loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0); optimizer.step(); optimizer.zero_grad(set_to_none=True)
            if step % 40 == 0:
                print(json.dumps(dict(phase='train', model=name, epoch=epoch, step=step, loss=total/step,
                    elapsed=time.perf_counter()-start)), flush=True)
        tune_sum = 0; tokens = 0
        with torch.no_grad():
            for j, job in enumerate(tune_jobs):
                loss = token_loss(model, torch.load(paths[len(train_jobs)+j], weights_only=True), job, cut)
                count = len(job['target_ids']); tune_sum += float(loss)*count; tokens += count
        item = dict(epoch=epoch, training_mean_record_loss=total/len(order), tuning_token_loss=tune_sum/tokens,
            elapsed=time.perf_counter()-start)
        history.append(item); dump(out / 'training-history.json', history)
        if item['tuning_token_loss'] < best:
            best = item['tuning_token_loss']
            torch.save(dict(layers={str(i): model.model.layers[i].state_dict() for i in range(cut,len(model.model.layers))},
                epoch=epoch, cut=cut, tuning_loss=best), out / 'checkpoint.pt')
            dump(out / 'selection.json', dict(epoch=epoch, tuning_loss=best, criterion=policy['checkpoint_selection'],
                audit_seen=False, fresh_seen=False, checkpoint_sha256=sha(out / 'checkpoint.pt')))
        print(json.dumps(dict(phase='epoch', model=name, **item)), flush=True)
    dump(out / 'training-complete.json', dict(epochs=len(history), model_trained=True, weight_updates_split='train only',
        selection=json.loads((out / 'selection.json').read_text()), seconds=time.perf_counter()-start))


def generate(work, name, threads, pretrained=False):
    import torch
    if not pretrained:
        completed=json.loads((work/name/'training-complete.json').read_text())
        expected=json.loads((work/'protocol.json').read_text())['epochs']
        if completed['epochs']!=expected or not completed['model_trained']:
            raise RuntimeError('Finish training and lock checkpoint selection before evaluation')
    tok, model = load(name, threads)
    out = work / (name + ('-pretrained' if pretrained else ''))
    if pretrained: out.mkdir(exist_ok=True)
    else:
        saved = torch.load(out / 'checkpoint.pt', weights_only=True)
        for i, state in saved['layers'].items(): model.model.layers[int(i)].load_state_dict(state, strict=True)
    # Float32 capability reference: dynamic activation-int8 failed tuning numerical qualification.
    model.eval(); tok.padding_side = 'left'
    if tok.pad_token_id is None: tok.pad_token_id = tok.eos_token_id
    eos = [151645] if name == 'qwen' else [1, 50, tok.convert_tokens_to_ids('<end_of_turn>'),
        tok.convert_tokens_to_ids('<start_function_response>')]
    eos = sorted(set(eos)); batch_size = 4
    splits = ('fresh',) if pretrained else ('audit', 'fresh','conditional')
    for split in splits:
        cases = read_rows(work / (split+'.jsonl')); records = []
        if pretrained:
            chosen=set(json.loads((work/'pretrained-reference-ids.json').read_text())['ids'])
            cases=[c for c in cases if c['id'] in chosen]
        output = out / (split+'-predictions.jsonl')
        if output.exists(): raise FileExistsError(output)
        for start in range(0, len(cases), batch_size):
            batch = cases[start:start+batch_size]
            jobs = [serialize(tok, name, dict(public_input(c),id=c['id'])) for c in batch]
            maximum = max(len(j['prompt_ids']) for j in jobs)
            inputs = torch.tensor([[tok.pad_token_id]*(maximum-len(j['prompt_ids']))+j['prompt_ids'] for j in jobs])
            mask = torch.tensor([[0]*(maximum-len(j['prompt_ids']))+[1]*len(j['prompt_ids']) for j in jobs])
            tick = time.perf_counter()
            with torch.inference_mode():
                outputs = model.generate(input_ids=inputs, attention_mask=mask, max_new_tokens=256,
                    do_sample=False, use_cache=True, eos_token_id=eos, pad_token_id=tok.pad_token_id,
                    repetition_penalty=1.0)
            seconds = time.perf_counter()-tick
            for i, case in enumerate(batch):
                ids = outputs[i,maximum:].tolist()
                stop = next((p for p,v in enumerate(ids) if v in eos), len(ids))
                generated = ids[:stop]; raw = tok.decode(generated, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                error = None
                try: payload = unwrap(name, raw)
                except ValueError as exc: payload = ''; error = str(exc)
                row = verdict(case, payload, seconds/len(batch), native_output=raw, native_parse_error=error,
                    actual_prompt_ids=jobs[i]['prompt_ids'], generated_ids=generated,
                    stopped_on_eos=stop<len(ids), total_reserved=len(jobs[i]['prompt_ids'])+256,
                    checkpoint='pretrained' if pretrained else sha(out/'checkpoint.pt'))
                with output.open('a', encoding='utf-8') as stream: stream.write(json.dumps(row)+'\n')
                records.append(row)
            dump(out / (split+'-status.json'), dict(completed=len(records), total=len(cases)))
            print(json.dumps(dict(phase='evaluate', model=name, pretrained=pretrained, split=split,
                completed=len(records), correct=sum(r['correct'] for r in records))), flush=True)
        dump(out / (split+'-summary.json'), dict(summary(records), inference_precision='float32 CPU',
            weights_finetuned=not pretrained, format='native wrapper' if name=='functiongemma' else 'maintenance JSON',
            grammar=False, repair=False))


def controls(work, threads, split='fresh'):
    import torch
    from transformers import AutoModel, AutoTokenizer
    from torch import nn
    torch.set_num_threads(threads)
    cases = read_rows(work / (split+'.jsonl'))
    for name in ('rules','tfidf','minilm'):
        out = work/name; out.mkdir(exist_ok=True)
        if (out/(split+'-predictions.jsonl')).exists(): raise FileExistsError('Control split already evaluated')
        if name == 'tfidf':
            # Trusted local checkpoint from the sealed parent run.
            vectorizer, heads = pickle.loads((PARENT/'tfidf/model.pkl').read_bytes())
        if name == 'minilm':
            saved = torch.load(PARENT/'minilm/checkpoint.pt', weights_only=True)
            base = AutoModel.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'), local_files_only=True)
            base.load_state_dict(saved['base']); base.eval()
            tok = AutoTokenizer.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'), local_files_only=True)
            classes = saved['classes']; names = list(classes)
            heads = nn.ModuleList([nn.Linear(base.config.hidden_size,len(classes[k])) for k in names])
            heads.load_state_dict(saved['heads']); heads.eval()
        records = []
        for case in cases:
            tick = time.perf_counter(); fields = None
            try:
                if name == 'rules': raw = encode(rules(public_input(case)))
                elif name == 'tfidf':
                    x = vectorizer.transform([features(public_input(case))])
                    fields = {k:h if type(h) is str else str(h.predict(x)[0]) for k,h in heads.items()}
                    raw = encode(unflatten(fields, case['catalog']))
                else:
                    b = tok(features(public_input(case)), return_tensors='pt', truncation=False)
                    with torch.inference_mode():
                        hidden = base(**b).last_hidden_state; mask = b['attention_mask'].unsqueeze(-1)
                        pooled = (hidden*mask).sum(1)/mask.sum(1)
                        fields = {k:classes[k][int(h(pooled)[0].argmax())] for k,h in zip(names,heads)}
                    raw = encode(unflatten(fields,case['catalog']))
            except (ValueError, TypeError, KeyError, IndexError): raw = json.dumps(fields)
            records.append(verdict(case,raw,time.perf_counter()-tick))
        write_rows(out/(split+'-predictions.jsonl'),records); dump(out/(split+'-summary.json'),summary(records))
        print(json.dumps(dict(model=name, **summary(records))),flush=True)


def report(work):
    check_seal(PARENT)
    results = {}
    for name in ('rules','tfidf','minilm','qwen','qwen-pretrained','functiongemma','functiongemma-pretrained'):
        results[name] = {}
        for split in ('audit','fresh','conditional'):
            path = work/name/(split+'-predictions.jsonl')
            if not path.exists() and split == 'audit' and name in ('rules','tfidf','minilm'):
                path = PARENT/name/'audit-predictions.jsonl'
            if not path.exists(): continue
            cases = {c['id']:c for c in read_rows(work/(split+'.jsonl'))}
            if name.endswith('-pretrained'):
                chosen=set(json.loads((work/'pretrained-reference-ids.json').read_text())['ids'])
                cases={k:v for k,v in cases.items() if k in chosen}
            rows = read_rows(path)
            if [r['id'] for r in rows] != list(cases): raise RuntimeError('Incomplete evaluation')
            for row in rows:
                replay = verdict(cases[row['id']],row['raw_output'],0)
                if any(replay[k] != row[k] for k in ('correct','valid','accepted')):
                    raise RuntimeError('Rescore mismatch')
                if name.startswith('functiongemma') and row.get('native_parse_error') is None:
                    if unwrap('functiongemma',row['native_output']) != row['raw_output']:
                        raise RuntimeError('Native adapter mismatch')
            result = summary(rows)
            if name in ('qwen','qwen-pretrained','functiongemma','functiongemma-pretrained'):
                result['token_audit']=dict(max_input_tokens=max(len(r['actual_prompt_ids']) for r in rows),
                    max_reserved_total=max(r['total_reserved'] for r in rows),
                    max_generated_tokens=max(len(r['generated_ids']) for r in rows),
                    stopped_on_eos=sum(r['stopped_on_eos'] for r in rows))
            conditional = [r for r in rows if r['stratum']=='conditional']
            result['conditional_wrong_accepted'] = sum(r['accepted'] and not r['correct'] for r in conditional)
            result['predicate_fields'] = {}
            for field in ('source','op','rhs'):
                result['predicate_fields'][field] = sum((r.get('ast',{}).get('predicate') or {}).get(field)==
                    cases[r['id']]['gold']['predicate'][field] for r in conditional)
            result['conditional_breakdown'] = {}
            for field in ('op','rhs'):
                grouped = {}
                for row in conditional:
                    key = str(cases[row['id']]['gold']['predicate'][field])
                    bucket = grouped.setdefault(key,dict(count=0,correct=0))
                    bucket['count'] += 1; bucket['correct'] += int(row['correct'])
                result['conditional_breakdown'][field] = grouped
            result['operator_confusion'] = {}
            result['conditional_structure_fields'] = dict(guards=0,evidence=0,tools=0,assets=0)
            for row in conditional:
                gold=cases[row['id']]['gold']; ast=row.get('ast') or {}
                pair=gold['predicate']['op']+' -> '+str((ast.get('predicate') or {}).get('op','missing'))
                result['operator_confusion'][pair]=result['operator_confusion'].get(pair,0)+1
                actual=ast.get('steps',[]); desired=gold['steps']
                for label,field in (('guards','guard'),('evidence','evidence'),('tools','tool'),('assets','asset')):
                    def value(node):
                        return node.get(field)
                    if len(actual)==len(desired) and [value(n) for n in actual]==[value(n) for n in desired]:
                        result['conditional_structure_fields'][label]+=1
            results[name][split] = result
    dump(work/'comparison.json',dict(results=results,development_only=True,energy_measured=False,board_access=False,
        parent=check_seal(PARENT)))
    chosen=set(json.loads((work/'pretrained-reference-ids.json').read_text())['ids'])
    matched={}
    for name in ('qwen','functiongemma'):
        matched[name]={variant:summary([r for r in read_rows(work/variant/'fresh-predictions.jsonl') if r['id'] in chosen])
            for variant in (name+'-pretrained',name)}
    dump(work/'matched-reference-comparison.json',matched)
    lines = ['# Maintenance task fine-tuning comparison','',
        'Fresh data are new seeds/assets from the same authored templates. The older audit is a regression set already inspected before training.',
        'Generator checkpoints are selected only by tuning completion loss. Both generators train their last two decoder blocks; all embeddings, earlier blocks and vocabulary projections remain frozen.',
        'Inference uses the qualified float32 CPU reference, full vocabulary and greedy decoding without grammar or repair. Dynamic activation-int8 failed tuning numerical qualification and is archived separately. Previous Qwen few-shot Q8 scores use a different backend/precision.', '',
        'Pretrained references use a predeclared balanced 24-request subset; adapted models use all120 fresh requests. The matched before/after subset scores are retained separately.', '',
        '| Model | Regression correct | Regression conditional | Fresh correct | Fresh conditional | Conditional stress | Fresh valid | Fresh wrong accepted |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, splits in results.items():
        a=splits.get('audit'); f=splits.get('fresh')
        lines.append('| '+name+' | '+' | '.join(str(v) for v in (
            f"{a['correct']}/{a['count']}" if a else '-',f"{a['strata']['conditional']['correct']}/20" if a else '-',
            f"{f['correct']}/{f['count']}" if f else '-',
            f"{f['strata']['conditional']['correct']}/{f['strata']['conditional']['count']}" if f else '-',
            f"{splits['conditional']['correct']}/64" if 'conditional' in splits else '-',
            f"{f['valid']}/{f['count']}" if f else '-',f['incorrect_accepted'] if f else '-'))+' |')
    lines += ['', '## Matched float32 reference subset', '',
        '| Model | Pretrained correct /24 | Fine-tuned correct /24 |',
        '|---|---:|---:|']
    for name, variants in matched.items():
        lines.append(f"| {name} | {variants[name+'-pretrained']['correct']} | {variants[name]['correct']} |")
    lines += ['', '## Interpretation', '',
        'Qwen leads the learned baselines on fresh requests from familiar templates. Neither generator exceeds TF-IDF on the crossed conditional stress set; authored rules remain perfect on these authored cases.',
        f"On conditional stress, Qwen emits {results['qwen']['conditional']['incorrect_accepted']} valid but incorrect plans and FunctionGemma emits {results['functiongemma']['conditional']['incorrect_accepted']}. Schema validity does not establish semantic reliability.",
        'This is a one-seed, final-two-block adaptation pilot with unequal trainable parameter budgets. It establishes neither a model-family optimum nor independent real-world generalization. No FPGA latency or energy has been measured.',
        'The next capability milestone needs independent operator requests, broader conditional training combinations and a stronger structured encoder. Changes informed by this stress set require a new held-out test.']
    (work/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    required = [('qwen', 'audit'),('qwen','fresh'),('qwen-pretrained','fresh'),
        ('qwen','conditional'),('functiongemma','audit'),('functiongemma','fresh'),
        ('functiongemma','conditional'),('functiongemma-pretrained','fresh')]
    if not all(split in results[name] for name,split in required): raise RuntimeError('Required model results missing')
    files = {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*')
        if p.is_file() and 'prefix-cache' not in p.parts and p.name!='final-seal.json'}
    dump(work/'final-seal.json',dict(files_sha256=files,excluded='recomputable frozen-prefix caches only',parent_verified=True))
    print('\n'.join(lines),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=['prepare','prepare-conditional','prepare-references','train','evaluate','controls','controls-conditional','report'])
    ap.add_argument('--work',type=Path,default=DEFAULT)
    ap.add_argument('--model',choices=list(MODELS),default='qwen')
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--pretrained',action='store_true')
    a=ap.parse_args()
    if a.phase!='prepare':
        inv=a.work/'invocations'; inv.mkdir(exist_ok=True)
        stem=f'{a.phase}-{a.model}-{time.time_ns()}'
        shutil.copyfile(__file__,inv/(stem+'.py'))
        dump(inv/(stem+'.json'),dict(arguments=vars(a)|{'work':str(a.work)},source_sha256=sha(Path(__file__)),
            protocol_sha256=sha(a.work/'protocol.json')))
    if a.phase=='prepare': prepare(a.work)
    elif a.phase=='prepare-conditional': prepare_conditional(a.work)
    elif a.phase=='prepare-references': prepare_references(a.work)
    elif a.phase=='train': train(a.work,a.model,a.threads)
    elif a.phase=='evaluate': generate(a.work,a.model,a.threads,a.pretrained)
    elif a.phase=='controls': controls(a.work,a.threads)
    elif a.phase=='controls-conditional': controls(a.work,a.threads,'conditional')
    else: report(a.work)


if __name__=='__main__': main()
