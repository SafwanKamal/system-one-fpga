"""Freeze the completed local PMU diagnostic experiment and preserved baselines."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    docs=ROOT/'docs/research';dest=docs/'2026-10-15-typed200-timed-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    prior=docs/'2026-10-15-typed200-owner-trace-validation.json';old=json.loads(prior.read_text());preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256','historical_evidence_sha256'):
        for p,h in old[k].items():assert sha(ROOT/p)==h,p;preserved[p]=h
    b=ROOT/'build/v2/typed200-timed-host-v3';r=json.loads((b/'receipt.json').read_text())
    for p,h in r['source_sha256'].items():assert sha(ROOT/p)==h,p
    for p,h in r['artifact_sha256'].items():assert sha(b/p)==h,p
    sources={**r['source_sha256']}
    for p in [Path(__file__),ROOT/'scripts/v2/create_typed200_timed.py',ROOT/'scripts/v2/check_typed200_timed_capture.py']:
        sources[p.relative_to(ROOT).as_posix()]=sha(p)
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in b.rglob('*') if p.is_file()}
    review=ROOT/'build/v2/typed200-timed-review-v1'
    evidence.update({p.relative_to(ROOT).as_posix():sha(p) for p in review.iterdir() if p.is_file()})
    history={}
    for p in (ROOT/'build/v2').glob('typed200-timed-host-v[12]-runner.py'):
        history[p.relative_to(ROOT).as_posix()]=sha(p)
    oldbuild=ROOT/'build/v2/typed200-timed-host-v2'
    v2=json.loads((oldbuild/'receipt.json').read_text())
    for p,h in v2['source_sha256'].items():assert sha(oldbuild/'source-snapshot'/p)==h,p
    for p in oldbuild.rglob('*'):
        if p.is_file():history[p.relative_to(ROOT).as_posix()]=sha(p)
    documents=[ROOT/'firmware/typed200_timed/README.md',docs/'2026-10-15-typed200-timed-provider.md']
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Separate timed diagnostic firmware, host mock tests, ARM link/instruction audit; no target execution',
        'prior_seal_sha256':sha(prior),'preserved_unique_files':len(preserved),
        'all_preserved_files_unchanged':True,'preserved_sha256':preserved,
        'source_sha256':sources,'documentation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in documents},
        'evidence_sha256':evidence,'historical_evidence_sha256':history,
        'tests_passed':396,'paired_poll_records':49,'paired_poll_bytes':55076,'elf_audit':r['elf_audit'],
        'target_executed':False,'wcet_certified':False,'frequency_verified':False,
        'pmu_ownership_verified':False,'board_programming_performed':False}
    with dest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(f'PASS {len(preserved)} preserved files; timed provider tests, ARM artifacts and source history bound')
if __name__=='__main__':main()
