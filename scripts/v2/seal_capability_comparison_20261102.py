"""Verify the completed finite campaign and preserve a compact research receipt."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from audit_capability_gguf_20261102 import audit

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'build/v2/model-capability-20261102-r3'
REASON=ROOT/'build/v2/model-capability-20261102-reasoning'
OUT=ROOT/'docs/research/model-capability-2026-11-02'

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    if not (MAIN/'pipeline-complete.json').exists():raise RuntimeError('Inference campaign is not complete')
    if not (REASON/'complete.json').exists():raise RuntimeError('Reasoning ablation incomplete')
    spec=importlib.util.spec_from_file_location('report',ROOT/'scripts/v2/report_capability_comparison_20261102.py')
    report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
    works=[MAIN,ROOT/'build/v2/model-capability-20261102-boundary',ROOT/'build/v2/model-capability-20261102-adapted-controls',REASON/'off',REASON/'on']
    if load(REASON/'complete.json')['promoted']:works.append(REASON/'promoted')
    checks=[];models={};verified=0;repeats=[]
    OUT.mkdir(parents=True,exist_ok=True)
    adapted=ROOT/'build/v2/model-capability-20261102-adapted-controls'
    receipt=load(adapted/'export-receipt.json')
    parent=ROOT/'build/v2/maintenance-sft-v3'
    parent_digest=sha(parent/'qwen/checkpoint.pt')
    if parent_digest!=receipt['checkpoint_sha256'] or load(parent/'final-seal.json')['files_sha256']['qwen/checkpoint.pt']!=parent_digest:raise RuntimeError('Historical adapted checkpoint changed')
    for name,wanted in receipt['base_safetensors'].items():
        if sha(ROOT/'models/Qwen3-0.6B-HF'/name)!=wanted:raise RuntimeError('Historical base weights changed')
    checker=ROOT/'build/v2/general-tool-data-v1/bfcl-python-checker'
    frozen_checker=MAIN/'dependencies/bfcl-python-checker'
    for p in frozen_checker.rglob('*.py'):
        actual=checker/p.relative_to(frozen_checker)
        if not actual.exists() or sha(actual)!=sha(p):raise RuntimeError('Upstream checker changed since snapshot')
    for work in works:
        report.report(work)
        data={c['id']:c for c in rows(work/'evaluation.jsonl')}
        if len(data)!=396:raise RuntimeError('Evaluation cardinality changed')
        screen=load(work/'screen-ids.json')
        if len(screen)!=len(set(screen)):raise RuntimeError('Duplicate registered IDs')
        protocol=load(work/'protocol.json')
        if sha(ROOT/'build/v2/model-capability-runtime-vulkan-b11540/bin/llama-server.exe')!=protocol['server_sha256']:raise RuntimeError('Runtime differs from registered protocol')
        for name,wanted in protocol['files'].items():
            if sha(work/name)!=wanted:raise RuntimeError('Frozen data changed: '+str(work/name))
        for model in load(work/'models.json'):
            models[model['path']]=model
            folder=work/'runs'/model['key']
            for stage in ['screen','confirm']:
                if not (folder/(stage+'-complete.json')).exists():continue
                result=sum([rows(folder/(stage+'-'+d+'.jsonl')) for d in ['maintenance','general','episode']],[])
                ids=[r['id'] for r in result];expected=set(screen if stage=='screen' else data)
                if len(ids)!=len(set(ids)) or set(ids)!=expected:raise RuntimeError('Dropped/duplicated stage cases')
                if any(r['context_limit']!=protocol['primary_context'] or r['output_budget']!=protocol['output_tokens'] for r in result):raise RuntimeError('Profile mismatch')
                checks.append(dict(work=str(work.relative_to(ROOT)),model=model['key'],stage=stage,n=len(ids),ids_match=True))
            if (folder/'confirm-complete.json').exists():
                def read_stage(stage):return {r['id']:r for d in ['maintenance','general','episode'] for r in rows(folder/(stage+'-'+d+'.jsonl'))}
                a,b=read_stage('screen'),read_stage('confirm')
                same_prompts=sum(a[k]['prompt_ids']==b[k]['prompt_ids'] for k in a)
                if same_prompts!=len(a):raise RuntimeError('Repeated screen first prompts differ')
                repeats.append(dict(model=model['key'],n=len(a),identical_first_prompts=same_prompts,
                    identical_first_outputs=sum(a[k].get('decoded_output',a[k]['raw'])==b[k].get('decoded_output',b[k]['raw']) for k in a),
                    identical_correctness=sum(a[k]['correct']==b[k]['correct'] for k in a),
                    correctness_flips=[dict(id=k,screen=a[k]['correct'],confirm=b[k]['correct']) for k in a if a[k]['correct']!=b[k]['correct']]))
        result=load(work/'independent-rescore.json');verified+=result['verified_records']
        target=OUT/work.name if work not in [REASON/'off',REASON/'on',REASON/'promoted'] else OUT/('reasoning-'+work.name)
        for name in ['RESULTS.md','independent-rescore.json','models.json','protocol.json','screen-comparison.json','memory-envelope.json','promotion-decision.json']:
            if (work/name).exists():
                target.mkdir(parents=True,exist_ok=True);shutil.copyfile(work/name,target/name)
    precision=[]
    for key in load(MAIN/'pipeline-complete.json')['finalists']:
        plan=load(MAIN/'precision-plan.json')
        for model in plan['candidates']:
            if model['base_key']==key:models[model['path']]=model
        pair={}
        for label in ['q4','q8']:
            records=rows(MAIN/'precision'/key/label/'predictions.jsonl')
            if len(records)!=32 or {r['id'] for r in records}!=set(plan['ids']):raise RuntimeError('Precision case mismatch')
            pair[label]={r['id']:r for r in records}
            for row in records:
                c=data[row['id']];_,correct,_=report.audit_row(c,row,row['route'])
                if c['domain']=='episode':
                    _,second,_=report.audit_row(c,row['second_turn'],row['route'],True);correct &= second
                if bool(row['correct'])!=correct:raise RuntimeError('Precision rescore disagreement')
                verified+=1
        for cid in pair['q4']:
            a,b=pair['q4'][cid],pair['q8'][cid]
            if a['prompt_ids']!=b['prompt_ids']:raise RuntimeError('Precision prompts differ')
            if a['domain']=='episode' and a['second_turn']['prompt_ids']!=b['second_turn']['prompt_ids']:
                # Histories can legitimately differ when first-turn model outputs differ.
                checks.append(dict(model=key,id=cid,note='Second-turn precision prompts differ because generated histories differ'))
        comparison=load(MAIN/'precision'/key/'comparison.json');precision.append(dict(model=key,**comparison))
        retry=load(MAIN/'runs'/key/'context4096-summary.json')
        if retry['cases']:
            records=rows(MAIN/'runs'/key/'context4096-predictions.jsonl')
            if len(records)!=retry['cases'] or len({r['id'] for r in records})!=len(records):raise RuntimeError('Context retry cardinality mismatch')
            for row in records:
                if row['context_limit']!=4096 or row['output_budget']!=256:raise RuntimeError('Context retry profile mismatch')
                _,correct,_=report.audit_row(data[row['id']],row,row['route'])
                if bool(row['correct'])!=correct:raise RuntimeError('Context retry rescore disagreement')
                verified+=1
    dump(OUT/'precision-comparison.json',precision)
    dump(OUT/'repeated-screen-comparison.json',repeats)
    shutil.copyfile(REASON/'comparison.json',OUT/'reasoning-comparison.json')
    shutil.copyfile(REASON/'registration.json',OUT/'reasoning-registration.json')
    shutil.copyfile(REASON/'mode-guidance-review.json',OUT/'mode-guidance-review.json')
    weight_checks=[]
    for path,model in models.items():
        p=Path(path)
        if p.stat().st_size!=model['bytes'] or sha(p)!=model['sha256']:raise RuntimeError('Weight digest mismatch '+path)
        weight_checks.append(dict(path=path,bytes=model['bytes'],sha256=model['sha256']))
        dump(OUT/'gguf-audits'/(model['key']+'.json'),audit(p))
    runtime=ROOT/'build/v2/model-capability-runtime-vulkan-b11540/bin'
    shutil.copyfile(runtime.parent/'receipt.json',OUT/'runtime-release-receipt.json')
    device=subprocess.run([str(runtime/'llama-server.exe'),'--list-devices'],capture_output=True,text=True,check=True)
    dump(OUT/'runtime.json',dict(device_stdout=device.stdout,device_stderr=device.stderr,
        binaries=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(runtime.iterdir()) if p.suffix in ['.exe','.dll']]))
    test=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_capability_comparison_20261102.py'],capture_output=True,text=True,cwd=ROOT)
    if test.returncode:raise RuntimeError(test.stdout+test.stderr)
    dump(OUT/'verification.json',dict(stages=checks,records_rescored=verified,scorer_disagreements=0,
        weights=weight_checks,tests=test.stdout,qualification=load(MAIN/'parent-gold-fixture-qualification.json'),
        historical_checkpoint_sha256=parent_digest,historical_base_weights_unchanged=True,
        caveat='Separate execution of the same pinned scorers; not independent labels or a blinded reliability study.'))
    subprocess.run([sys.executable,str(ROOT/'scripts/v2/synthesize_capability_comparison_20261102.py')],check=True,cwd=ROOT)
    evidence=[]
    for work in works+[ROOT/'build/v2/model-capability-20261102',ROOT/'build/v2/model-capability-20261102-r2']:
        for p in sorted(work.rglob('*')):
            if p.is_file() and p.suffix not in ['.pyc']:
                evidence.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)))
    evidence += [dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(REASON.iterdir()) if p.is_file()]
    source=[ROOT/'scripts/v2'/name for name in ['capability_comparison_20261102.py','report_capability_comparison_20261102.py','reasoning_capability_20261102.py','seal_capability_comparison_20261102.py','replay_capability_tokens_20261102.py','export_capability_adapted_control_20261102.py','finish_capability_campaign_20261102.py','audit_capability_gguf_20261102.py']]
    source+=[ROOT/'tests/test_capability_comparison_20261102.py']
    source+=list((ROOT/'src/sysone/v2/maintenance').glob('*.py'))
    source+=[ROOT/'src/sysone/v2/general_tool_eval.py']
    source+=[ROOT/'scripts/v2/synthesize_capability_comparison_20261102.py',ROOT/'docs/research/2026-11-02-quantized-model-capability-comparison.md']
    source+=list(checker.rglob('*.py'))
    evidence += [dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in source]
    dump(OUT/'evidence-manifest.json',evidence)
    dump(OUT/'final-seal.json',dict(status='Completed software capability campaign; no hardware qualification',
        files=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='final-seal.json']))
    print(json.dumps(dict(verified=verified,weights=len(weight_checks),evidence_files=len(evidence),out=str(OUT))))

if __name__=='__main__':main()
