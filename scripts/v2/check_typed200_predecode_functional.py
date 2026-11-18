"""Freeze completed local functional evidence while the isolated physical flow proceeds."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-predecode-functional.json';assert not dest.exists()
    sim=ROOT/'build/v2/typed200-predecode-integration-v1'
    while not (sim/'completion-status.json').exists():time.sleep(5)
    assert json.loads((sim/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
    assert '5400 golden words, 14 paired completions' in (sim/'run.log').read_text()
    parent=ROOT/'docs/research/2026-10-16-typed200-stage-clamp-validation.json';old=json.loads(parent.read_text());preserved={}
    for key in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256'):
        for n,h in old[key].items():assert sha(ROOT/n)==h,n;preserved[n]=h
    preserved[parent.relative_to(ROOT).as_posix()]=sha(parent)
    candidate=ROOT/'rtl/v2/candidates/typed200_predecode';m=json.loads((candidate/'candidate.json').read_text())
    for n,h in m['candidate_sha256'].items():assert sha(candidate/n)==h,n
    for line in (sim/'source-sha256.txt').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if n.startswith('rtl/v2/'):assert sha(candidate/n[len('rtl/v2/'):])==h,n
    stage=(sim/'stage.txt').read_text().strip();path=sim/'source-sha256.txt'
    wsl='/mnt/'+str(path.drive)[0].lower()+str(path.resolve())[2:].replace('\\','/')
    log=sim/'functional-staged-rehash.log';assert not log.exists()
    with log.open('w') as f:r=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',stage,'--','sha256sum','-c',wsl],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0,'Preserve input-drift failure'
    proof=ROOT/'build/v2/typed200-predecode-formal-v3';p=json.loads((proof/'receipt.json').read_text());assert p['passed']
    for n,h in p['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in p['artifact_sha256'].items():assert sha(proof/n)==h,n
    comp=ROOT/'build/v2/typed200-predecode-composition-v1';c=json.loads((comp/'receipt.json').read_text());assert c['passed']
    for n,h in c['source_sha256'].items():assert sha(ROOT/n)==h,n
    sources=[Path(__file__),ROOT/'scripts/v2/prove_typed200_predecode.py',ROOT/'scripts/v2/review_typed200_predecode_composition.py',
        ROOT/'scripts/v2/kr260/create_typed200_predecode_candidate.py',ROOT/'simulation/v2/run_typed200_predecode.sh',
        *[q for q in candidate.rglob('*') if q.is_file()]]
    evidence=[q for folder in (proof,comp,sim) for q in folder.iterdir() if q.is_file()]
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),'scope':'Actual sequencer/cache/stability and modular engine proof plus complete independent numerical/cycle regression; no physical/WCET qualification',
        'all_preserved_files_unchanged':True,'preserved_unique_files':len(preserved),'preserved_sha256':preserved,
        'source_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in sources},
        'evidence_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in evidence},
        'golden_words':5400,'paired_completions':14,'full_engine_equivalence_points':886,
        'sequencer_and_composition_proved':True,'actual_staged_inputs_rehashed':True,'hardware_qualified':False,'target_executed':False}
    with dest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS full functional seal and',len(preserved),'preserved paths; no target qualification')

if __name__=='__main__':main()
