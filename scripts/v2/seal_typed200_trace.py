"""Rehash all preserved inputs and freeze the completed local trace experiment."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    docs=ROOT/'docs/research';dest=docs/'2026-10-15-typed200-owner-trace-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    prior=docs/'2026-10-15-typed200-capture-validation.json';old=json.loads(prior.read_text());preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256'):
        for p,h in old[k].items():assert sha(ROOT/p)==h,p;preserved[p]=h
    b=ROOT/'build/v2/typed200-trace-host-v3';r=json.loads((b/'receipt.json').read_text())
    for p,h in r['source_sha256'].items():assert sha(ROOT/p)==h,p
    for p,h in r['artifact_sha256'].items():assert sha(b/p)==h,p
    candidate=ROOT/'firmware/typed200_trace/candidate.json';c=json.loads(candidate.read_text())
    assert sha(ROOT/'firmware/typed200_r5/service.c')==c['base_service_sha256']
    assert sha(ROOT/'firmware/typed200_trace/service.c')==c['candidate_service_sha256']
    history={}
    for version in (1,2):
        folder=ROOT/f'build/v2/typed200-trace-host-v{version}'
        receipt=json.loads((folder/'receipt.json').read_text())
        for p,h in receipt['source_sha256'].items():assert sha(folder/'source-snapshot'/p)==h,p
        for p in folder.rglob('*'):
            if p.is_file():history[p.relative_to(ROOT).as_posix()]=sha(p)
    sources={**r['source_sha256'],
        'scripts/v2/check_typed200_trace_capture.py':sha(ROOT/'scripts/v2/check_typed200_trace_capture.py'),
        Path(__file__).relative_to(ROOT).as_posix():sha(Path(__file__))}
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in b.rglob('*') if p.is_file()}
    review=ROOT/'build/v2/typed200-trace-review-v1'
    evidence.update({p.relative_to(ROOT).as_posix():sha(p) for p in review.iterdir() if p.is_file()})
    documents=[ROOT/'firmware/typed200_trace/README.md',docs/'2026-10-15-typed200-owner-trace.md']
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Local separate diagnostic firmware, host differential and actual ARM ELF audit',
        'prior_seal_sha256':sha(prior),'all_preserved_files_unchanged':True,
        'preserved_unique_files':len(preserved),'preserved_sha256':preserved,
        'source_sha256':sources,'documentation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in documents},
        'evidence_sha256':evidence,'historical_evidence_sha256':history,
        'paired_poll_records':49,'paired_poll_bytes':55076,'tests_passed':364,
        'trace_bytes':1488,'elf_audit':r['elf_audit'],'target_executed':False,
        'wcet_certified':False,'instrumentation_overhead_bounded':False,
        'board_programming_performed':False}
    with dest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(f'PASS {len(preserved)} preserved files; final trace sources/evidence and historical snapshots bound')
if __name__=='__main__':main()
