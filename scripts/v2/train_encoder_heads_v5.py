"""Train-only balanced linear heads on cached frozen v4 CLS features."""
import argparse,collections,hashlib,json,random,sys,time,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import torch
from torch import nn
from transformers import AutoTokenizer
from sysone.v2.general_tool_encoder import ToolEncoder,KINDS
from sysone.v2.checkpoint_io import write_checkpoint

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def class_weights(labels,size):
    counts=torch.bincount(torch.tensor(labels),minlength=size).float();positive=counts[counts>0]
    weights=torch.zeros(size)
    if len(positive):weights[counts>0]=(positive.max()/counts[counts>0]).sqrt().clamp(max=4)
    return weights

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--threads',type=int,default=2);ap.add_argument('--records',type=int,default=512);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(args.threads);torch.manual_seed(2026101805)
    parent=ROOT/'build/v2/general-tool-expanded-training-v4/encoder';run=json.loads((parent/'run.json').read_text());rows=json.loads((parent/'training-cases.json').read_text());originals=[r for r in rows if not r['id'].endswith(':deny')][:args.records];chosen={r['id'] for r in originals};chosen|={i+':deny' for i in chosen};chosen&={r['id'] for r in rows}
    jobs=[j for j in json.loads((parent/'training-jobs.json').read_text()) if j['record_id'] in chosen]
    count_labels=[j['count'] for j in jobs if j['task']=='count'];kind_labels=[j['kind'] for j in jobs if j['task']=='argument']
    weights=[class_weights(count_labels,6),class_weights(kind_labels,len(KINDS))]
    sources=[Path(__file__)]+[ROOT/'src/sysone/v2'/name for name in ['general_tool_encoder.py','general_tools.py','checkpoint_io.py']]
    protocol=ROOT/'build/v2/general-tool-parallel-protocol-v5'
    manifest={'stage':'caching','warm_start':str(parent/'best.pt'),'parent_checkpoint_sha256':digest(parent/'best.pt'),'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in sources},'training_jobs_sha256':digest(parent/'training-jobs.json'),'training_cases_sha256':digest(parent/'training-cases.json'),'selection_protocol_sha256':{name:digest(protocol/name) for name in ['manifest.json','selection-cases.json']},'training_record_ids':sorted(chosen),'jobs':len(jobs),'count_histogram':dict(collections.Counter(count_labels)),'kind_histogram':dict(collections.Counter(kind_labels)),'policy':{'trainable':'count and kind linear heads ONLY','frozen':'all BERT and span head','epochs':3,'learning_rate':0.0001,'batch':64,'seed':2026101805,'class_weights':'sqrt(max observed class frequency / class frequency), cap4; zero for absent classes','loss':'mean count/kind task losses, each separately weighted CE','candidate_grid':['parent','epoch1','epoch2','epoch3'],'selection':'reused shared selection40, added exposure declared; legacy decoder; strict higher complete correct,no fewer correct accepted,no worse accepted error,NO increase absolute wrong accepted; ties retain earlier','bfcl_used':False,'audit_used':False},'class_weights':[w.tolist() for w in weights],'execution':'CPU_only','threads':args.threads}
    dump(args.out/'run.json',manifest);dump(args.out/'training-job-ids.json',[j['id'] for j in jobs])
    checkpoint=torch.load(parent/'best.pt',map_location='cpu',weights_only=False);model=ToolEncoder(run['arguments']['model'],4);model.load_state_dict(checkpoint['trainable_state'],strict=False);model.requires_grad_(False);model.eval();tok=AutoTokenizer.from_pretrained(run['arguments']['model'],local_files_only=True)
    count=nn.Linear(768,6);kind=nn.Linear(768,len(KINDS));count.load_state_dict(model.count.state_dict());kind.load_state_dict(model.kind.state_dict())
    features=[];started=time.perf_counter()
    ordered=sorted(jobs,key=lambda j:len(j['tokens']['input_ids']))
    with torch.inference_mode():
        for i in range(0,len(ordered),8):
            batch=ordered[i:i+8];tokens=tok.pad([j['tokens'] for j in batch],padding=True,return_tensors='pt');cls=model.encoder(**tokens).last_hidden_state[:,0,:].clone();features.append(cls)
            if i%256==0:print(json.dumps({'cache_jobs':min(i+8,len(jobs)),'total':len(jobs),'elapsed_seconds':time.perf_counter()-started}),flush=True)
    feature_tensor=torch.cat(features).clone();del model,features,tok;gc.collect()
    # Inference-mode tensors must be materialized outside inference mode for head gradients.
    feature_tensor=feature_tensor.clone();tasks=torch.tensor([0 if j['task']=='count' else 1 for j in ordered]);labels=torch.tensor([j['count'] if j['task']=='count' else j['kind'] for j in ordered])
    torch.save({'features':feature_tensor,'tasks':tasks,'labels':labels},args.out/'cls-cache.pt')
    manifest.update(stage='heads_training',cache_bytes=feature_tensor.numel()*4,cache_seconds=time.perf_counter()-started);dump(args.out/'run.json',manifest)
    opt=torch.optim.AdamW(list(count.parameters())+list(kind.parameters()),lr=0.0001);updates=0;history=[]
    with (args.out/'training.jsonl').open('w',encoding='utf-8') as stream:
        for epoch in range(3):
            indices=torch.randperm(len(ordered))
            for offset in range(0,len(indices),64):
                selected=indices[offset:offset+64];losses=[];opt.zero_grad(set_to_none=True)
                for task,head in enumerate([count,kind]):
                    sub=selected[tasks[selected]==task]
                    if len(sub):losses.append(nn.functional.cross_entropy(head(feature_tensor[sub]),labels[sub],weight=weights[task]))
                loss=torch.stack(losses).mean()
                if not torch.isfinite(loss):raise ValueError('nonfinite head loss')
                loss.backward();nn.utils.clip_grad_norm_(list(count.parameters())+list(kind.parameters()),1);opt.step();updates+=1
                stream.write(json.dumps({'epoch':epoch+1,'step':updates,'loss':loss.item()})+'\n');stream.flush()
            state=dict(checkpoint['trainable_state'])
            for prefix,head in [('count',count),('kind',kind)]:
                for name,value in head.state_dict().items():state[prefix+'.'+name]=value.detach().clone()
            frozen=[k for k in state if not k.startswith(('count.','kind.'))]
            assert all(torch.equal(state[k],checkpoint['trainable_state'][k]) for k in frozen)
            assert all(torch.isfinite(v).all() for v in state.values())
            path=args.out/f'epoch-{epoch+1}.pt';write_checkpoint({'trainable_state':state,'manifest':manifest,'tag':f'v5-head-epoch{epoch+1}'},path,torch.save);history.append({'epoch':epoch+1,'checkpoint':path.name,'sha256':digest(path),'updates':updates,'all_non_head_tensors_exactly_unchanged':True,'frozen_tensor_names':frozen,'all_saved_tensors_finite':True})
            print(json.dumps(history[-1]),flush=True)
    manifest.update(stage='complete',updates=updates,checkpoints=history);dump(args.out/'run.json',manifest)
if __name__=='__main__':main()
