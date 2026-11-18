"""Freeze actual functional inputs and results before physical conclusions."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'docs/research/2026-10-15-typed200-profile-cache-functional.json'
    assert not out.exists(),'Preserve completed functional evidence'
    prior=ROOT/'docs/research/2026-10-15-typed200-timed-validation.json'
    old=json.loads(prior.read_text());preserved={}
    for key in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256'):
        for p,h in old[key].items():assert sha(ROOT/p)==h,p;preserved[p]=h
    sim=ROOT/'build/v2/typed200-profile-cache-integration-v1'
    assert json.loads((sim/'completion-status.json').read_text())=={'exit_code':0,'complete':True}
    log=(sim/'run.log').read_text();assert '5400 golden words, 14 paired completions' in log
    cases=re.findall(r'MATCH case (\d+) T(\d+):.*?counts (\d+)/(\d+); publication age (\d+)',log)
    assert [int(c[1]) for c in cases]==[1,2,3,4,5,12,64,128]
    formal=ROOT/'build/v2/typed200-profile-cache-formal-v3'
    receipt=json.loads((formal/'receipt.json').read_text());assert receipt['passed']
    for n,h in receipt['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in receipt['artifact_sha256'].items():assert sha(formal/n)==h,n
    stage=(sim/'stage.txt').read_text().strip();assert re.fullmatch(r'/var/tmp/sysone-typed200\.[A-Za-z0-9]+',stage)
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    command=['wsl','-d','Ubuntu-24.04','--cd',stage,'--','sha256sum','-c',
        wslroot+'/'+(sim/'source-sha256.txt').relative_to(ROOT).as_posix()]
    r=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (sim/'staged-rehash-v2.log').write_bytes(r.stdout);assert r.returncode==0
    candidate=ROOT/'rtl/v2/candidates/typed200_profile_cache'
    for line in (sim/'source-sha256.txt').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if n.startswith('rtl/v2/'):assert sha(candidate/n[7:])==h,n
    sources=[p for p in candidate.rglob('*') if p.is_file()]
    sources += [Path(__file__),ROOT/'scripts/v2/kr260/create_typed200_profile_cache_candidate.py',
        ROOT/'scripts/v2/prove_typed200_profile_cache.py',ROOT/'simulation/v2/run_typed200_profile_cache.sh']
    files=[p for p in formal.iterdir() if p.is_file()]+[p for p in sim.iterdir() if p.is_file()]
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Full endpoint sequential proof and full-model differential regression, no physical/hardware/WCET claim',
        'prior_seal_sha256':sha(prior),'preserved_unique_files':len(preserved),'all_preserved_files_unchanged':True,
        'preserved_sha256':preserved,'endpoint_sequential_equivalence':True,'digest_bits_checked':256,
        'byte_invariants':32,'golden_words':5400,'paired_completions':14,
        'every_cycle_raw_counts_axi_outputs_match':True,'actual_staged_inputs_rehashed':True,
        'stage_rehash_command':command,
        'normal_cases':[dict(zip(('case','tokens','encoder_cycles','request_cycles','emulated_publication_age'),map(int,c))) for c in cases],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in files},
        'target_executed':False,'wcet_certified':False}
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(f'PASS full endpoint proof,5400words/14completions, actual staged rehash; {len(preserved)} preserved paths unchanged')
if __name__=='__main__':main()
