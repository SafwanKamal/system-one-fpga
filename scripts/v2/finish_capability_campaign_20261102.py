"""Finish finite registered stages serially after the eight-model screen."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'build/v2/model-capability-20261102-r3'
BOUNDARY=ROOT/'build/v2/model-capability-20261102-boundary'
RUNNER=ROOT/'scripts/v2/capability_comparison_20261102.py'
SERVER=ROOT/'build/v2/model-capability-runtime-vulkan-b11540/bin/llama-server.exe'

def load(path):return json.loads(path.read_text(encoding='utf-8'))

def command(stage,work,models=None):
    args=[sys.executable,str(RUNNER),stage,'--work',str(work),'--server',str(SERVER),'--gpu-layers','99']
    if models:args+=['--model',','.join(models)]
    print(json.dumps(dict(stage=stage,work=work.name,models=models)),flush=True)
    with (MAIN/'pipeline.log').open('ab') as out:
        subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,check=True,cwd=ROOT)

def components(work,key):
    s=load(work/'runs'/key/'screen-complete.json')['summary']
    return {name:s[name]['correct']/s[name]['count'] for name in ['fresh','conditional','bfcl','two_turn']}

def main():
    print('Waiting for registered eight-model screen.',flush=True)
    while len(list((MAIN/'runs').glob('*/screen-complete.json')))<8:
        time.sleep(5)
    command('report-screen',MAIN)
    finalists=load(MAIN/'screen-comparison.json')['finalists']
    if len(finalists)!=2:raise RuntimeError('Finalist rule did not produce two models')
    command('screen',BOUNDARY,['qwen8-q2'])
    b=components(BOUNDARY,'qwen8-q2')
    dominated=[]
    for model in load(MAIN/'models.json'):
        c=components(MAIN,model['key'])
        if all(c[k]>=b[k] for k in b):dominated.append(model['key'])
    promote=not dominated
    decision=dict(boundary_components=b,dominating_smaller_profiles=dominated,promote=promote,
                  rule=load(BOUNDARY/'protocol.json')['selection'])
    (BOUNDARY/'promotion-decision.json').write_text(json.dumps(decision,indent=2))
    controls=ROOT/'build/v2/model-capability-20261102-adapted-controls'
    if not (controls/'preparation-complete.json').exists():raise RuntimeError('Adapted control export must finish first')
    command('screen',controls,['qwen06-sft-q4','qwen06-sft-q8'])
    subprocess.run([sys.executable,str(ROOT/'scripts/v2/report_capability_comparison_20261102.py'),'--work',str(controls)],check=True,cwd=ROOT)
    print('Running registered reasoning-budget ablation.',flush=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/v2/reasoning_capability_20261102.py'),'run'],check=True,cwd=ROOT)
    command('confirm',MAIN,finalists)
    if promote:command('confirm',BOUNDARY,['qwen8-q2'])
    command('precision',MAIN,finalists)
    command('rescue',MAIN,finalists)
    for work in [MAIN,BOUNDARY]:
        subprocess.run([sys.executable,str(ROOT/'scripts/v2/report_capability_comparison_20261102.py'),'--work',str(work)],check=True,cwd=ROOT)
    (MAIN/'pipeline-complete.json').write_text(json.dumps(dict(finalists=finalists,boundary=decision,
        status='Finite stages completed; interpretation and evidence sealing still required.'),indent=2))
    print('Registered inference stages completed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        (MAIN/'pipeline-failure.json').write_text(json.dumps(dict(type=type(exc).__name__,error=str(exc)),indent=2))
        raise
