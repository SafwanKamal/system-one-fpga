"""Fit and compare a maintenance-only action head over frozen Qwen3 Q4 states."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import time

import capability_comparison_20261102 as base
from sysone.v2.maintenance import schema
from sysone.v2.maintenance.dataset import public_input
from sysone.v2.maintenance.simulator import execute, world

ROOT = base.ROOT
WORK = ROOT / 'build/v2/interactive-maintenance-20261104'
PARENT = ROOT / 'build/v2/model-capability-20261102-r3'
TRAIN = ROOT / 'build/v2/maintenance-sft-v3/train.jsonl'
SERVER = ROOT / 'build/v2/model-capability-runtime-vulkan-b11540/bin/llama-server.exe'
MODEL = next(item for item in base.rows_json(PARENT/'models.json') if item['key']=='qwen17-q4')
base.SERVER, base.GPU_LAYERS, base.PORT = SERVER, 99, 18204
READS = schema.TOOLS[:5] + ('lookup_procedure',)
ACTIONS = ('draft_report', 'request_inspection')
ARG_FIELDS = {
    'read_metric': ('metric',), 'read_history': ('metric', 'count'),
    'read_metadata': ('field',), 'lookup_procedure': ('topic',),
    'draft_report': ('priority', 'evidence'), 'request_inspection': ('priority', 'evidence'),
}
FIELDS = {
    'tool': (*schema.TOOLS, 'done', 'clarify', 'reject'),
    'asset': tuple(range(12)), 'metric': schema.METRICS, 'count': tuple(range(1,6)),
    'field': ('manufacturer', 'inspection_date'), 'topic': ('inspection', 'lubrication'),
    'priority': ('normal', 'high'), 'evidence': tuple(range(1,8)),
    'op': (None, *schema.OPS), 'source': (0,1,2), 'rhs': ('limit', 0, 1, 2, 3),
    'reason': tuple(reason for reasons in schema.REASONS.values() for reason in reasons),
}
SYSTEM = """Choose the next maintenance step only. Output one JSON array.
Use ["done"] to finish after all requested steps. Before any step you may return ["clarify",reason] or ["reject",reason].
For a step return [tool,asset,args,condition]. condition is null or [earlier metric step index,"gt|ge|lt|le",number or "limit"]. Repeat the condition on each guarded step even when the current sample fails it. Step indices start at zero.
Reads: read_metric(metric), read_history(metric,count), list_alarms(), read_status(), read_metadata(field), lookup_procedure(topic). Metrics: temperature, vibration, current. Metadata: manufacturer, inspection_date. Topics: inspection, lubrication.
Actions: draft_report(priority,evidence), request_inspection(priority,evidence). priority is normal or high. evidence lists previous read step indices.
Clarify reasons: ambiguous_asset, missing_reference, missing_asset, contradiction. Reject reasons: unsupported_operation, unknown_asset, unsupported_unit, unsupported_value, plan_capacity.
Use the request, context, catalog, and prior read receipts. Stop when complete. Propose at most three steps on one asset. Return the array only."""
FORMAT_EXAMPLES = """
These examples show valid JSON shapes. Use the input's actual asset and values.
["read_metric","P21",{"metric":"temperature"},null]
["read_history","P21",{"metric":"temperature","count":3},[0,"ge",70]]
["request_inspection","P21",{"priority":"high","evidence":[0,1]},[0,"ge",70]]
["clarify","ambiguous_asset"]
["reject","unknown_asset"]
["done"]"""
COMPACT = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def state(case, steps, predicate):
    data = public_input(case)
    previous = data['context'].get('previous_request', '')
    texts = data['request'] + '\n' + previous
    named = re.findall(r'\b[PMF][1-9][0-9]?\b', texts)
    data['catalog'] = list(dict.fromkeys([a for a in named if a in data['catalog']] + sorted(data['catalog'])))
    numbers = list(dict.fromkeys(int(n) for n in re.findall(r'(?<![\w.])-?\d+(?![\w.])', data['request'])))[:4]
    reads = [step for step in steps if step['tool'] in READS and not step['guard']]
    receipts = execute(schema.plan(*reads), world(data['catalog']))['trace'] if reads else []
    data.update(steps=steps, predicate=predicate, read_receipts=receipts, number_literals=numbers)
    return data


def wire(step, predicate):
    args = {key: step[key] for key in ARG_FIELDS.get(step['tool'], ())}
    guard = [predicate[key] for key in ('source','op','rhs')] if step['guard'] else None
    return [step['tool'], step['asset'], args, guard]


def labels(action, data):
    tool = action[0]
    fields = {'tool': tool}
    if tool in ('clarify','reject'):
        fields['reason'] = action[1]
    if tool in schema.TOOLS:
        _, asset, args, guard = action
        fields.update(args, asset=data['catalog'].index(asset), op=guard[1] if guard else None)
        if 'evidence' in fields:
            fields['evidence'] = sum(1 << index for index in fields['evidence'])
        if guard:
            fields.update(source=guard[0], rhs='limit' if guard[2]=='limit' else data['number_literals'].index(guard[2]))
    return [options.index(fields[key]) if key in fields else -100 for key, options in FIELDS.items()]


def prompt_ids(data, examples=False):
    instructions = SYSTEM + FORMAT_EXAMPLES if examples else SYSTEM
    messages = [{'role':'system','content':instructions}, {'role':'user','content':COMPACT(data)}]
    prompt = base.post('/apply-template', dict(messages=messages,add_generation_prompt=True,
        chat_template_kwargs={'enable_thinking':False},enable_thinking=False))['prompt']
    ids = base.post('/tokenize', dict(content=prompt,add_special=True,parse_special=True))['tokens']
    if len(ids)+96 > 2048:
        raise ValueError('Prompt exceeds context allowance')
    return ids


def features(ids):
    result = base.post('/embedding', dict(content=ids,embd_normalize=-1))
    vector = result[0]['embedding']
    if len(vector)==1 and isinstance(vector[0],list):
        vector = vector[0]
    if len(vector)!=2048 or not isinstance(vector[0],(int,float)):
        raise RuntimeError('Unexpected pooled Qwen hidden state shape')
    return vector


def train_jobs():
    per_stratum = {}
    jobs = []
    for case in base.rows(TRAIN):
        stratum = case['stratum']
        if per_stratum.get(stratum,0)>=64:
            continue
        per_stratum[stratum] = per_stratum.get(stratum,0)+1
        gold = case['gold']
        steps = gold.get('steps', [])
        predicate = gold.get('predicate')
        actions = [wire(step,predicate) for step in steps]
        if not steps:
            actions = [[gold['outcome'],gold['reason']]]
        elif len(steps)<3:
            actions.append(['done'])
        for index, action in enumerate(actions):
            prefix = steps[:index]
            active_predicate = predicate if any(step['guard'] for step in prefix) else None
            data = state(case, prefix, active_predicate)
            jobs.append(dict(id=case['id']+'/'+str(index), state=data, target=labels(action,data)))
    return jobs


def make_head():
    import torch
    return torch.nn.Sequential(torch.nn.LayerNorm(2048),torch.nn.Linear(2048,128),
        torch.nn.GELU(),torch.nn.Linear(128,sum(map(len,FIELDS.values()))))


def fit(jobs, vectors, centered=False):
    import torch
    import torch.nn.functional as functional
    torch.manual_seed(20261104)
    torch.set_num_threads(4)
    x = torch.tensor(vectors)
    y = torch.tensor([job['target'] for job in jobs])
    mean = x.mean(0) if centered else torch.zeros(x.shape[1])
    x = x - mean
    model = make_head()
    optimizer = torch.optim.AdamW(model.parameters(),lr=0.001,weight_decay=0.02)
    for epoch in range(48 if centered else 24):
        for batch in torch.randperm(len(jobs)).split(64):
            columns = model(x[batch]).split(tuple(map(len,FIELDS.values())),dim=1)
            loss = sum(functional.cross_entropy(column[active], y[batch,i][active])
                       for i,column in enumerate(columns) if (active := y[batch,i]!=-100).any())
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        print(f'epoch {epoch+1} loss {loss.item():.4f}',flush=True)
    if centered:
        torch.save(dict(head=model.state_dict(),mean=mean),WORK/'action-head-centered.pt')
    else:
        torch.save(model.state_dict(),WORK/'action-head.pt')
    return model.eval(),mean


def adapted_action(adapter, vector, data):
    import torch
    model, mean = adapter
    with torch.inference_mode():
        columns = model(torch.tensor(vector)-mean).split(tuple(map(len,FIELDS.values())))
    predictions = {key:options[int(column.argmax())]
                   for (key,options),column in zip(FIELDS.items(),columns)}
    tool = predictions['tool']
    if tool=='done':
        return [tool]
    if tool in ('clarify','reject'):
        return [tool,predictions['reason']]
    asset = data['catalog'][predictions['asset']]
    args = {key:predictions[key] for key in ARG_FIELDS.get(tool,())}
    if 'evidence' in args:
        args['evidence'] = [i for i in range(3) if args['evidence'] & (1 << i)]
    guard = None
    if predictions['op'] is not None:
        rhs = predictions['rhs']
        if rhs!='limit':
            rhs = data['number_literals'][rhs]
        guard = [predictions['source'],predictions['op'],rhs]
    return [tool,asset,args,guard]


def one_step(mode, data, model):
    ids = prompt_ids(data,examples=mode=='examples')
    if mode=='adapted':
        return dict(action=adapted_action(model,features(ids),data),prompt_ids=ids,raw=None,
                    generated_tokens=0,error=None)
    answer = base.post('/completion',dict(prompt=ids,n_predict=96,temperature=0,seed=20261104,
        repeat_penalty=1.0,samplers=['temperature'],cache_prompt=False,return_tokens=True))
    raw = base.decode_generated(answer)
    turn = dict(action=None,prompt_ids=ids,raw=raw,generated_tokens=answer.get('tokens_predicted'),
                stop_type=answer.get('stop_type'),error=None)
    try:
        if answer.get('stop_type')=='limit' or answer.get('truncated'):
            raise ValueError('Next-step generation exhausted its token budget')
        turn['action'] = json.loads(base.strip_format(raw),object_pairs_hook=schema._unique)
    except ValueError as exc:
        turn['error'] = str(exc)
    return turn


def propose(case, mode, model=None):
    start = time.perf_counter()
    steps, turns, predicate, ast = [], [], None, None
    error = None
    try:
        for _ in range(3):
            data = state(case,steps,predicate)
            turn = one_step(mode,data,model)
            turns.append(turn)
            if turn['error']:
                raise ValueError(turn['error'])
            action = turn['action']
            if type(action) is not list or not action:
                raise ValueError('Expected nonempty action array')
            if action==['done']:
                break
            if action[0] in ('clarify','reject'):
                if steps or len(action)!=2:
                    raise ValueError('Terminal decision after partial plan or with extra fields')
                ast = schema.terminal(*action)
                break
            if len(action)!=4 or type(action[2]) is not dict or set(action[2]) & {'tool','asset','guard'}:
                raise ValueError('Malformed step')
            tool, asset, args, guard = action
            if guard is not None:
                if type(guard) is not list or len(guard)!=3:
                    raise ValueError('Malformed guard')
                proposed = dict(zip(('source','op','rhs'),guard))
                if predicate is not None and predicate!=proposed:
                    raise ValueError('Inconsistent guard across steps')
                predicate = proposed
            steps.append(dict(tool=tool,asset=asset,guard=guard is not None,**args))
            schema.validate(schema.plan(*steps,predicate=predicate),case['catalog'])
        ast = schema.validate(ast if ast is not None else schema.plan(*steps,predicate=predicate),case['catalog'])
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        error = str(exc)
    return dict(valid=error is None,predicted=ast,turns=turns,error=error,seconds=time.perf_counter()-start)


def plan_case(case, mode, model=None):
    result = propose(case,mode,model)
    score = (base.maintenance_score(case,result['predicted']) if result['valid'] else
             dict(correct=False,exact=False,behavioral_match=False,accepted=False))
    return dict(id=case['id'],subset=case['subset'],stratum=case['stratum'],**result,**score)


def load_head(centered=False):
    import torch
    torch.set_num_threads(1)
    head = make_head().eval()
    if centered:
        checkpoint = torch.load(WORK/'action-head-centered.pt',weights_only=True)
        head.load_state_dict(checkpoint['head'])
        return head,checkpoint['mean']
    head.load_state_dict(torch.load(WORK/'action-head.pt',weights_only=True))
    return head,torch.zeros(2048)


def embedding_mode():
    os.environ['LLAMA_ARG_EMBEDDINGS'] = '1'
    os.environ['LLAMA_ARG_POOLING'] = 'last'


def read_request(path):
    data = base.rows_json(path)
    if type(data) is not dict or set(data)-{'request','catalog','context'}:
        raise ValueError('Expected request, catalog and optional context')
    request = data.get('request')
    catalog = data.get('catalog')
    context = data.get('context',{})
    if type(request) is not str or not request.strip():
        raise ValueError('Expected a nonempty request')
    if type(catalog) is not list or not 1<=len(catalog)<=12 or any(
        type(asset) is not str or re.fullmatch(r'[PMF][1-9][0-9]?',asset) is None for asset in catalog
    ) or len(set(catalog))!=len(catalog):
        raise ValueError('Expected one to twelve unique maintenance asset IDs')
    if type(context) is not dict or not isinstance(context.get('previous_request',''),str):
        raise ValueError('Expected a context object with optional previous_request text')
    return dict(request=request,catalog=catalog,context=context)


def run_rows(path, cases, fn):
    existing = base.rows(path) if path.exists() else []
    done = {row['id'] for row in existing}
    pending = [case for case in cases if case['id'] not in done]
    with ThreadPoolExecutor(max_workers=4) as pool, path.open('a',encoding='utf-8') as stream:
        for offset in range(0,len(pending),4):
            chunk = list(pool.map(fn,pending[offset:offset+4]))
            for row in chunk:
                stream.write(COMPACT(row)+'\n')
            stream.flush()
            count = len(existing)+offset+len(chunk)
            if count%40==0 or count==len(cases):
                print(path.name,count,'/',len(cases),flush=True)
    return base.rows(path)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('stage',choices=['adapted','centered','generation','examples','plan'])
    cli.add_argument('--request-file',type=Path)
    args = cli.parse_args()
    stage = args.stage
    if (stage=='plan') != (args.request_file is not None):
        cli.error('plan requires --request-file and the benchmark stages take no request file')
    WORK.mkdir(parents=True,exist_ok=True)
    protocol = WORK/'protocol.json'
    if not protocol.exists():
        base.dump(protocol,dict(model=MODEL,model_sha256=base.digest(Path(MODEL['path'])),
            train_sha256=base.digest(TRAIN),evaluation_sha256=base.digest(PARENT/'evaluation.jsonl'),
            train_selection='first 64 records per stratum from existing train split',seed=20261104,
            head='frozen last pooled Q4 hidden state -> layer norm -> 128 GELU -> categorical fields',
            epochs=24,evaluation='all 184 maintenance and 212 general records from prior campaign',
            max_proposed_steps=3,source_sha256=base.digest(Path(__file__))))
    config = base.rows_json(protocol)
    if config['model_sha256']!=MODEL['sha256'] or base.digest(Path(MODEL['path']))!=MODEL['sha256']:
        raise RuntimeError('Q4 checkpoint integrity failure')
    if base.digest(TRAIN)!=config['train_sha256'] or base.digest(PARENT/'evaluation.jsonl')!=config['evaluation_sha256']:
        raise RuntimeError('Frozen data changed')
    if stage=='plan':
        try:
            request = read_request(args.request_file)
        except (OSError, ValueError) as exc:
            cli.error(str(exc))
        if not (WORK/'action-head-centered.pt').is_file():
            cli.error('Run the adapted and centered stages to fit the maintenance action head first')
        head = load_head(centered=True)
        embedding_mode()
        with base.Server(MODEL,WORK/'demo-server'):
            result = propose(request,'adapted',head)
        print(json.dumps(dict(proposal=result['predicted'],
            turns=[turn['action'] for turn in result['turns']],error=result['error']),indent=2))
        return
    cases = base.rows(PARENT/'evaluation.jsonl')
    maintenance = [case for case in cases if case['domain']=='maintenance']
    if stage in ('adapted','centered'):
        centered = stage=='centered'
        jobs = train_jobs()
        if {job['id'].rsplit('/',1)[0] for job in jobs} & {case['id'] for case in cases}:
            raise RuntimeError('Training and evaluation IDs intersect')
        feature_path = WORK/'train-features.jsonl'
        if centered:
            rows = base.rows(feature_path)
            if len(rows)!=len(jobs) or {row['id'] for row in rows}!={job['id'] for job in jobs}:
                raise RuntimeError('Run the adapted stage to finish the frozen feature cache first')
            if base.rows(WORK/'training-jobs.jsonl')!=jobs:
                raise RuntimeError('Feature cache training jobs differ from this source')
            (WORK/'centered-source.py').write_bytes(Path(__file__).read_bytes())
        embedding_mode()
        with base.Server(MODEL,WORK/('centered-server' if centered else 'embedding-server')):
            if not centered:
                rows = run_rows(feature_path,jobs,
                    lambda job: dict(id=job['id'],vector=features(prompt_ids(job['state']))))
                base.write_rows(WORK/'training-jobs.jsonl',jobs)
            vectors = {row['id']:row['vector'] for row in rows}
            checkpoint = WORK/('action-head-centered.pt' if centered else 'action-head.pt')
            if checkpoint.exists():
                head = load_head(centered=centered)
            else:
                head = fit(jobs,[vectors[job['id']] for job in jobs],centered=centered)
                import torch
                torch.set_num_threads(1)
            output = WORK/('centered-maintenance.jsonl' if centered else 'adapted-maintenance.jsonl')
            run_rows(output,maintenance,lambda case:plan_case(case,'adapted',head))
    elif stage=='examples':
        (WORK/'examples-source.py').write_bytes(Path(__file__).read_bytes())
        with base.Server(MODEL,WORK/'examples-server'):
            run_rows(WORK/'examples-maintenance.jsonl',maintenance,lambda case:plan_case(case,'examples'))
    else:
        base.WORK = WORK
        (WORK/'generation-source.py').write_bytes(Path(__file__).read_bytes())
        base.CHECKER = base.BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
        with base.Server(MODEL,WORK/'generation-server'):
            run_rows(WORK/'prompt-maintenance.jsonl',maintenance,lambda case:plan_case(case,'prompt'))
            for domain in ('general','episode'):
                base.run_batch([case for case in cases if case['domain']==domain],
                               'native',WORK/(domain+'.jsonl'))


if __name__=='__main__':
    main()
