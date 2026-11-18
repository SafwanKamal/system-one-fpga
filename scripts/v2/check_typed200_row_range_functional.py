"""Freeze row-range functional evidence after verifying inherited preservation."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
from create_typed200_row_range_candidate import OUT,verify as candidate_verify
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
DEST=ROOT/'docs/research/2026-10-16-typed200-row-range-functional.json'
def check_maps(r,keys):
    for k in keys:
        for n,h in r[k].items():assert sha(ROOT/n)==h,n
def verify():
    r=json.loads(DEST.read_text());check_maps(r,('preserved_sha256','source_sha256','evidence_sha256'));return r
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:verify();print('PASS row-range functional seal unchanged');return
    assert not DEST.exists();candidate_verify()
    parent=ROOT/'docs/research/2026-10-16-typed200-predecode-validation.json';p=json.loads(parent.read_text());preserved={}
    for key in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256'):
        for n,h in p[key].items():assert sha(ROOT/n)==h,n;preserved[n]=h
    preserved[parent.relative_to(ROOT).as_posix()]=sha(parent)
    evidence=[]
    for name in ('typed200-row-range-arithmetic-v2','typed200-row-range-endpoint-formal-v1','typed200-row-range-ooc-v1'):
        b=ROOT/'build/v2'/name;r=json.loads((b/'receipt.json').read_text());assert r['passed']
        for n,h in r['source_sha256'].items():assert sha(ROOT/n)==h,n
        for n,h in r['artifact_sha256'].items():assert sha(b/n)==h,n
        evidence.extend(q for q in b.rglob('*') if q.is_file() and '.Xil' not in q.parts)
    sim=ROOT/'build/v2/typed200-row-range-integration-v1'
    assert json.loads((sim/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
    assert '5400 golden words, 14 paired completions' in (sim/'run.log').read_text()
    for line in (sim/'source-sha256.txt').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if n.startswith('rtl/v2/'):assert sha(OUT/n[len('rtl/v2/'):])==h,n
    stage=(sim/'stage.txt').read_text().strip();manifest='/mnt/'+sim.drive[0].lower()+str((sim/'source-sha256.txt').resolve())[2:].replace('\\','/')
    rehash=sim/'functional-staged-rehash.log';assert not rehash.exists()
    with rehash.open('w') as log:r=subprocess.run(['wsl','-d','Ubuntu-24.04','--cd',stage,'--','sha256sum','-c',manifest],stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0
    evidence.extend(q for q in sim.rglob('*') if q.is_file())
    sources=[Path(__file__),ROOT/'scripts/v2/kr260/create_typed200_row_range_candidate.py',
        ROOT/'scripts/v2/prove_typed200_row_range.py',ROOT/'scripts/v2/prove_typed200_row_range_endpoint.py',
        ROOT/'simulation/v2/run_typed200_row_range.sh',ROOT/'scripts/v2/kr260/check_typed200_row_range_ooc.py',
        *[q for q in OUT.rglob('*') if q.is_file()]]
    result={'passed':True,'preserved_unique_files':len(preserved),'preserved_sha256':preserved,
        'source_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in sources},
        'evidence_sha256':{q.relative_to(ROOT).as_posix():sha(q) for q in evidence},
        'all_raw_inputs_proved':True,'full_endpoint_sequential_equivalence_proved':True,
        'golden_words':5400,'paired_completions':14,'actual_staged_inputs_rehashed':True,
        'hardware_qualified':False,'wcet_certified':False}
    with DEST.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS functional freeze;',len(preserved),'prior unique files preserved')
if __name__=='__main__':main()
