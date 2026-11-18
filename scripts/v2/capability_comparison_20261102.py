"""Finite local quantized capability comparison. No FPGA or external tool execution."""
import argparse
import ast
import concurrent.futures
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import re
import random
import socket
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from sysone.v2.maintenance.dataset import public_input, score as maintenance_score
from sysone.v2.maintenance.revision2 import SYSTEM_V2
from sysone.v2.maintenance.schema import parse as maintenance_parse, encode as maintenance_encode
from sysone.v2.general_tool_eval import BFCLPythonChecker

ROOT = Path(__file__).resolve().parents[2]
EXECUTED_SOURCE = Path(__file__).read_bytes()
EXECUTED_SOURCE_SHA = hashlib.sha256(EXECUTED_SOURCE).hexdigest()
WORK = ROOT / 'build/v2/model-capability-20261102'
CACHE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SysoneModels/capability-20261102'
MODELS = [
    ('qwen06-q4', 'unsloth/Qwen3-0.6B-GGUF', 'Qwen3-0.6B-Q4_0.gguf'),
    ('qwen17-q4', 'unsloth/Qwen3-1.7B-GGUF', 'Qwen3-1.7B-Q4_0.gguf'),
    ('qwen4-q4', 'unsloth/Qwen3-4B-Instruct-2507-GGUF', 'Qwen3-4B-Instruct-2507-Q4_0.gguf'),
    ('qwen35-2-q4', 'unsloth/Qwen3.5-2B-GGUF', 'Qwen3.5-2B-Q4_0.gguf'),
    ('qwen35-4-q4', 'unsloth/Qwen3.5-4B-GGUF', 'Qwen3.5-4B-Q4_0.gguf'),
    ('xlam3-q4', 'Salesforce/xLAM-2-3b-fc-r-gguf', 'xLAM-2-3B-fc-r-Q4_0.gguf'),
    ('lfm12-q4', 'LiquidAI/LFM2.5-1.2B-Instruct-GGUF', 'LFM2.5-1.2B-Instruct-Q4_0.gguf'),
    ('smol3-q4', 'unsloth/SmolLM3-3B-GGUF', 'SmolLM3-3B-Q4_0.gguf'),
]
SERVER = ROOT / 'build/v2/generation/windows/llama-server.exe'
GPU_LAYERS = 0
PORT = 18192
ACTIVE_BOS = None
ACTIVE_CONTEXT = 2048
ACTIVE_ARCH = None
THINKING = False
OUTPUT_BUDGET = 256
PROFILE_CONTEXT = 2048
GENERAL_SYSTEM = ('Select only the supplied functions, with arguments grounded in the user request and prior results. '
                  'Never invent missing required values. If no function applies, return an empty list. '
                  'Do not call a dependent action before its required result is available. ')
DIRECT_SYSTEM = GENERAL_SYSTEM + ('Return only a JSON array of {"name":"function_name","arguments":{...}} objects. '
                                 'Return [] when no call is needed. No explanation or Markdown.')
SUBMIT = dict(type='function', function=dict(name='submit_maintenance_plan',
    description='Submit a complete maintenance outcome, including clarification or rejection.',
    parameters=dict(type='object', properties=dict(plan_json=dict(type='string',description='The exact maintenance outcome JSON array.')),required=['plan_json'])))

def write_rows(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in data), encoding='utf-8')

