"""Fresh development comparison of immutable v4 weights and typed joint decoding."""
import argparse,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import torch
from transformers import AutoTokenizer
from sysone.v2.general_schema_annotations import adapt_records
from sysone.v2.general_tool_encoder import ToolEncoder
from sysone.v2.general_training_v2 import encoder_text
from sysone.v2.general_tools import normalize_tool,validate_calls
from sysone.v2.general_call_matching import exact_calls
from sysone.v2.general_encoder_decode_v5 import decode_argument

def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--split',choices=['selection','audit'],default='selection');ap.add_argument('--threads',type=int,default=2);ap.add_argument('--checkpoint',type=Path,default=ROOT/'build/v2/general-tool-expanded-training-v4/encoder/best.pt');args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(args.threads)
    prior=ROOT/'build/v2/general-tool-expanded-training-v4/encoder'
    run=json.loads((prior/'run.json').read_text(encoding='utf-8'));model_path=run['arguments']['model']
    data=ROOT/'build/v2/general-tool-data-v1';dev=[json.loads(x) for x in (data/'dev.jsonl').read_text(encoding='utf-8').splitlines()];random.Random(2026101702).shuffle(dev)
    # Exclude every component in the historical inspected prefix and every saved audit.
    blocked={r['split_component'] for r in dev[:256]}
    exposure=[]
    for directory in ['general-tool-clean-training-v3/encoder','general-tool-clean-training-v3/functiongemma','general-tool-expanded-training-v4/encoder']:
        for name in ['selection-cases.json','audit-cases.json']:
            p=ROOT/'build/v2'/directory/name
            if p.exists():
                rows=json.loads(p.read_text(encoding='utf-8'));blocked.update(r['split_component'] for r in rows);exposure.append(str(p.relative_to(ROOT)))
    fresh=[r for r in dev if r['split_component'] not in blocked];selection=fresh[:64];selected_components={r['split_component'] for r in selection};audit=[r for r in fresh[64:] if r['split_component'] not in selected_components][:64]
    assert len(selection)==len(audit)==64
    def augment(rows,phrase):return adapt_records(rows+[{**r,'id':r['id']+':deny-v5','query':phrase,'answers':[],'provenance':'synthetic_explicit_no_action_instruction'} for r in rows[::8]])
    splits={args.split:adapt_records(json.loads((args.protocol/(args.split+'-cases.json')).read_text(encoding='utf-8')))}
    for name,rows in splits.items():dump(args.out/(name+'-cases.json'),rows)
    sources=[Path(__file__),ROOT/'src/sysone/v2/general_encoder_decode_v5.py']
    manifest={'stage':'running','execution':'CPU_only','threads':args.threads,'parent_checkpoint':str(args.checkpoint),'parent_checkpoint_sha256':digest(args.checkpoint),'warm_start':True,'prior_dev_exposure':exposure,'bfcl_used_for_selection':False,'blind_test':False,'protocol':str(args.protocol),'protocol_cases_sha256':digest(args.protocol/(args.split+'-cases.json')),'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sources},'data_sha256':digest(data/'dev.jsonl'),'candidates':['legacy_independent_argmax','typed_joint_span'],'predetermined_candidate':'typed_joint_span; no learned weights changed'};dump(args.out/'run.json',manifest)
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True);model=ToolEncoder(model_path,4)
    checkpoint=torch.load(args.checkpoint,map_location='cpu',weights_only=False);result=model.load_state_dict(checkpoint['trainable_state'],strict=False);assert not result.unexpected_keys;model.eval()
    all_summary={}
    for name,rows in splits.items():
        outputs={False:[],True:[]};start=time.perf_counter()
        with (args.out/(name+'-cache.jsonl')).open('w',encoding='utf-8') as stream:
            for index,row in enumerate(rows):
                cache={'id':row['id'],'tools':[]}
                def predict(tool,key=None,slot=0):
                    question,lower=encoder_text(tool,key,slot);enc=tok(question,row['query'],truncation=False,return_offsets_mapping=True)
                    if len(enc['input_ids'])>256:raise ValueError('encoder input profile')
                    with torch.inference_mode():count,kind,span=model({k:torch.tensor([v]) for k,v in enc.items() if k!='offset_mapping'})
                    return {'count':count[0].tolist(),'kind':kind[0].tolist(),'span':span[0].tolist(),'offsets':enc['offset_mapping'],'sequences':enc.sequence_ids(),'question':question,'lower':lower}
                try:
                    if len(row['tools'])>8:raise ValueError('tool-count profile')
                    total=0
                    for raw_tool in row['tools']:
                        tool=normalize_tool(raw_tool);item={'tool':tool,'count_prediction':predict(tool),'slots':[]};count=max(range(6),key=lambda i:item['count_prediction']['count'][i])
                        if count==5:raise ValueError('call-count overflow')
                        total+=count
                        if total>4:raise ValueError('total-call profile')
                        for slot in range(count):item['slots'].append({key:predict(tool,key,slot) for key in tool['parameters']['properties']})
                        cache['tools'].append(item)
                except Exception as exc:cache['error']=type(exc).__name__+': '+str(exc)
                stream.write(json.dumps(cache)+'\n');stream.flush()
                for constrained in outputs:
                    prediction={'id':row['id'],'correct':False,'valid':False,'accepted':False,'calls':[]}
                    try:
                        if 'error' in cache:raise ValueError(cache['error'])
                        calls=[]
                        for item in cache['tools']:
                            tool=item['tool']
                            for slot in item['slots']:
                                arguments={}
                                for key,p in slot.items():
                                    present,value=decode_argument(p['kind'],p['span'],p['offsets'],p['sequences'],p['lower'],p['question'],row['query'],tool['parameters']['properties'][key],key in tool['parameters'].get('required',[]),constrained)
                                    if present:arguments[key]=value
                                calls.append({'name':tool['name'],'arguments':arguments})
                        validate_calls(calls,row['tools']);prediction.update(calls=calls,valid=True,accepted=bool(calls));prediction['correct']=exact_calls(calls,row['answers'],row['tools'])
                    except Exception as exc:prediction['error']=type(exc).__name__+': '+str(exc)
                    outputs[constrained].append(prediction)
                if (index+1)%8==0:print(json.dumps({'split':name,'completed':index+1,'elapsed_seconds':time.perf_counter()-start}),flush=True)
        summaries={}
        for constrained,results in outputs.items():
            label='typed_joint_span' if constrained else 'legacy_independent_argmax';dump(args.out/(name+'-'+label+'-requests.json'),results)
            summaries[label]={'requests':len(results),'correct':sum(r['correct'] for r in results),'correct_accepted':sum(r['correct'] and r['accepted'] for r in results),'wrong_accepted':sum(r['accepted'] and not r['correct'] for r in results),'accepted':sum(r['accepted'] for r in results),'valid':sum(r['valid'] for r in results)}
        dump(args.out/(name+'-summary.json'),summaries);all_summary[name]=summaries;print(json.dumps({name:summaries}),flush=True)
    manifest.update(stage='complete',summaries=all_summary);dump(args.out/'run.json',manifest)
if __name__=='__main__':main()
