"""Finite head-grid selection or frozen paired audit in one BERT process."""
import argparse,gc,hashlib,json,sys,time
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
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cases',type=Path,required=True);ap.add_argument('--head-root',type=Path,required=True);ap.add_argument('--epochs',type=int,nargs='*',default=[1,2,3]);ap.add_argument('--threads',type=int,default=2);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(args.threads)
    parent=ROOT/'build/v2/general-tool-expanded-training-v4/encoder';run=json.loads((parent/'run.json').read_text());rows=adapt_records(json.loads(args.cases.read_text(encoding='utf-8')));dump(args.out/'cases.json',rows)
    paths={'parent':parent/'best.pt',**{f'epoch{n}':args.head_root/f'epoch-{n}.pt' for n in args.epochs}}
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/name for name in ['general_encoder_decode_v5.py','general_tool_encoder.py','general_training_v2.py','general_schema_annotations.py','general_tools.py','general_call_matching.py']]
    manifest={'stage':'running','candidate_grid':list(paths),'checkpoints':{k:{'path':str(p),'sha256':digest(p)} for k,p in paths.items()},'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sources},'cases_sha256':digest(args.cases),'cases_path':str(args.cases),'protocol_manifest_sha256':digest(args.cases.parent/'manifest.json'),'execution':'CPU_only','threads':args.threads,'decoder':'legacy_independent_argmax','warm_start':True,'reused_selection40_for_additional_model_choice':args.cases.name=='selection-cases.json','bfcl_used_for_selection':False,'audit_used_for_training':False};dump(args.out/'run.json',manifest)
    tok=AutoTokenizer.from_pretrained(run['arguments']['model'],local_files_only=True);model=ToolEncoder(run['arguments']['model'],4);parent_state=torch.load(paths['parent'],map_location='cpu',weights_only=False)['trainable_state'];model.load_state_dict(parent_state,strict=False);model.eval()
    all_results={}
    for tag,path in paths.items():
        state=torch.load(path,map_location='cpu',weights_only=False)['trainable_state'];assert set(state)==set(parent_state)
        assert all(torch.equal(v,parent_state[k]) for k,v in state.items() if not k.startswith(('count.','kind.')))
        model.load_state_dict(state,strict=False);del state;gc.collect();results=[];start=time.perf_counter()
        with (args.out/(tag+'-requests.jsonl')).open('w',encoding='utf-8') as stream:
            for index,row in enumerate(rows):
                prediction={'id':row['id'],'correct':False,'valid':False,'accepted':False,'calls':[],'gold_valid':True}
                try:validate_calls(row['answers'],row['tools'])
                except (ValueError,TypeError,KeyError) as exc:prediction.update(gold_valid=False,gold_error=type(exc).__name__+': '+str(exc))
                try:
                    if len(row['tools'])>8:raise ValueError('tool-count profile')
                    def predict(tool,key=None,slot=0):
                        question,lower=encoder_text(tool,key,slot);enc=tok(question,row['query'],truncation=False,return_offsets_mapping=True)
                        if len(enc['input_ids'])>256:raise ValueError('encoder input profile')
                        with torch.inference_mode():count,kind,span=model({k:torch.tensor([v]) for k,v in enc.items() if k!='offset_mapping'})
                        return enc,count[0],kind[0].tolist(),span[0].tolist(),question,lower
                    calls=[]
                    for raw_tool in row['tools']:
                        tool=normalize_tool(raw_tool);_,count,*_=predict(tool);count=int(count.argmax())
                        if count==5:raise ValueError('call-count overflow')
                        for slot in range(count):
                            if len(calls)>=4:raise ValueError('total-call profile')
                            arguments={}
                            for key,spec in tool['parameters']['properties'].items():
                                enc,_,kinds,spans,question,lower=predict(tool,key,slot)
                                present,value=decode_argument(kinds,spans,enc['offset_mapping'],enc.sequence_ids(),lower,question,row['query'],spec,key in tool['parameters'].get('required',[]),False)
                                if present:arguments[key]=value
                            calls.append({'name':tool['name'],'arguments':arguments})
                    validate_calls(calls,row['tools']);prediction.update(calls=calls,valid=True,accepted=bool(calls));prediction['correct']=prediction['gold_valid'] and exact_calls(calls,row['answers'],row['tools'])
                except (ValueError,TypeError,KeyError) as exc:prediction['error']=type(exc).__name__+': '+str(exc)
                results.append(prediction);stream.write(json.dumps(prediction)+'\n');stream.flush()
                if (index+1)%8==0:print(json.dumps({'tag':tag,'completed':index+1,'elapsed_seconds':time.perf_counter()-start}),flush=True)
        summary={'requests':len(results),'correct':sum(r['correct'] for r in results),'correct_accepted':sum(r['correct'] and r['accepted'] for r in results),'wrong_accepted':sum(r['accepted'] and not r['correct'] for r in results),'accepted':sum(r['accepted'] for r in results),'valid':sum(r['valid'] for r in results),'gold_errors':sum(not r['gold_valid'] for r in results)}
        all_results[tag]=summary;dump(args.out/(tag+'-summary.json'),summary);print(json.dumps({tag:summary}),flush=True)
    manifest.update(stage='complete',summaries=all_results);dump(args.out/'run.json',manifest);dump(args.out/'summaries.json',all_results)
if __name__=='__main__':main()