def freeze():
    if (WORK/'protocol.json').exists():
        raise FileExistsError('Protocol already frozen')
    rng = random.Random(20261102)
    fresh = rows(ROOT/'build/v2/maintenance-sft-v3/fresh.jsonl')
    stress = rows(ROOT/'build/v2/maintenance-sft-v3/conditional.jsonl')
    dev = rows(ROOT/'build/v2/maintenance-sft-v3/tuning.jsonl')
    maintenance = [dict(x, domain='maintenance', subset='fresh') for x in fresh]
    maintenance += [dict(x, domain='maintenance', subset='conditional') for x in stress]
    screen_ids = []
    for stratum in sorted({x['stratum'] for x in fresh}):
        group = [x for x in fresh if x['stratum'] == stratum]
        rng.shuffle(group); screen_ids += [x['id'] for x in group[:4]]
    # Cross all operators and both actions rather than take a contiguous prefix.
    for op in ['gt','ge','lt','le']:
        group = [x for x in stress if x['gold']['predicate']['op'] == op]
        rng.shuffle(group); screen_ids += [x['id'] for x in group[:6]]
    development = []
    for stratum in sorted({x['stratum'] for x in dev}):
        development += [dict(x, domain='maintenance', subset='development') for x in dev if x['stratum'] == stratum][:2]
    bfcl = rows(ROOT/'build/v2/general-tool-data-v1/external-evaluation.jsonl')
    answers = rows_json(ROOT/'build/v2/general-tool-data-v1/bfcl-answer-registry.json')
    general = []
    for category in sorted({x['category'] for x in bfcl}):
        group = [x for x in bfcl if x['category'] == category]
        rng.shuffle(group)
        for i, case in enumerate(group[:42]):
            x = dict(case, domain='general', gold=answers[case['id']], subset='bfcl')
            if i < 2: development.append(dict(x, subset='development'))
            else:
                general.append(x)
                if i < 12: screen_ids.append(x['id'])
    # Simulator-only conditional episodes: input/tool-response values are public,
    # no process, device, or real-world tool is invoked.
    episodes = []
    for i, (op, value) in enumerate((op,v) for op in ['gt','ge','lt','le'] for v in [69,70,71]):
        words = {'gt':'strictly above','ge':'at least','lt':'strictly below','le':'at most'}[op]
        asset = 'unit-'+str(87+i)
        tools = [dict(name='read_sensor',description='Read the current temperature in C.',parameters=dict(type='dict',properties=dict(asset=dict(type='string')),required=['asset'])),
                 dict(name='open_inspection',description='Open an inspection after reading the sensor if the requested condition holds.',parameters=dict(type='dict',properties=dict(asset=dict(type='string'),priority=dict(type='string',enum=['normal','high'])),required=['asset','priority']))]
        condition = {'gt':value>70,'ge':value>=70,'lt':value<70,'le':value<=70}[op]
        first = [dict(name='read_sensor',arguments=dict(asset=asset))]
        second = [dict(name='open_inspection',arguments=dict(asset=asset,priority='high'))] if condition else []
        episodes.append(dict(id=f'episode-{i:02d}',domain='episode',subset='two_turn',category='two_turn',tools=tools,
            query=f'Read the temperature of {asset}. Only if it is {words} 70 C, open a high-priority inspection. Otherwise do nothing else.',
            gold=first, followup=dict(tool_result=dict(asset=asset,temperature=value,unit='C'),gold=second),operator=op))
    write_rows(WORK/'development.jsonl', development)
    write_rows(WORK/'evaluation.jsonl', maintenance+general+episodes)
    dump(WORK/'screen-ids.json', screen_ids+[x['id'] for x in episodes if int(x['id'].split('-')[1])%2 == 0])
    # Freeze existing scorer sources by copying them; no historical source edits.
    for p in (ROOT/'src/sysone/v2/maintenance').glob('*.py'):
        target=WORK/'sources'/p.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    for p in [Path(__file__), ROOT/'src/sysone/v2/general_tool_eval.py']:
        target=WORK/'sources'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    protocol = dict(research_date='2026-11-02', candidates=rows_json(WORK/'models.json'),
        selection='Two finalists: highest balanced screen score and highest remaining nonhybrid Qwen3/Qwen2-family score. Balanced=mean(maintenance fresh accuracy, conditional accuracy, equal-category BFCL accuracy, complete two-turn episode accuracy). All weights 1/4.',
        routes='Direct shared JSON versus native tool template selected separately per domain/model on development only; ties prefer direct. Maintenance native uses submit_maintenance_plan(plan_json:string). Episodes use selected general route.',
        primary_context=2048, output_tokens=256, reasoning='disabled via official template kwargs, no forced reasoning tokens',
        temperature=0, seed=20261102, repeat_penalty=1.0, grammar=False, repair=False, retries=False,
        cache_prompt=False, server_parallel=4, server_context=8192, threads=8, batch=512, ubatch=512,
        evaluation_counts=dict(maintenance_fresh=len(fresh),maintenance_conditional=len(stress),bfcl=len(general),episodes=len(episodes)),
        screen_records=len(screen_ids)+6, development_records=len(development),
        pretrained_weights=True, fine_tuning=False, historical_adapted_results='Separate controls; not directly comparable to pretrained checkpoints.',
        data_scope='Previously inspected authored maintenance development and public BFCL; not an independent reliability test. New simulator episodes authored by the implementing agent, not blind human review.',
        bfcl_revision='6ea57973c7a6097fd7c5915698c54c17c5b1b6c8',
        general_scoring='Pinned upstream BFCL Python AST checker; synthetic episodes use exact call-set equality.',
        maintenance_scoring='Strict schema + exact canonical plan + trusted simulator counterfactual agreement.',
        generation='CPU llama.cpp quantized weight inference, backend default floating activation arithmetic; not FPGA arithmetic or FPGA latency.',
        files={str(p.relative_to(WORK)):digest(p) for p in [WORK/'development.jsonl',WORK/'evaluation.jsonl',WORK/'screen-ids.json']},
        server_sha256=digest(SERVER), server_version=subprocess.check_output([str(SERVER),'--version'],stderr=subprocess.STDOUT,text=True).strip())
    dump(WORK/'protocol.json',protocol)
    print(json.dumps({k:protocol[k] for k in ['evaluation_counts','screen_records','development_records','server_version']}),flush=True)

def post(endpoint, body, timeout=240):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}'+endpoint,
        data=json.dumps(body,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError('Local server '+endpoint+' HTTP '+str(exc.code)+': '+exc.read().decode('utf-8',errors='replace')) from exc

class Server:
    def __init__(self,item,folder,parallel=4,context=None,warmup=True):
        self.item,self.folder,self.parallel,self.context=item,folder,parallel,PROFILE_CONTEXT if context is None else context
        self.warmup=warmup
    def __enter__(self):
        global ACTIVE_BOS,ACTIVE_CONTEXT,ACTIVE_ARCH
        ACTIVE_CONTEXT=self.context
        audit=ROOT/'build/v2/model-capability-20261102/gguf-audits'/f"{self.item.get('base_key',self.item['key'])}.json"
        ACTIVE_BOS=rows_json(audit)['metadata'].get('tokenizer.ggml.bos_token_id') if audit.exists() else None
        ACTIVE_ARCH=rows_json(audit)['metadata'].get('general.architecture') if audit.exists() else None
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',PORT)) == 0:raise RuntimeError('Comparison port already in use')
        self.folder.mkdir(parents=True,exist_ok=True)
        self.log=(self.folder/'server.log').open('ab')
        args=[str(SERVER),'-m',self.item['path'],'--host','127.0.0.1','--port',str(PORT),'-c',str(self.parallel*self.context),'-np',str(self.parallel),
              '-t','8','-tb','8','-b','512','-ub','512','-ngl',str(GPU_LAYERS),'--jinja','--no-context-shift','--cache-ram','0','--reasoning-budget','-1' if THINKING else '0','-lv','4']
        if not self.warmup:args.append('--no-warmup')
        self.tick=time.perf_counter()
        self.process=subprocess.Popen(args,stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(180):
                if self.process.poll() is not None:raise RuntimeError('Server exited; see '+str(self.folder/'server.log'))
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=1) as r:
                        if r.status==200:break
                except Exception:time.sleep(1)
            else:raise TimeoutError('Server startup timeout')
            receipt=dict(args=args,pid=self.process.pid,startup_seconds=time.perf_counter()-self.tick,model=self.item)
            dump(self.folder/'server-start.json',receipt)
            attempt=self.folder/'attempts'/str(time.time_ns())
            dump(attempt/'server-start.json',receipt)
            props=local_get('/props')
            dump(self.folder/'server-props.json',props)
            dump(attempt/'server-props.json',props)
            return self
        except Exception:
            self.__exit__(None,None,None);raise
    def __exit__(self,*args):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        self.log.close()

def local_get(endpoint):
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}'+endpoint,timeout=20) as r:return json.load(r)

