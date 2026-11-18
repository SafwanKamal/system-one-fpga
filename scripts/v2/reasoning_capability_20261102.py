"""Registered bounded reasoning/context/output-budget ablation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'build/v2/model-capability-20261102-r3'
BASE=ROOT/'build/v2/model-capability-20261102-reasoning'
RUNNER=ROOT/'scripts/v2/capability_comparison_20261102.py'
SERVER=ROOT/'build/v2/model-capability-runtime-vulkan-b11540/bin/llama-server.exe'
KEYS=['qwen06-q4','qwen17-q4','qwen35-2-q4','qwen35-4-q4']

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def prepare():
    if (BASE/'registration.json').exists():return
    BASE.mkdir(exist_ok=False)
    registration=dict(reason='User acceptance thresholds remain open. A nonthinking 256-output profile alone cannot establish capability of checkpoints supporting reasoning.',
        candidates=KEYS,context=4096,total_output_budget=1024,includes_reasoning_tokens=True,
        sample='Same prospectively fixed 32 IDs as precision sensitivity. No error-conditioned case selection.',
        paired_modes=['thinking disabled','thinking enabled'],route='Reuse primary development-selected route; no retuning on the ablation outputs.',
        promotion='Among enabled-thinking profiles with more complete correct sample tasks than paired disabled-thinking control, promote highest four-axis balanced score to the same 104-task screen as primary models. Ties follow registered candidate order.',
        data_scope='Exploratory development evidence after initial short-profile results, not a blinded generalization or reliability test.',
        no_new_training=True,no_FPGA_access=True)
    dump(BASE/'registration.json',registration)
    for mode in ['off','on']:
        folder=BASE/mode;folder.mkdir()
        for name in ['development.jsonl','evaluation.jsonl','demonstrations.jsonl','precision-plan.json']:
            shutil.copyfile(MAIN/name,folder/name)
        ids=load(MAIN/'precision-plan.json')['ids'];dump(folder/'screen-ids.json',ids)
        models=[m for m in load(MAIN/'models.json') if m['key'] in KEYS]
        dump(folder/'models.json',models)
        protocol=load(MAIN/'protocol.json')
        protocol.update(candidates=models,primary_context=4096,server_context=16384,screen_records=len(ids),output_tokens=1024,thinking=mode=='on',
            reasoning='Enabled within total output budget' if mode=='on' else 'Disabled within extended output budget',selection=registration['promotion'],reasoning_ablation=registration)
        protocol['files']={name:sha(folder/name) for name in ['development.jsonl','evaluation.jsonl','demonstrations.jsonl','screen-ids.json']}
        dump(folder/'protocol.json',protocol)
    print(json.dumps(registration),flush=True)

def run_command(folder,keys):
    args=[sys.executable,str(RUNNER),'screen','--work',str(folder),'--server',str(SERVER),'--gpu-layers','99',
        '--model',','.join(keys),'--context','4096','--output-budget','1024']
    if folder.name!='off':args.append('--thinking')
    with (BASE/'inference.log').open('ab') as log:subprocess.run(args,check=True,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)

def run():
    prepare()
    for mode in ['off','on']:
        folder=BASE/mode
        for key in KEYS:
            target=folder/'runs'/key/'routes.json'
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copyfile(MAIN/'runs'/key/'routes.json',target)
        print('Reasoning ablation '+mode,flush=True)
        run_command(folder,KEYS)
    comparisons=[]
    for key in KEYS:
        left=load(BASE/'off/runs'/key/'screen-complete.json')['summary']
        right=load(BASE/'on/runs'/key/'screen-complete.json')['summary']
        n=sum(x['count'] for x in right.values())
        off=sum(x['correct'] for x in left.values());on=sum(x['correct'] for x in right.values())
        score=sum(right[k]['correct']/right[k]['count'] for k in ['fresh','conditional','bfcl','two_turn'])/4
        comparisons.append(dict(model=key,n=n,off_correct=off,on_correct=on,balanced=score,off=left,on=right))
    eligible=[x for x in comparisons if x['on_correct']>x['off_correct']]
    promoted=max(eligible,key=lambda x:x['balanced'])['model'] if eligible else None
    dump(BASE/'comparison.json',dict(comparisons=comparisons,promoted=promoted,scope=load(BASE/'registration.json')))
    if promoted:
        print('Promoted reasoning profile '+promoted,flush=True)
        folder=BASE/'promoted'
        if not folder.exists():
            folder.mkdir()
            for name in ['development.jsonl','evaluation.jsonl','demonstrations.jsonl']:
                shutil.copyfile(MAIN/name,folder/name)
            shutil.copyfile(MAIN/'screen-ids.json',folder/'screen-ids.json')
            model=next(m for m in load(MAIN/'models.json') if m['key']==promoted)
            dump(folder/'models.json',[model])
            protocol=load(BASE/'on/protocol.json');protocol['candidates']=[model];protocol['screen_records']=104
            protocol['files']={name:sha(folder/name) for name in ['development.jsonl','evaluation.jsonl','demonstrations.jsonl','screen-ids.json']}
            dump(folder/'protocol.json',protocol)
            target=folder/'runs'/promoted;target.mkdir(parents=True)
            shutil.copyfile(MAIN/'runs'/promoted/'routes.json',target/'routes.json')
        run_command(folder,[promoted])
    dump(BASE/'complete.json',dict(promoted=promoted,status='Bounded ablation and any promoted 104-task screen complete.'))
    print(json.dumps(dict(reasoning_complete=True,promoted=promoted)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run'])
    args=parser.parse_args()
    prepare() if args.command=='prepare' else run()
