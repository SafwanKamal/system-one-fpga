"""Preserve prior baselines and bind the finished full cache physical experiment."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    docs=ROOT/'docs/research';dest=docs/'2026-10-16-typed200-profile-cache-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    functional=docs/'2026-10-15-typed200-profile-cache-functional.json'
    f=json.loads(functional.read_text());preserved={}
    for key in ('preserved_sha256','source_sha256','evidence_sha256'):
        for n,h in f[key].items():assert sha(ROOT/n)==h,n;preserved[n]=h
    assert f['endpoint_sequential_equivalence'] and f['actual_staged_inputs_rehashed']
    b=ROOT/'build/v2/typed200-profile-cache-physical-v1'
    synth=json.loads((b/'synthesis-review.json').read_text())
    for n,h in synth['evidence_sha256'].items():assert sha(ROOT/n)==h,n
    place=json.loads((b/'placement-review.json').read_text())
    for n,h in place['evidence_sha256'].items():assert sha(b/n)==h,n
    route=None
    if place['route_approved']:
        assert place['setup_ns']>=0.5
        route=json.loads((b/'route-review.json').read_text())
        for n,h in route['evidence_sha256'].items():assert sha(b/n)==h,n
    else:
        assert not (b/'route').exists(),'Do not route a rejected checkpoint'
    sources=[Path(__file__),ROOT/'scripts/v2/kr260/prepare_typed200_profile_cache_flow.py',
        ROOT/'scripts/v2/kr260/run_typed200_profile_cache_pipeline.py',
        ROOT/'scripts/v2/kr260/build_typed200_profile_cache_physical.py',
        ROOT/'scripts/v2/kr260/review_typed200_cache_synthesis.py',
        ROOT/'scripts/v2/kr260/review_typed200_cache_placement.py',
        ROOT/'scripts/v2/kr260/review_typed200_cache_route.py',
        ROOT/'scripts/v2/kr260/audit_typed200_cache_placement.tcl']
    report=docs/'2026-10-15-typed200-profile-cache.md'
    files=[functional,b/'synthesis-review.json',b/'placement-review.json',
        b/'input-proof.json',b/'synth-status.json',b/'place-status.json',
        b/'synthesized.dcp',b/'synthesis-utilization.rpt',b/'synthesis-critical.rpt',
        b/'synthesis-timing.rpt',b/'place/placed.dcp',
        *[p for p in (b/'place').iterdir() if p.suffix in ('.rpt','.json','.txt')],
        *[p for p in (b/'placement-audit').iterdir() if p.is_file()]]
    pipeline=ROOT/'build/v2/typed200-profile-cache-pipeline-v1'
    assert json.loads((pipeline/'completion.json').read_text())['completed']
    files.extend(p for p in pipeline.iterdir() if p.is_file())
    if route is not None:
        files.extend([b/'route-review.json',*[p for p in (b/'route').iterdir() if p.is_file()]])
    history={}
    for version in (1,2):
        folder=ROOT/f'build/v2/typed200-profile-cache-formal-v{version}'
        for p in folder.iterdir():
            if p.is_file():history[p.relative_to(ROOT).as_posix()]=sha(p)
    p=ROOT/'build/v2/profile-cache-initial-crlf-script.sh';history[p.relative_to(ROOT).as_posix()]=sha(p)
    r={'verified_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Full profile-cache endpoint proof, full numerical differential regression and completed local physical experiment',
        'all_preserved_files_unchanged':True,'preserved_unique_files':len(preserved),
        'functional_evidence_sha256':sha(functional),'preserved_sha256':preserved,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'documentation_sha256':{report.relative_to(ROOT).as_posix():sha(report)},
        'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in files},
        'historical_evidence_sha256':history,'synthesis':synth,'placement':place,'route':route,
        'golden_words':5400,'paired_completions':14,'endpoint_sequential_equivalence':True,
        'target_executed':False,'hardware_qualified':False,'wcet_certified':False,
        'package_or_deployment_approved':False}
    with dest.open('x',encoding='utf-8') as stream:json.dump(r,stream,indent=2);stream.write('\n')
    print(f'PASS {len(preserved)} preserved paths and completed physical evidence bound; no hardware qualification')
if __name__=='__main__':main()