def normalize_schema(value):
    if isinstance(value,list):return [normalize_schema(x) for x in value]
    if not isinstance(value,dict):return value
    result={k:normalize_schema(v) for k,v in value.items()}
    if isinstance(result.get('type'),str):
        if result['type']=='any':result.pop('type')
        else:result['type']={'dict':'object','float':'number','tuple':'array'}.get(result['type'],result['type'])
    return result

def messages(case,route,previous=None):
    if case['domain']=='maintenance':
        system=SYSTEM_V2
        if route=='native':system+=' Submit exactly one submit_maintenance_plan call with the complete outcome array as plan_json.'
        user=json.dumps(public_input(case),separators=(',',':'))
        tools=[SUBMIT] if route=='native' else None
    else:
        system=GENERAL_SYSTEM if route=='native' else DIRECT_SYSTEM
        tools=[dict(type='function',function=normalize_schema(t)) for t in case['tools']] if route=='native' else None
        user=case['query'] if route=='native' else json.dumps(dict(request=case['query'],tools=case['tools']),separators=(',',':'))
    result=[dict(role='system',content=system)]
    demonstrations=WORK/'demonstrations.jsonl'
    if case['domain']=='maintenance' and demonstrations.exists():
        for example in rows(demonstrations):
            result.append(dict(role='user',content=json.dumps(public_input(example),separators=(',',':'))))
            payload=maintenance_encode(example['gold'])
            if route=='native':
                if ACTIVE_ARCH=='lfm2':
                    result.append(dict(role='assistant',content='<|tool_call_start|>[submit_maintenance_plan(plan_json='+repr(payload)+')]<|tool_call_end|>'))
                elif ACTIVE_ARCH=='smollm3':
                    result.append(dict(role='assistant',content='<tool_call>'+json.dumps(dict(name='submit_maintenance_plan',arguments=dict(plan_json=payload)))+'</tool_call>'))
                else:
                    result.append(dict(role='assistant',content=None,tool_calls=[dict(type='function',function=dict(name='submit_maintenance_plan',arguments=dict(plan_json=payload)))]))
            else:result.append(dict(role='assistant',content=payload))
    result.append(dict(role='user',content=user))
    if previous is not None:
        # A simulator follow-up shows a fixed authoritative sensor result, even
        # when the first proposal is wrong. Full episode success requires both.
        result += [dict(role='assistant',content=previous.get('decoded_output',previous['raw'])),dict(role='user',content='Simulator tool result: '+json.dumps(case['followup']['tool_result'])+'. Continue the original request using only the supplied tools. Return no call if its condition is false.')]
    return result,tools

def strip_format(raw):
    text=raw.strip()
    if '<think>' in text:
        if not text.startswith('<think>') or '</think>' not in text:raise ValueError('Incomplete or misplaced reasoning block')
        text=text.split('</think>',1)[1].strip()
    if text.startswith('```'):
        match=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',text,re.S)
        if not match:raise ValueError('Malformed code fence')
        text=match[1].strip()
    return text

def python_calls(text):
    parsed=ast.parse(text,mode='eval').body
    nodes=parsed.elts if isinstance(parsed,(ast.List,ast.Tuple)) else [parsed]
    result=[]
    def name(node):
        if isinstance(node,ast.Name):return node.id
        if isinstance(node,ast.Attribute):return name(node.value)+'.'+node.attr
        raise ValueError('Invalid function reference')
    for node in nodes:
        if not isinstance(node,ast.Call) or node.args or any(k.arg is None for k in node.keywords):raise ValueError('Expected keyword-only literal function calls')
        arguments={k.arg:ast.literal_eval(k.value) for k in node.keywords}
        if len(arguments)!=len(node.keywords):raise ValueError('Duplicate argument')
        result.append(dict(name=name(node.func),arguments=arguments))
    return result

def xml_function_call(text,tools):
    match=re.fullmatch(r'<function=([^<>\s]+)>\s*(.*?)\s*</function>',text,re.S)
    if not match:raise ValueError('Malformed native XML function')
    name,body=match.groups()
    specs={t.get('function',t)['name']:t.get('function',t) for t in (tools or [])}
    schema=specs.get(name,{}).get('parameters',{}).get('properties',{})
    parameters=list(re.finditer(r'<parameter=([^<>\s]+)>\s*(.*?)\s*</parameter>',body,re.S))
    if re.sub(r'<parameter=([^<>\s]+)>\s*(.*?)\s*</parameter>','',body,flags=re.S).strip():raise ValueError('Extra content in native XML function')
    args={}
    for parameter in parameters:
        key,value=parameter.groups()
        if key in args:raise ValueError('Duplicate XML parameter')
        kind=schema.get(key,{}).get('type')
        if kind=='string':
            if value.startswith('"'):
                try:
                    decoded=json.loads(value)
                    args[key]=decoded if isinstance(decoded,str) else value
                except json.JSONDecodeError:args[key]=value
            else:args[key]=value
        else:
            try:args[key]=json.loads(value)
            except json.JSONDecodeError:
                if kind in ['integer','number','float','boolean','object','dict','array','tuple']:raise ValueError('Malformed typed XML value')
                args[key]=value
    return dict(name=name,arguments=args)

