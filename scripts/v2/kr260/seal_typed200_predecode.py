"""Final preservation and evidence seal for the isolated clamp experiment."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[3]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    docs=ROOT/'docs/research';dest=docs/'2026-10-16-typed200-predecode-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    parent=docs/'2026-10-16-typed200-stage-clamp-validation.json'
    old=json.loads(parent.read_text());preserved={}
    for key in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256'):
        for n,h in old[key].items():assert sha(ROOT/n)==h,n;preserved[n]=h
    preserved[parent.relative_to(ROOT).as_posix()]=sha(parent)
    from create_typed200_predecode_candidate import verify, OUT
    manifest=verify()
    proof=ROOT/'build/v2/typed200-predecode-formal-v3';p=json.loads((proof/'receipt.json').read_text());assert p['passed']
    assert p['sequencer']['passed'] and p['arithmetic']['passed'] and p['engine']['passed']
    for n,h in p['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in p['artifact_sha256'].items():assert sha(proof/n)==h,n
    sim=ROOT/'build/v2/typed200-predecode-integration-v1'
    assert json.loads((sim/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
    assert '5400 golden words, 14 paired completions' in (sim/'run.log').read_text()
    for line in (sim/'source-sha256.txt').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if n.startswith('rtl/v2/'):assert sha(OUT/n[len('rtl/v2/'):])==h,n
    stage=(sim/'stage.txt').read_text().strip()
    manifest_wsl='/mnt/'+str(sim.drive)[0].lower()+str((sim/'source-sha256.txt').resolve())[2:].replace('\\','/')
    rehash=sim/'staged-rehash.log';assert not rehash.exists()
    with rehash.open('w') as log:
        r=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',stage,'--','sha256sum','-c',manifest_wsl],stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0,'Staged inputs changed; preserve failure'
    probe=ROOT/'build/v2/typed200-predecode-ooc-v1';mapped=json.loads((probe/'receipt.json').read_text());assert mapped['passed']
    for n,h in mapped['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in mapped['artifact_sha256'].items():assert sha(probe/n)==h,n
    composition_dir=ROOT/'build/v2/typed200-predecode-composition-v1'
    composition=json.loads((composition_dir/'receipt.json').read_text());assert composition['passed']
    assert composition['proof_sha256']==sha(proof/'receipt.json')
    for n,h in composition['source_sha256'].items():assert sha(ROOT/n)==h,n
    pipeline=ROOT/'build/v2/typed200-predecode-pipeline-v2';done=json.loads((pipeline/'completion.json').read_text());assert done['completed']
    physical=ROOT/'build/v2/typed200-predecode-physical-v1'
    if done['physical_build_admitted']:
        synth=json.loads((physical/'synthesis-review.json').read_text())
        for n,h in synth['evidence_sha256'].items():assert sha(ROOT/n)==h,n
        place=json.loads((physical/'placement-review.json').read_text())
        for n,h in place['evidence_sha256'].items():assert sha(physical/n)==h,n
        if place['route_approved']:
            route=json.loads((physical/'route-review.json').read_text())
            for n,h in route['evidence_sha256'].items():assert sha(physical/n)==h,n
        else:assert not (physical/'route').exists()
    else:assert not physical.exists(),'Probe-held candidate must not start full build'
    inventory=docs/'2026-10-16-typed200-deployment-profile-draft.json'
    draft=json.loads(inventory.read_text());assert not draft['deployment_ready'] and not draft['target_executed']
    for item in draft['artifacts'].values():assert sha(ROOT/item['path'])==item['sha256']
    assert len(draft['unresolved_target_gates'])==13
    assert all(g['status']=='unresolved' and g['evidence'] is None for g in draft['unresolved_target_gates'].values())
    functional=docs/'2026-10-16-typed200-predecode-functional.json'
    f=json.loads(functional.read_text());assert f['actual_staged_inputs_rehashed'] and f['sequencer_and_composition_proved']
    for key in ('preserved_sha256','source_sha256','evidence_sha256'):
        for n,h in f[key].items():assert sha(ROOT/n)==h,n
    sources=[Path(__file__),ROOT/'scripts/v2/check_typed200_predecode_functional.py',ROOT/'scripts/v2/prove_typed200_predecode.py',ROOT/'scripts/v2/review_typed200_predecode_composition.py',
             ROOT/'simulation/v2/run_typed200_predecode.sh',*[q for q in OUT.rglob('*') if q.is_file()],
             *[q for q in (ROOT/'scripts/v2/kr260').glob('*typed200_predecode*') if q.suffix in ('.py','.tcl')]]
    documentation=[docs/'2026-10-16-typed200-predecode.md',docs/'2026-10-16-typed200-mvp-readiness.md',inventory]
    evidence=[functional]
    for folder in (proof,sim,probe,pipeline,composition_dir):evidence.extend(q for q in folder.rglob('*') if q.is_file() and '.Xil' not in q.parts)
    if physical.exists():
        evidence.extend(q for q in physical.iterdir() if q.is_file())
        for sub in ('place','placement-audit','route'):
            evidence.extend(q for q in (physical/sub).glob('*') if q.is_file())
    history=[q for i in (1,2) for q in (ROOT/f'build/v2/typed200-predecode-formal-v{i}').glob('*') if q.is_file()]
    history.extend(q for q in (ROOT/'build/v2/typed200-predecode-pipeline-v1').glob('*') if q.is_file())
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),'all_preserved_files_unchanged':True,
        'preserved_unique_files':len(preserved),'preserved_sha256':preserved,
        'source_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in sources},
        'documentation_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in documentation},
        'evidence_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in evidence},
        'historical_evidence_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in history},
        'sequencer_cache_stability_and_history_proved':True,'whole_domain_arithmetic_proved':True,'full_engine_equivalence_points':p['engine']['equivalence_points'],
        'golden_words':5400,'paired_completions':14,'staged_inputs_rehashed':True,
        'mapped_results':mapped['results'],'pipeline_result':done,'deployment_profile_ready':False,
        'target_executed':False,'hardware_qualified':False,'wcet_certified':False,'package_or_deployment_approved':False}
    with dest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS',len(preserved),'preserved paths; full clamp experiment and draft profile bound')

if __name__=='__main__':main()
