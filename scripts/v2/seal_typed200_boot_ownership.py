"""Seal boot-profile review and prospective qualification procedure; no target work."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-boot-ownership-review-v1'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-boot-ownership-validation.json'
    assert not dest.exists()
    receipt=json.loads((OUT/'review-receipt.json').read_text())
    for field in ('preserved_sha256','source_sha256','evidence_sha256'):
        for p,h in receipt[field].items():assert sha(ROOT/p)==h,p
    profile=ROOT/'docs/research/2026-10-16-typed200-target-qualification-profile.json'
    assert sha(profile)==receipt['profile_sha256']
    refs=json.loads((OUT/'primary-sources.json').read_text())
    assert len(refs)==24
    for p,r in refs.items():assert sha(ROOT/p)==sha(Path(r['original']))==r['sha256']
    assert '510 passed' in (OUT/'pytest.log').read_text()
    assessment=json.loads((OUT/'preparation-assessment.json').read_text())
    assert not any(assessment[k] for k in ['artifact_review_complete','functional_receipts_complete','timing_receipts_complete','hardware_action_authorized','target_execution_verified','wcet_certified'])
    assert len([x for x in assessment['missing_or_invalid'] if x.startswith('artifact:')])==8
    mapping=json.loads((OUT/'memory-map-review.json').read_text())
    assert len(mapping['overlaps'])==2 and not mapping['ordinary_direct_fsbl_load_allowed']
    source=dict(receipt['source_sha256']);source[Path(__file__).relative_to(ROOT).as_posix()]=sha(Path(__file__))
    docs={p.relative_to(ROOT).as_posix():sha(p) for p in [profile,
        ROOT/'docs/research/2026-10-16-typed200-boot-ownership-review.md',
        ROOT/'docs/research/2026-10-16-typed200-target-qualification-procedure.md']}
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
    result={'review_complete':True,'qualification_procedure_prepared':True,
        'deployment_ready':False,'target_contacted':False,'target_executed':False,
        'boot_image_created':False,'bitstream_created':False,'wcet_certified':False,
        'pytest_passed':510,'primary_sources_pinned':24,'runtime_rules_exported':20,
        'runtime_bits_checked':131,'missing_boot_artifact_roles':8,
        'prior_preserved_unique_files':len(receipt['preserved_sha256']),
        'preserved_sha256':receipt['preserved_sha256'],'source_sha256':source,
        'documentation_sha256':docs,'evidence_sha256':evidence}
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS sealed ownership review/qualification plan, 24 pinned primary sources, 510 tests, prior baseline/seals unchanged; deployment remains blocked')
if __name__=='__main__':main()