def parse_calls(raw,tools=None,allow_text_no_calls=False):
    text=strip_format(raw)
    if '<|tool_call_start|>' in text:
        chunks=re.findall(r'<\|tool_call_start\|>\s*(.*?)\s*<\|tool_call_end\|>',text,re.S)
        if not chunks or len(chunks)!=text.count('<|tool_call_start|>') or len(chunks)!=text.count('<|tool_call_end|>'):
            raise ValueError('Incomplete native Python-call frame')
        # LFM's published assistant format permits explanatory text outside
        # explicit call blocks. Only the delimited block supplies calls.
        return sum([python_calls(c) for c in chunks],[])
    elif '<tool_call>' in text:
        chunks=re.findall(r'<tool_call>\s*(.*?)\s*</tool_call>',text,re.S)
        if not chunks or len(chunks)!=text.count('<tool_call>') or len(chunks)!=text.count('</tool_call>'):
            raise ValueError('Incomplete native call frame')
        if chunks and all(c.startswith('<function=') for c in chunks):
            # This model's published format explicitly permits leading rationale.
            end=text.rfind('</tool_call>')+len('</tool_call>')
            if text[end:].strip() and not allow_text_no_calls:raise ValueError('Extra suffix after XML calls')
            value=[xml_function_call(c,tools) for c in chunks]
        else:
            if re.sub(r'<tool_call>\s*.*?\s*</tool_call>','',text,flags=re.S).strip() and not allow_text_no_calls:raise ValueError('Extra text outside native calls')
            value=[json.loads(c) for c in chunks]
    elif text.startswith('<|tool_call_start|>') and text.endswith('<|tool_call_end|>'):
        return python_calls(text[len('<|tool_call_start|>'):-len('<|tool_call_end|>')].strip())
    else:
        try:value=json.loads(text)
        except json.JSONDecodeError:
            try:return python_calls(text)
            except (ValueError,TypeError,SyntaxError):
                framed=text.startswith(('[','{','<')) or bool(re.match(r'^[A-Za-z_][\w.]*\s*\(',text))
                if allow_text_no_calls and not framed:return []
                raise
    if isinstance(value,dict):value=[value]
    if not isinstance(value,list):raise ValueError('Expected call list')
    result=[]
    for call in value:
        if not isinstance(call,dict) or set(call)!={'name','arguments'} or not isinstance(call['name'],str):raise ValueError('Call must contain name and arguments only')
        args=call['arguments']
        if isinstance(args,str):args=json.loads(args)
        if not isinstance(args,dict):raise ValueError('Arguments must be object')
        result.append(dict(name=call['name'],arguments=args))
    return result

