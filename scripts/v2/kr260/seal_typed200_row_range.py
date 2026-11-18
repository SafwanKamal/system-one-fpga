"""Seal one completed row-range attempt, including rejection and predecessor maps."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/v2'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=('direct','csa'),required=True);a=ap.parse_args()
    suffix='row_range' if a.variant=='direct' else 'row_range_csa';tag=suffix.replace('_','-')
    record=ROOT/f'docs/research/2026-10-16-typed200-{tag}-validation.json';assert not record.exists()
    mod=__import__('check_typed200_'+suffix+'_functional');f=mod.verify()
    pipeline=ROOT/f'build/v2/typed200-{tag}-pipeline-v1';done=json.loads((pipeline/'completion.json').read_text());assert done['completed']
    for cmd in json.loads((pipeline/'commands.json').read_text()):assert cmd['returncode']==0,cmd
    physical=ROOT/f'build/v2/typed200-{tag}-physical-v1'
    if done['physical_build_admitted']:
        synth=json.loads((physical/'synthesis-review.json').read_text())
        for n,h in synth['evidence_sha256'].items():assert sha(ROOT/n)==h,n
        place=json.loads((physical/'placement-review.json').read_text())
        for n,h in place['evidence_sha256'].items():assert sha(physical/n)==h,n
        assert not (physical/'route').exists(),'Routing outside this placement experiment'
    else:assert not physical.exists()
    sim=ROOT/f'build/v2/typed200-{tag}-integration-v1';stage=(sim/'stage.txt').read_text().strip()
    manifest='/mnt/'+sim.drive[0].lower()+str((sim/'source-sha256.txt').resolve())[2:].replace('\\','/')
    rehash=sim/'final-staged-rehash.log';assert not rehash.exists()
    with rehash.open('w') as log:r=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',stage,'--','sha256sum','-c',manifest],stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0
    evidence=[mod.DEST]
    for folder in (pipeline,sim,physical):
        if folder==physical:
            if folder.exists():
                evidence.extend(p for p in folder.iterdir() if p.is_file())
                for sub in ('place','placement-audit'):evidence.extend(p for p in (folder/sub).glob('*') if p.is_file())
        else:evidence.extend(p for p in folder.rglob('*') if p.is_file())
    preserved=dict(f['preserved_sha256'])
    for key in ('source_sha256','evidence_sha256'):
        for n,h in f[key].items():assert sha(ROOT/n)==h,n
    sources=[Path(__file__)]
    for folder in (ROOT/'scripts/v2/kr260',ROOT/'scripts/v2',ROOT/'simulation/v2'):
        for q in folder.glob('*typed200_'+suffix+'*'):
            if a.variant=='direct' and '_row_range_csa' in q.name:continue
            if q.is_file():sources.append(q)
    sources.extend(p for p in (ROOT/'rtl/v2/candidates'/('typed200_'+suffix)).rglob('*') if p.is_file())
    report=ROOT/f'docs/research/2026-10-16-typed200-{tag}.md'
    historical=[]
    if a.variant=='direct':historical.extend(p for p in (ROOT/'build/v2/typed200-row-range-arithmetic-v1').glob('*') if p.is_file())
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),'passed':True,
        'preserved_unique_files':len(preserved),'all_preserved_files_unchanged':True,
        'preserved_sha256':preserved,'source_sha256':{**f['source_sha256'],**{p.relative_to(ROOT).as_posix():sha(p) for p in sources}},
        'documentation_sha256':{report.relative_to(ROOT).as_posix():sha(report)},
        'evidence_sha256':{**f['evidence_sha256'],**{p.relative_to(ROOT).as_posix():sha(p) for p in evidence}},
        'historical_evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in historical},
        'all_raw_inputs_proved':True,'full_endpoint_sequential_equivalence_proved':True,
        'golden_words':5400,'paired_completions':14,'actual_staged_inputs_rehashed':True,
        'pipeline_result':done,'hardware_qualified':False,'wcet_certified':False,
        'package_or_deployment_approved':False,'target_executed':False}
    with record.open('x') as log:json.dump(result,log,indent=2);log.write('\n')
    print('PASS final',tag,'seal;',len(preserved),'prior paths unchanged')
if __name__=='__main__':main()
