"""Isolated ONNX/DirectML inference qualification for the local Radeon GPU.

Run with .venv-maintenance-accel, which inherits the unchanged benchmark packages
through a .pth file and installs ONNX tools locally. No driver/NPU/FPGA changes.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8')
RUNTIME_SOURCE=Path(__file__).read_bytes()
RUNTIME_SHA=hashlib.sha256(RUNTIME_SOURCE).hexdigest()
import numpy as np
import onnx
from onnx import helper,TensorProto
import onnxruntime as ort

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'build/v2/maintenance-decisions-v4'
FOLDER=WORK/'directml'


def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def options(profile=False):
    s=ort.SessionOptions();s.enable_mem_pattern=False
    s.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;s.intra_op_num_threads=2
    s.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if profile:s.enable_profiling=True;s.profile_file_prefix=str(FOLDER/'profile')
    return s


def session(path,profile=False):
    if 'DmlExecutionProvider' not in ort.get_available_providers():raise RuntimeError('DirectML is unavailable')
    s=ort.InferenceSession(str(path),sess_options=options(profile),providers=[('DmlExecutionProvider',{'device_id':0})])
    s.disable_fallback()
    if s.get_providers()[0]!='DmlExecutionProvider':raise RuntimeError('GPU provider was not selected')
    return s


def ready():
    a=helper.make_tensor_value_info('a',TensorProto.FLOAT,[4,4]);y=helper.make_tensor_value_info('y',TensorProto.FLOAT,[4,4])
    weight=np.arange(16,dtype=np.float32).reshape(4,4)
    graph=helper.make_graph([helper.make_node('MatMul',['a','w'],['y'])],'gpu-readiness',[a],[y],[onnx.numpy_helper.from_array(weight,name='w')])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',18)],ir_version=10)
    path=FOLDER/'readiness.onnx';onnx.save(model,str(path));s=session(path,True)
    x=np.eye(4,dtype=np.float32);got=s.run(None,{'a':x})[0];assert np.allclose(got,weight)
    profile=Path(s.end_profiling());events=json.loads(profile.read_text())
    providers=sorted({e.get('args',{}).get('provider','') for e in events if e.get('cat')=='Node'})
    if not any('Dml' in p for p in providers):raise RuntimeError('No actual GPU node execution was profiled')
    result=dict(onnxruntime=ort.__version__,available_providers=ort.get_available_providers(),session_providers=s.get_providers(),
        execution_providers_observed=providers,numerical_check=True,profile=str(profile),driver_changed=False)
    dump(FOLDER/'readiness.json',result);print(json.dumps(result),flush=True)


def get_items(tok,case,classes):
    from maintenance_decisions import LAYA_CONTRACT,features,public_input,field_question,option_text
    from laya.common import build_sequence,QTYPES
    result=[]
    for k,vs in classes.items():
        if len(vs)==1:continue
        q=dict(t='choice',ins=field_question(k),crit={f'v{i}':option_text(k,v) for i,v in enumerate(vs)})
        ids,markers,stats,trunc=build_sequence(tok,LAYA_CONTRACT+'\n'+features(public_input(case)),q,
            max_len=1024,head_max_len=256,return_stats=True,return_truncation_stats=True)
        if trunc['truncated'] or stats['options_distinct']!=len(vs):raise RuntimeError('Truncated input')
        result.append((k,dict(ids=ids,markers=markers,qtype=QTYPES['choice'])))
    return result


def feed(item,length,width,pad):
    if len(item['ids'])>length or len(item['markers'])>width:raise RuntimeError('Static export envelope exceeded')
    ids=np.full((1,length),pad,dtype=np.int64);att=np.zeros((1,length),dtype=np.int64)
    ids[0,:len(item['ids'])]=item['ids'];att[0,:len(item['ids'])]=1
    pos=np.zeros((1,width),dtype=np.int64);mask=np.zeros((1,width),dtype=bool)
    pos[0,:len(item['markers'])]=item['markers'];mask[0,:len(item['markers'])]=True
    return dict(input_ids=ids,attention_mask=att,marker_pos=pos,marker_mask=mask,qtype=np.array([0],dtype=np.int64))


def export():
    import torch
    import laya
    from maintenance_decisions import read_rows
    torch.set_num_threads(4)
    torch.backends.mha.set_fastpath_enabled(False)
    agent=laya.load(str(ROOT/'models/laya-typed-decisions'),device='cpu',compile=False,fast=False)
    agent.model.float().eval();agent.model.requires_grad_(False)
    classes=json.loads((WORK/'classes.json').read_text());maximum=0
    for split in ('calibration','fresh','conditional'):
        for c in read_rows(WORK/(split+'.jsonl')):
            maximum=max(maximum,max(len(it['ids']) for _,it in get_items(agent.tok,c,classes)))
    length=32*((maximum+31)//32);width=max(map(len,classes.values()))
    if length>1024:raise RuntimeError('Model input budget exceeded')
    item=get_items(agent.tok,read_rows(WORK/'calibration.jsonl')[0],classes)[0][1]
    values=feed(item,length,width,agent.tok.pad_token_id)
    class ChoiceOnly(torch.nn.Module):
        def __init__(self,base):super().__init__();self.base=base
        def forward(self,input_ids,attention_mask,marker_pos,marker_mask,qtype):
            logits,_=self.base(input_ids,attention_mask,marker_pos,marker_mask,qtype)
            return logits
    wrapper=ChoiceOnly(agent.model).eval();args=tuple(torch.from_numpy(v) for v in values.values())
    with torch.inference_mode():reference=wrapper(*args).numpy()
    np.savez(FOLDER/'reference.npz',logits=reference,**values)
    dump(FOLDER/'envelope.json',dict(sequence_length=length,maximum_actual_tokens=maximum,marker_width=width,
        batch_size=1,pad_token=agent.tok.pad_token_id,precision='float32',opset=18,public_input_only=True))
    print(json.dumps(dict(phase='export',length=length,marker_width=width)),flush=True)
    torch.onnx.export(wrapper,args,str(FOLDER/'laya-float32.onnx'),input_names=list(values),output_names=['logits'],
        opset_version=18,export_params=True,external_data=True,dynamo=True)
    print('Export complete',flush=True)


def probe():
    from transformers import AutoTokenizer
    from maintenance_decisions import read_rows,softmax
    env=json.loads((FOLDER/'envelope.json').read_text());classes=json.loads((WORK/'classes.json').read_text())
    tok=AutoTokenizer.from_pretrained(str(ROOT/'models/laya-typed-decisions/tokenizer'),local_files_only=True)
    s=session(FOLDER/env.get('onnx_file','laya-float32.onnx'),True)
    ref=np.load(FOLDER/'reference.npz');values={k:ref[k] for k in ref.files if k!='logits'}
    got=s.run(None,values)[0]
    assert np.allclose(softmax(got[0]),softmax(ref['logits'][0]),atol=.001,rtol=0)
    cases=read_rows(WORK/'calibration.jsonl')
    archived=read_rows(WORK/'laya-float32-qualification/calibration-predictions.jsonl')
    results=[]
    for index in (0,20,40,60,80):
        c=cases[index];reference=archived[index];assert c['id']==reference['id']
        tick=time.perf_counter();error=0.;identical=True
        for k,item in get_items(tok,c,classes):
            logits=s.run(None,feed(item,env['sequence_length'],env['marker_width'],env['pad_token']))[0][0,:len(classes[k])]
            p=softmax(logits);target=softmax(reference['field_logits'][k])
            error=max(error,float(np.abs(p-target).max()));identical=identical and int(p.argmax())==int(target.argmax())
        results.append(dict(id=c['id'],seconds=time.perf_counter()-tick,max_probability_error=error,all_choice_argmaxes_identical=identical))
        print(json.dumps(results[-1]),flush=True)
        if error>=.001 or not identical:break
    profile=Path(s.end_profiling());events=json.loads(profile.read_text());providers={}
    for e in events:
        if e.get('cat')=='Node':
            key=e.get('args',{}).get('provider','unknown');providers[key]=providers.get(key,0)+1
    passed=len(results)==5 and all(x['max_probability_error']<.001 and x['all_choice_argmaxes_identical'] for x in results) and any('Dml' in p for p in providers)
    dump(FOLDER/'qualification.json',dict(passed=passed,gate='5 calibration cases; max probability error<.001; every choice argmax matches fp32; GPU nodes observed',
        results=results,execution_provider_node_events=providers,precision='float32',calibration_only=True,profile=str(profile)))
    print(json.dumps(dict(passed=passed,execution_provider_node_events=providers)),flush=True)


def static_shapes():
    """Specialize Reshape shape inputs to the already fixed tensor envelope.

    No weights or tensor values change. Avoids the documented DirectML/dynamo
    view(-1) shape-inference failure. Still requires CPU and GPU qualification.
    """
    model=onnx.load(str(FOLDER/'laya-float32.onnx'),load_external_data=False)
    values={v.name:v for v in list(model.graph.input)+list(model.graph.output)+list(model.graph.value_info)}
    count=0
    for node in model.graph.node:
        if node.op_type!='Reshape':continue
        info=values.get(node.output[0])
        if info is None:continue
        dims=info.type.tensor_type.shape.dim
        if not dims or any(not d.HasField('dim_value') or d.dim_value<=0 for d in dims):continue
        name=f'directml_static_shape_{count}';shape=np.array([d.dim_value for d in dims],dtype=np.int64)
        model.graph.initializer.append(onnx.numpy_helper.from_array(shape,name=name));node.input[1]=name;count+=1
    path=FOLDER/'laya-float32-static.onnx';onnx.save_model(model,str(path))
    env=json.loads((FOLDER/'envelope.json').read_text());env['onnx_file']=path.name;env['static_reshape_specializations']=count
    dump(FOLDER/'envelope.json',env);print(json.dumps(dict(static_reshape_specializations=count)),flush=True)


def evaluate():
    from transformers import AutoTokenizer
    from maintenance_decisions import read_rows,decode,summary,sha
    qualification=json.loads((FOLDER/'qualification.json').read_text())
    if not qualification['passed']:raise RuntimeError('Unqualified GPU model')
    env=json.loads((FOLDER/'envelope.json').read_text());classes=json.loads((WORK/'classes.json').read_text())
    tok=AutoTokenizer.from_pretrained(str(ROOT/'models/laya-typed-decisions/tokenizer'),local_files_only=True)
    graph=FOLDER/env['onnx_file'];out=WORK/'laya-directml';out.mkdir(exist_ok=True)
    dump(WORK/'laya-runtime-selection.json',dict(folder='laya-directml',precision='float32 DirectML GPU',
        selection='calibration-only numerical qualification and measured runtime; no evaluation accuracy selection',
        qualification_sha256=sha(FOLDER/'qualification.json'),cpu_attempts_retained=True,
        weights_and_questions_unchanged=True,static_sequence_envelope=env['sequence_length']))
    s=session(graph)
    for split in ('calibration','fresh','conditional'):
        path=out/(split+'-predictions.jsonl');done=read_rows(path) if path.exists() else []
        cases=read_rows(WORK/(split+'.jsonl'));assert [r['id'] for r in done]==[c['id'] for c in cases[:len(done)]]
        for index,c in enumerate(cases[len(done):],len(done)):
            tick=time.perf_counter();items=get_items(tok,c,classes)
            z={k:[0.] for k,vs in classes.items() if len(vs)==1}
            for k,item in items:
                logits=s.run(None,feed(item,env['sequence_length'],env['marker_width'],env['pad_token']))[0][0]
                z[k]=logits[:len(classes[k])].tolist()
            row=decode(c,z,classes,time.perf_counter()-tick)
            row.update(precision='float32 DirectML GPU',input_tokens_max=max(len(it['ids']) for _,it in items),
                input_tokens_sum=sum(len(it['ids']) for _,it in items),question_count=len(items),
                padded_tokens_processed=len(items)*env['sequence_length'],native_choice_logits=True,
                static_sequence_length=env['sequence_length'])
            with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            done.append(row)
            if (index+1)%10==0:print(json.dumps(dict(model='laya-directml',split=split,completed=index+1,correct=sum(r['correct'] for r in done))),flush=True)
        dump(out/(split+'-summary.json'),summary(done))
    dump(out/'model.json',dict(precision='float32 DirectML GPU',maintenance_finetuned=False,
        graph_sha256=sha(graph),weights_data_sha256=sha(FOLDER/'laya-float32.onnx.data'),graph_path=str(graph),
        qualification_sha256=sha(FOLDER/'qualification.json'),static_sequence_length=env['sequence_length'],
        maximum_actual_tokens=env['maximum_actual_tokens'],question_batch_size=1,source_sha256=RUNTIME_SHA,
        provider_execution_verified=True,source_revision='a478221bcad24d1a9c47b361c79328ebd2b100c6',
        model_download=json.loads((WORK/'laya-download.json').read_text()),
        files_sha256={p.relative_to(ROOT/'models/laya-typed-decisions').as_posix():sha(p) for p in (ROOT/'models/laya-typed-decisions').rglob('*') if p.is_file() and '.cache' not in p.parts}))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['ready','export','probe','static','evaluate'])
    ap.add_argument('--work',type=Path,default=WORK);a=ap.parse_args();WORK=a.work;FOLDER=WORK/'directml';FOLDER.mkdir(parents=True,exist_ok=True)
    ledger=WORK/'invocations';ledger.mkdir(exist_ok=True);stem=f'directml-{a.phase}-{time.time_ns()}'
    (ledger/(stem+'.py')).write_bytes(RUNTIME_SOURCE)
    dump(ledger/(stem+'.json'),dict(phase='directml-'+a.phase,source_sha256=RUNTIME_SHA,
        protocol_sha256=hashlib.sha256((WORK/'protocol.json').read_bytes()).hexdigest(),arguments=dict(phase=a.phase,work=str(WORK))))
    if a.phase=='ready':ready()
    elif a.phase=='export':export()
    elif a.phase=='static':static_shapes()
    elif a.phase=='evaluate':evaluate()
    else:probe()