def summarize(results):
    groups={}
    for subset in sorted({r['subset'] for r in results}):
        group=[r for r in results if r['subset']==subset]
        groups[subset]=dict(count=len(group),correct=sum(r['correct'] for r in group),valid=sum(r['valid'] for r in group),
            accepted=sum(r['accepted'] for r in group),wrong_accepted=sum(r['accepted'] and not r['correct'] for r in group),
            context_rejections=sum(r['status']=='context_rejection' for r in group),truncated=sum(r.get('truncated',False) for r in group),
            median_wall_seconds=sorted(r['seconds'] for r in group)[len(group)//2])
    return groups

def run_batch(cases,route,output):
    completed={r['id'] for r in rows(output)} if output.exists() else set()
    pending=[c for c in cases if c['id'] not in completed]
    with output.open('a',encoding='utf-8') as f:
        for start in range(0,len(pending),4):
            chunk=pending[start:start+4]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures=[pool.submit(generate,c,route,i) for i,c in enumerate(chunk)]
                result=[future.result() for future in futures]
            for case,r in zip(chunk,result):
                if case['domain']=='episode':
                    second=generate(case,route,0,previous=r)
                    r['second_turn']=second
                    r['first_turn_correct']=r['correct']
                    r['correct']=r['correct'] and second['correct']
                    r['seconds']+=second['seconds']
                f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
            print(json.dumps(dict(output=str(output.relative_to(WORK)),done=len(completed)+min(start+4,len(pending)),total=len(cases))),flush=True)
    return rows(output)

def check_frozen():
    protocol=rows_json(WORK/'protocol.json')
    for name,sha in protocol['files'].items():
        if digest(WORK/name)!=sha:raise RuntimeError('Frozen data changed: '+name)
    if digest(SERVER)!=protocol['server_sha256']:raise RuntimeError('Server binary changed')
    if GPU_LAYERS!=protocol.get('gpu_layers',0):raise RuntimeError('GPU offload profile differs from protocol')
    if PROFILE_CONTEXT!=protocol['primary_context'] or OUTPUT_BUDGET!=protocol['output_tokens'] or THINKING!=protocol.get('thinking',False):
        raise RuntimeError('Context/output/reasoning profile differs from protocol')
    return protocol

def run_models(keys,phase):
    global CHECKER
    check_frozen()
    CHECKER=BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    # Known positive and negative upstream scorer fixtures before inference.
    from sysone.v2.general_tool_eval import checker_self_check
    checker_self_check(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker',
        rows(ROOT/'build/v2/general-tool-data-v1/external-evaluation.jsonl'),
        rows_json(ROOT/'build/v2/general-tool-data-v1/bfcl-answer-registry.json'))
    development=rows(WORK/'development.jsonl')
    evaluation=rows(WORK/'evaluation.jsonl')
    selected=set(rows_json(WORK/'screen-ids.json'))
    if phase=='screen':evaluation=[x for x in evaluation if x['id'] in selected]
    for item in rows_json(WORK/'models.json'):
        if keys and item['key'] not in keys:continue
        folder=WORK/'runs'/item['key']
        if (folder/f'{phase}-complete.json').exists():
            print('already completed '+item['key']+' '+phase,flush=True);continue
        if digest(Path(item['path']))!=item['sha256']:raise RuntimeError('Model digest mismatch')
        folder.mkdir(parents=True,exist_ok=True)
        source_sha=EXECUTED_SOURCE_SHA
        (folder/f'{phase}-source-{source_sha[:12]}.py').write_bytes(EXECUTED_SOURCE)
        try:
            with Server(item,folder/phase):
                choice_path=folder/'routes.json'
                if not choice_path.exists():
                    choices={}
                    for domain in ['maintenance','general']:
                        cases=[c for c in development if c['domain']==domain]
                        scores={}
                        for route in ['direct','native']:
                            result=run_batch(cases,route,folder/f'dev-{domain}-{route}.jsonl')
                            scores[route]=sum(r['correct'] for r in result)
                        choices[domain]='native' if scores['native']>scores['direct'] else 'direct'
                        choices[domain+'_scores']=scores
                    dump(choice_path,choices)
                choices=rows_json(choice_path)
                for domain in ['maintenance','general','episode']:
                    cases=[c for c in evaluation if c['domain']==domain]
                    route=choices['general' if domain=='episode' else domain]
                    run_batch(cases,route,folder/f'{phase}-{domain}.jsonl')
                all_results=sum([rows(folder/f'{phase}-{d}.jsonl') for d in ['maintenance','general','episode']],[])
                dump(folder/f'{phase}-complete.json',dict(model=item,source_sha256=source_sha,routes=choices,summary=summarize(all_results)))
                print(json.dumps(dict(model=item['key'],phase=phase,summary=summarize(all_results))),flush=True)
        except Exception as exc:
            dump(folder/f'{phase}-failure-{int(time.time())}.json',dict(type=type(exc).__name__,error=str(exc),source_sha256=source_sha))
            raise

def screen_report():
    reports=[]
    for item in rows_json(WORK/'models.json'):
        folder=WORK/'runs'/item['key']
        path=folder/'screen-complete.json'
        if not path.exists():continue
        results=sum([rows(folder/f'screen-{d}.jsonl') for d in ['maintenance','general','episode']],[])
        def acc(group):return sum(r['correct'] for r in group)/len(group) if group else 0
        components={s:acc([r for r in results if r['subset']==s]) for s in ['fresh','conditional','two_turn']}
        lookup={c['id']:c for c in rows(WORK/'evaluation.jsonl')}
        components['bfcl']=sum(acc([r for r in results if r['domain']=='general' and lookup[r['id']]['category']==cat]) for cat in ['simple_python','multiple','parallel','parallel_multiple','irrelevance'])/5
        reports.append(dict(model=item['key'],balanced=sum(components.values())/4,components=components,summary=rows_json(path)['summary']))
    reports.sort(key=lambda x:x['balanced'],reverse=True)
    finalists=[]
    if len(reports)==8:
        finalists.append(reports[0]['model'])
        finalists.append(next(x['model'] for x in reports if x['model'] not in finalists and x['model'] in ['qwen06-q4','qwen17-q4','qwen4-q4','xlam3-q4']))
    dump(WORK/'screen-comparison.json',dict(reports=reports,finalists=finalists,complete=len(reports)==8))
    print(json.dumps(dict(reports=reports,finalists=finalists),indent=2),flush=True)

def revise():
    parent=ROOT/'build/v2/model-capability-20261102'
    if WORK==parent:raise ValueError('Use a new --work directory')
    WORK.mkdir(parents=True,exist_ok=False)
    for name in ['models.json','development.jsonl','evaluation.jsonl','screen-ids.json']:
        shutil.copyfile(parent/name,WORK/name)
    shutil.copyfile(parent/'protocol.json',WORK/'parent-protocol.json')
    train=rows(ROOT/'build/v2/maintenance-sft-v3/train.jsonl')
    examples=[next(c for c in train if c['stratum']=='direct' and c['gold']['steps'][0]['tool']=='read_metric'),
              next(c for c in train if c['stratum']=='conditional' and len(c['gold']['steps'])==3)]
    write_rows(WORK/'demonstrations.jsonl',examples)
    protocol=rows_json(parent/'protocol.json')
    protocol['maintenance_demonstrations']=dict(count=2,source='Existing maintenance training split; fixed first direct metric request and first three-step conditional request. Same examples for every candidate.',ids=[c['id'] for c in examples])
    protocol['amendment']=dict(reason='Observed 0/12 valid maintenance development outputs for both zero-shot 0.6B and 1.7B; codec unfamiliarity can confound interpretation. Add fixed training demonstrations uniformly before revised evaluation.',
        observed_parent_results='0.6B screen maintenance 0/48; 1.7B development direct/native 0/12 each. Parent artifacts retained; revised evaluation is development evidence, not blind.',
        selection_rule_unchanged=True,all_evaluation_inputs_unchanged=True,all_models_same_examples=True)
    protocol['files']={name:digest(WORK/name) for name in ['development.jsonl','evaluation.jsonl','screen-ids.json','demonstrations.jsonl']}
    dump(WORK/'protocol.json',protocol)
    print(json.dumps(protocol['amendment']),flush=True)

def precision_plan():
    path=WORK/'precision-plan.json'
    if path.exists():return
    data=rows(WORK/'evaluation.jsonl')
    ids=[]
    for stratum in sorted({c['stratum'] for c in data if c['subset']=='fresh'}):
        ids += [c['id'] for c in data if c['subset']=='fresh' and c['stratum']==stratum][:2]
    for op in ['gt','ge','lt','le']:
        ids += [c['id'] for c in data if c['subset']=='conditional' and c['gold']['predicate']['op']==op][:2]
    for category in ['simple_python','multiple','parallel','parallel_multiple','irrelevance']:
        ids += [c['id'] for c in data if c['domain']=='general' and c['category']==category][:2]
    ids += [c['id'] for c in data if c['domain']=='episode'][:2]
    candidates=[]
    for item in rows_json(WORK/'models.json'):
        name=item['filename'].replace('Q4_0','Q8_0')
        tree=get(f"https://huggingface.co/api/models/{item['repo']}/tree/{item['revision']}?recursive=true")
        file=next(x for x in tree if x.get('path')==name)
        candidates.append(dict(item,key=item['key']+'-q8reference',base_key=item['key'],filename=name,
                               bytes=file['size'],sha256=file['lfs']['oid'],path=str(CACHE/name),quantization='Q8_0 higher-precision software reference'))
    dump(path,dict(ids=ids,candidates=candidates,selection='First fixed IDs by stratum/operator/category, no model correctness feedback. Two finalists only.',
        purpose='Quantization sensitivity, not a float32 or FPGA arithmetic reference.',parallel=1,context=2048,output=256))
    print(json.dumps(dict(precision_cases=len(ids))),flush=True)

def accelerate():
    parent=ROOT/'build/v2/model-capability-20261102-r2'
    if WORK==parent:raise ValueError('Use a new --work directory')
    WORK.mkdir(parents=True,exist_ok=False)
    for name in ['models.json','development.jsonl','evaluation.jsonl','screen-ids.json','demonstrations.jsonl','precision-plan.json']:
        shutil.copyfile(parent/name,WORK/name)
    shutil.copyfile(parent/'protocol.json',WORK/'parent-protocol.json')
    protocol=rows_json(parent/'protocol.json')
    protocol['gpu_layers']=GPU_LAYERS
    protocol['server_sha256']=digest(SERVER)
    protocol['server_version']=subprocess.check_output([str(SERVER),'--version'],stderr=subprocess.STDOUT,text=True).strip()
    protocol['generation']='Pinned b11540 Vulkan runtime, requested full GPU layer offload on Radeon780M. Backend arithmetic is not FPGA arithmetic. All primary candidates use this same runtime/configuration.'
    protocol['runtime_amendment']=dict(reason='CPU study is slow; use locally available GPU for the complete primary comparison. CPU attempts retained separately, never mixed into primary rankings.',
        qualification='11 fixed development probes; all prompt IDs identical to CPU, 10/11 raw outputs identical, one complete-decision difference. Not bit-exact. Same source commit, different backend.',
        data_and_model_hashes_unchanged=True,prompt_selection_and_finalist_rules_unchanged=True,
        parent_attempt=str(parent),qualification_directory=str(parent/'vulkan-qualification'))
    dump(WORK/'protocol.json',protocol)
    for name in ['gold-fixture-qualification.json','runtime-environment.json']:
        if (parent/name).exists():shutil.copyfile(parent/name,WORK/('parent-'+name))
    shutil.copytree(parent/'dependencies',WORK/'dependencies')
    shutil.copytree(parent/'controls',WORK/'controls')
    print(json.dumps(protocol['runtime_amendment']),flush=True)

def precision_run(keys):
    global CHECKER
    check_frozen();precision_plan()
    CHECKER=BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    plan=rows_json(WORK/'precision-plan.json')
    data={c['id']:c for c in rows(WORK/'evaluation.jsonl')}
    cases=[data[i] for i in plan['ids']]
    for key in keys:
        q4=next(x for x in rows_json(WORK/'models.json') if x['key']==key)
        q8=next(x for x in plan['candidates'] if x['base_key']==key)
        download_one(q8)
        choices=rows_json(WORK/'runs'/key/'routes.json')
        for label,item in [('q4',q4),('q8',q8)]:
            folder=WORK/'precision'/key/label
            folder.mkdir(parents=True,exist_ok=True)
            path=folder/'predictions.jsonl'
            completed={r['id'] for r in rows(path)} if path.exists() else set()
            if len(completed)==len(cases):continue
            with Server(item,folder,parallel=1,context=PROFILE_CONTEXT),path.open('a',encoding='utf-8') as f:
                for c in cases:
                    if c['id'] in completed:continue
                    route=choices['maintenance' if c['domain']=='maintenance' else 'general']
                    result=generate(c,route,0)
                    if c['domain']=='episode':
                        second=generate(c,route,0,previous=result)
                        result['second_turn']=second
                        result['first_turn_correct']=result['correct']
                        result['correct']=result['correct'] and second['correct']
                        result['seconds']+=second['seconds']
                    f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush()
                    print(json.dumps(dict(precision=key,format=label,done=len(completed)+1,total=len(cases))),flush=True)
                    completed.add(c['id'])
        left={r['id']:r for r in rows(WORK/'precision'/key/'q4/predictions.jsonl')}
        right={r['id']:r for r in rows(WORK/'precision'/key/'q8/predictions.jsonl')}
        comparison=dict(n=len(left),q4_correct=sum(r['correct'] for r in left.values()),q8_correct=sum(r['correct'] for r in right.values()),
            identical_prompt_ids=all(left[k]['prompt_ids']==right[k]['prompt_ids'] for k in left),
            correctness_disagreements=[dict(id=k,q4=left[k]['correct'],q8=right[k]['correct']) for k in left if left[k]['correct']!=right[k]['correct']],
            q4_summary=summarize(list(left.values())),q8_summary=summarize(list(right.values())),
            scope='Single-slot software Q4-release versus Q8-release with matched prompts. Not FPGA quantization qualification.')
        dump(WORK/'precision'/key/'comparison.json',comparison)
        if not comparison['identical_prompt_ids']:raise RuntimeError('Precision comparison prompt IDs differ')
        print(json.dumps(dict(model=key,precision_comparison=comparison)),flush=True)

def rescue_context(keys):
    global CHECKER
    CHECKER=BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    lookup={c['id']:c for c in rows(WORK/'evaluation.jsonl')}
    for key in keys:
        folder=WORK/'runs'/key
        records=sum([rows(folder/f'confirm-{d}.jsonl') for d in ['maintenance','general','episode']],[])
        candidates=[lookup[r['id']] for r in records if r['status']=='context_rejection']
        if not candidates:
            dump(folder/'context4096-summary.json',dict(cases=0,reason='No primary context overflows'));continue
        item=next(x for x in rows_json(WORK/'models.json') if x['key']==key)
        choices=rows_json(folder/'routes.json')
        out=folder/'context4096-predictions.jsonl'
        done={r['id'] for r in rows(out)} if out.exists() else set()
        with Server(item,folder/'context4096',parallel=1,context=4096),out.open('a',encoding='utf-8') as f:
            for c in candidates:
                if c['id'] in done:continue
                r=generate(c,choices['maintenance' if c['domain']=='maintenance' else 'general'],0)
                f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
        dump(folder/'context4096-summary.json',dict(cases=len(candidates),summary=summarize(rows(out))))

def generate(case,route,slot=0,previous=None):
    tick=time.perf_counter()
    message,tools=messages(case,route,previous)
    body=dict(messages=message,add_generation_prompt=True,chat_template_kwargs=dict(enable_thinking=THINKING),enable_thinking=THINKING)
    if tools:body['tools']=tools
    template=post('/apply-template',body)
    prompt=template['prompt']
    tokens=post('/tokenize',dict(content=prompt,add_special=True,parse_special=True))['tokens']
    duplicate_bos=ACTIVE_BOS is not None and len(tokens)>1 and tokens[0]==tokens[1]==ACTIVE_BOS
    if duplicate_bos:tokens=tokens[1:]
    reasoning_open=THINKING and prompt.rstrip().endswith('<think>')
    base=dict(id=case['id'],domain=case['domain'],subset=case['subset'],route=route,prompt=prompt,prompt_ids=tokens,
              input_tokens=len(tokens),output_budget=OUTPUT_BUDGET,context_limit=ACTIVE_CONTEXT,removed_duplicate_bos=duplicate_bos,
              reasoning_prefix_in_prompt=reasoning_open,thinking=THINKING,
              runner_source_sha256=EXECUTED_SOURCE_SHA,valid=False,correct=False,accepted=False)
    if len(tokens)+OUTPUT_BUDGET>ACTIVE_CONTEXT:
        return dict(base,status='context_rejection',raw='',seconds=time.perf_counter()-tick)
    request=dict(prompt=tokens,n_predict=OUTPUT_BUDGET,temperature=0,seed=20261102,repeat_penalty=1.0,
                 cache_prompt=False,id_slot=slot,return_tokens=True,samplers=['temperature'],grammar='')
    response=post('/completion',request)
    base.update(status='generated',raw=response['content'],seconds=time.perf_counter()-tick,
                response=response,generated_tokens=response.get('tokens_predicted'),timings=response.get('timings'),
                truncated=bool(response.get('truncated') or response.get('stopped_limit') or response.get('stop_type')=='limit'))
    decode_tick=time.perf_counter()
    base['decoded_output']=decode_generated(response)
    base['decode_seconds']=time.perf_counter()-decode_tick
    try:
        parse_text=('<think>'+base['decoded_output']) if reasoning_open else base['decoded_output']
        if case['domain']=='maintenance':
            if route=='native':
                calls=parse_calls(parse_text,tools,allow_text_no_calls=route=='native')
                if len(calls)!=1 or calls[0]['name']!='submit_maintenance_plan' or set(calls[0]['arguments'])!={'plan_json'}:raise ValueError('Expected exactly one maintenance submission')
                payload=calls[0]['arguments']['plan_json']
                if not isinstance(payload,str):raise ValueError('plan_json must be a string')
            else:payload=strip_format(parse_text)
            predicted=maintenance_parse(payload,case['catalog'])
            base.update(valid=True,predicted=predicted,**maintenance_score(case,predicted))
        else:
            calls=parse_calls(parse_text,tools or case['tools'],allow_text_no_calls=route=='native')
            base.update(valid=True,predicted=calls,accepted=bool(calls))
            if case['domain']=='episode':
                gold=case['followup']['gold'] if previous else case['gold']
                base['correct']=sorted(json.dumps(x,sort_keys=True) for x in calls)==sorted(json.dumps(x,sort_keys=True) for x in gold)
            else:
                check=CHECKER.score(case,calls,case['gold'])
                base.update(correct=bool(check['valid']),checker=check)
    except (ValueError,TypeError,KeyError,IndexError,SyntaxError) as exc:
        base['error']=type(exc).__name__+': '+str(exc)
    if base['truncated']:base.update(correct=False)
    return base

CHECKER=None

def decode_generated(response):
    tokens=list(response.get('tokens',[]))
    if not tokens:return response['content']
    if response.get('stop_type')=='eos':tokens=tokens[:-1]
    return post('/detokenize',dict(tokens=tokens))['content']

def probe(key):
    global CHECKER
    CHECKER=BFCLPythonChecker(ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker')
    item=next(x for x in rows_json(WORK/'models.json') if x['key']==key)
    cases=rows(WORK/'development.jsonl')
    with Server(item,WORK/'probe'/key):
        for domain in ['maintenance','general']:
            case=next(x for x in cases if x['domain']==domain)
            for route in ['direct','native']:
                result=generate(case,route)
                dump(WORK/'probe'/key/f'{domain}-{route}.json',result)
                print(json.dumps({k:result.get(k) for k in ['id','route','input_tokens','seconds','valid','correct','raw','error']}),flush=True)

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Sysone-capability-comparison/1'}), timeout=60) as r:
        return json.load(r)

def prepare_models():
    if (WORK/'models.json').exists():
        return
    result = []
    for key, repo, name in MODELS:
        info = get('https://huggingface.co/api/models/'+repo)
        revision = info['sha']
        tree = get(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true')
        item = next(x for x in tree if x.get('path') == name)
        result.append(dict(key=key, repo=repo, revision=revision, filename=name,
                           bytes=item['size'], sha256=item['lfs']['oid'],
                           path=str(CACHE/name), quantization='Q4_0 release; tensor mix audited separately'))
        dump(WORK/'metadata'/f'{key}.json', dict(api=info, file=item))
    dump(WORK/'models.json', result)
    print(json.dumps({'pinned_models':len(result),'download_bytes':sum(x['bytes'] for x in result)}), flush=True)

def download_one(item):
    target = Path(item['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == item['bytes'] and digest(target) == item['sha256']:
        print('verified existing '+item['key'], flush=True)
        return
    partial = target.with_suffix('.gguf.partial')
    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['filename']}?download=true"
    tick = time.perf_counter()
    parts=target.parent/(target.name+'.parts')
    parts.mkdir(exist_ok=True)
    extent=16 << 20
    def part(start):
        end=min(start+extent,item['bytes'])-1
        dest=parts/f'{start:012d}.part'
        if dest.exists() and dest.stat().st_size==end-start+1:return dest
        for attempt in range(3):
            try:
                request=urllib.request.Request(url+f'&start={start}&attempt={attempt}',headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=60) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f"bytes {start}-{end}/{item['bytes']}":
                        raise RuntimeError('Range not honored')
                    data=response.read(end-start+1)
                if len(data)!=end-start+1:raise RuntimeError('Short range')
                dest.write_bytes(data);return dest
            except Exception:
                if attempt==2:raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        chunks=list(pool.map(part,range(0,item['bytes'],extent)))
    with partial.open('wb') as out:
        for chunk in chunks:
            with chunk.open('rb') as source:shutil.copyfileobj(source,out,4 << 20)
    if partial.stat().st_size!=item['bytes'] or digest(partial)!=item['sha256']:raise RuntimeError('Size or SHA256 mismatch')
    partial.replace(target)
    dump(WORK/'downloads'/f"{item['key']}.json",dict(item,verified=True,method='16MiB HTTP ranges, final full SHA256',seconds=time.perf_counter()-tick))
    print('downloaded and verified '+item['key']+' '+str(round(time.perf_counter()-tick,1))+'s',flush=True)

def download():
    prepare_models()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download_one, rows_json(WORK/'models.json')))

def rows_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['download','freeze','probe','screen','confirm','report-screen','revise','precision-plan','precision','rescue','accelerate'])
    ap.add_argument('--model',default='qwen06-q4')
    ap.add_argument('--work',type=Path)
    ap.add_argument('--server',type=Path)
    ap.add_argument('--gpu-layers',type=int,default=0)
    ap.add_argument('--thinking',action='store_true')
    ap.add_argument('--context',type=int,default=2048)
    ap.add_argument('--output-budget',type=int,default=256)
    args = ap.parse_args()
    if args.work:WORK=args.work.resolve()
    if args.server:SERVER=args.server.resolve()
    GPU_LAYERS=args.gpu_layers
    THINKING=args.thinking
    PROFILE_CONTEXT=args.context
    OUTPUT_BUDGET=args.output_budget
    if args.command not in ['revise','accelerate']:
        invocation=WORK/'invocations'/str(time.time_ns())
        dump(invocation/'invocation.json',dict(argv=sys.argv,executed_source_sha256=EXECUTED_SOURCE_SHA,python=sys.executable))
        (invocation/'runner.py').write_bytes(EXECUTED_SOURCE)
    if args.command == 'download':
        download()
    elif args.command == 'freeze':freeze()
    elif args.command == 'probe':probe(args.model)
    elif args.command in ['screen','confirm']:run_models(args.model.split(',') if args.model!='all' else [],args.command)
    elif args.command == 'report-screen':screen_report()
    elif args.command == 'revise':revise()
    elif args.command == 'precision-plan':precision_plan()
    elif args.command == 'precision':precision_run(args.model.split(','))
    elif args.command == 'rescue':rescue_context(args.model.split(','))
    elif args.command == 'accelerate':accelerate()
