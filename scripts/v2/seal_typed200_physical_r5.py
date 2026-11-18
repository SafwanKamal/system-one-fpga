"""Seal isolated physical/R5 evidence after review; preserve all previous seals."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
import create_typed200_candidate as candidate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def check(p,h):assert sha(ROOT/p)==h,p
def main():
    dest=ROOT/'docs/research/2026-10-15-typed200-physical-r5-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    baseline=read('docs/research/2026-10-14-system-one-preservation.json')
    for row in baseline['file_checks']:check(row['path'],row['before_sha256'])
    previous=['docs/research/2026-10-15-'+x+'-validation.json' for x in
              ['typed-intent','typed200','typed200-transport']]
    for fn in previous:
        for key in ['source_sha256','documentation_sha256','evidence_sha256']:
            for p,h in read(fn)[key].items():check(p,h)
    candidate.verify()
    root=Path('build/v2/typed200-physical-v1');p=ROOT/root
    proof=read(root/'input-proof.json')
    check(candidate.OUT.relative_to(ROOT)/'candidate.json',proof['candidate_sha256'])
    check('rtl/platform/typed200/typed200_encoder_wrapper.v',proof['wrapper_sha256'])
    check('scripts/v2/kr260/create_project_kr260.tcl',proof['board_setup_sha256'])
    snapshot={x.relative_to(p/'rtl-snapshot').as_posix():sha(x) for x in (p/'rtl-snapshot').rglob('*') if x.is_file()}
    unused={'platform/kr260/kr260_encoder.sv','platform/kr260/kr260_encoder_wrapper.v'}
    assert set(snapshot)==set(proof['rtl_sha256'])-unused
    for n,h in proof['rtl_sha256'].items():
        check(root/'rtl-input'/n,h)
        if n not in unused:check(root/'rtl-snapshot'/n,h)
        if n!='platform/kr260/typed200_encoder_wrapper.v':check(candidate.OUT.relative_to(ROOT)/n,h)
    for stage in ['synth','place']:assert read(root/f'{stage}-status.json')['exit_code']==0
    review=read(root/'placement-review.json')
    for n,h in review['evidence_sha256'].items():check(root/n,h)
    routed=(p/'route-status.json').exists()
    if review['route_approved']:assert routed and read(root/'route-status.json')['exit_code']==0
    route_review=read(root/'route-review.json') if routed else None
    if route_review:
        for n,h in route_review['evidence_sha256'].items():check(root/n,h)
    firmware=Path('build/v2/typed200-r5-elf-v8');r=read(firmware/'receipt.json')
    assert r['passed'] and not r['target_executed'] and not r['wcet_certified']
    for n,h in r['source_sha256'].items():check(n,h)
    for n,h in r['artifact_sha256'].items():check(firmware/n,h)
    audit=Path('build/v2/typed200-r5-audit-v3');a=read(audit/'audit.json');assert a['passed']
    assert a['elf_sha256']==sha(ROOT/firmware/'typed200-r5.elf')
    docs=[ROOT/'docs/research/2026-10-15-typed200-physical-r5.md',ROOT/'firmware/typed200_r5/README.md']
    for doc in docs:
        for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            if '://' not in link:assert (doc.parent/link.split('#')[0]).resolve().exists(),link
    sources=[x for x in (ROOT/'firmware/typed200_r5').iterdir() if x.suffix in ['.c','.h','.S','.ld']]
    sources += [ROOT/n for n in ['rtl/platform/typed200/typed200_encoder_wrapper.v',
        'scripts/v2/build_typed200_r5_elf.py','scripts/v2/audit_typed200_r5.py',
        'scripts/v2/kr260/build_typed200_physical.py','scripts/v2/kr260/audit_typed200_physical.tcl',
        'scripts/v2/kr260/review_typed200_placement.py',
        'scripts/v2/kr260/review_typed200_route.py',
        'scripts/v2/seal_typed200_physical_r5.py']]
    evidence=[]
    for directory in [ROOT/firmware,ROOT/audit,p,p/'place',p/'placement-audit',*([p/'route'] if routed else [])]:
        evidence += [x for x in directory.iterdir() if x.is_file() and x.suffix in
            ['.json','.rpt','.txt','.tcl','.log','.dcp','.elf','.map','.su','.S','.h','.c','.xpr','.xdc']]
    record={'verified_utc':datetime.now(timezone.utc).isoformat(),'baseline_files_checked':len(baseline['file_checks']),
        'all_baseline_and_prior_sealed_artifacts_unchanged':True,'candidate_rtl_changed':False,
        'physical_target_mhz':200,'placed':True,'routed':routed,'hardware_qualified':False,
        'staged_rtl_files':len(proof['rtl_sha256']),'compiled_rtl_snapshot_sha256':snapshot,
        'staged_legacy_tops_not_compiled':sorted(unused),
        'target_r5_executed':False,'successful_inference_wcet_certified':False,'external_delivery_bound_certified':False,
        'r5_elf_audit':a,'placement_review':review,'route_review':route_review,
        'previous_validation_sha256':{n:sha(ROOT/n) for n in previous},
        'source_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in sources},
        'documentation_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in docs},
        'evidence_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in evidence}}
    dest.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS physical/R5 evidence sealed; prior seals and all 602 protected baseline files unchanged')
if __name__=='__main__':main()
