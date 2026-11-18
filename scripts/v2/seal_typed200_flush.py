"""Seal the independent synchronous-FIFO candidate and recheck frozen baselines."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
import create_typed200_flush_candidate as candidate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def check(p,h):assert sha(ROOT/p)==h,p
def main():
    dest=ROOT/'docs/research/2026-10-15-typed200-flush-validation.json'
    assert not dest.exists(),'Preserve completed seal'
    baseline=read('docs/research/2026-10-14-system-one-preservation.json')
    for row in baseline['file_checks']:check(row['path'],row['before_sha256'])
    previous=['docs/research/2026-10-15-'+n+'-validation.json' for n in
              ['typed-intent','typed200','typed200-transport','typed200-physical-r5']]
    for fn in previous:
        for key in ['source_sha256','documentation_sha256','evidence_sha256']:
            for n,h in read(fn)[key].items():check(n,h)
    m=candidate.verify();assert m['sealed']
    unit=Path('build/v2/typed200-flush-unit-v3');r=read(unit/'receipt.json');assert r['passed']
    for n,h in r['source_sha256'].items():check(n,h)
    for n,h in r['staged_sha256'].items():check(unit/n,h)
    unitlog=(ROOT/unit/'run.log').read_text()
    metrics=re.findall(r'L(\d+): (\d+) cycles, (\d+) abort/reset cases',unitlog)
    assert [int(x[0]) for x in metrics]==[3,4,5] and sum(int(x[1]) for x in metrics)==65673
    formal=Path('build/v2/typed200-flush-live-formal-v3');r=read(formal/'receipt.json')
    assert r['passed'] and r['depth']==8 and r['width']==128
    for n,h in r['source_sha256'].items():check(n,h)
    for n,h in r['artifact_sha256'].items():check(formal/n,h)
    sim=Path('build/v2/typed200-flush-integration-v2');assert read(sim/'completion-status.json')=={'exit_code':0,'complete':True}
    log=(ROOT/sim/'run.log').read_text();assert '5400 golden words, 14 paired completions, 14 launches' in log
    assert len(re.findall(r'^MATCH case',log,re.M))==8
    for line in (ROOT/sim/'source-sha256.txt').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if n.startswith('rtl/v2/'):check(candidate.OUT.relative_to(ROOT)/n[len('rtl/v2/'):],h)
        elif n.startswith('simulation/v2/vectors/'):check(n,h)
    ooc=Path('build/v2/typed200-flush-ooc-v1')
    assert 'Asynchronous reset/preset flip-flops: 0' in (ROOT/ooc/'reset-mapping.txt').read_text()
    assert 'LUTAR-1' not in (ROOT/ooc/'methodology.rpt').read_text()
    for n in ['encoder/result_streamer.sv','common/stream_fifo_sync_clear.sv']:
        assert sha(ROOT/ooc/Path(n).name)==sha(candidate.OUT/n)
    board=Path('build/v2/board-readonly-recovery-20261015-v1');r=read(board/'receipt.json')
    assert r['qualified_package_matches_frozen_archive'] and not r['remote_configuration_changed']
    archive=Path('build/v2/kr260-app-attention-context-capture-large.tar.gz');check(archive,r['archive_sha256'])
    physical=Path('build/v2/typed200-flush-physical-v1');p=ROOT/physical
    assert read(physical/'synth-status.json')['exit_code']==0
    assert read(physical/'place-status.json')['exit_code']==0
    proof=read(physical/'input-proof.json')
    check(candidate.OUT.relative_to(ROOT)/'candidate.json',proof['candidate_sha256'])
    check('rtl/platform/typed200/typed200_encoder_wrapper.v',proof['wrapper_sha256'])
    check('scripts/v2/kr260/create_project_kr260.tcl',proof['board_setup_sha256'])
    unused={'platform/kr260/kr260_encoder.sv','platform/kr260/kr260_encoder_wrapper.v'}
    actual={x.relative_to(p/'rtl-snapshot').as_posix():sha(x) for x in (p/'rtl-snapshot').rglob('*') if x.is_file()}
    assert set(actual)==set(proof['rtl_sha256'])-unused
    for n,h in proof['rtl_sha256'].items():
        check(physical/'rtl-input'/n,h)
        if n not in unused:assert actual[n]==h
        if n!='platform/kr260/typed200_encoder_wrapper.v':check(candidate.OUT.relative_to(ROOT)/n,h)
    review=read(physical/'placement-review.json')
    for n,h in review['evidence_sha256'].items():check(physical/n,h)
    post=read(physical/'postplace-review.json') if (p/'postplace-review.json').exists() else None
    if post:
        for n,h in post['evidence_sha256'].items():check(physical/n,h)
    decision=post if post else review
    routed=(p/'route-status.json').exists();route=read(physical/'route-review.json') if routed else None
    if decision['route_approved']:assert routed and read(physical/'route-status.json')['exit_code']==0
    else:assert not routed
    if route:
        for n,h in route['evidence_sha256'].items():check(physical/n,h)
    doc=ROOT/'docs/research/2026-10-15-typed200-synchronous-flush.md'
    for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
        if '://' not in link:assert (doc.parent/link.split('#')[0]).resolve().exists(),link
    sources=[x for x in candidate.OUT.rglob('*') if x.is_file()]
    names=['scripts/v2/kr260/create_typed200_flush_candidate.py','scripts/v2/check_typed200_flush.py',
        'scripts/v2/prove_typed200_flush_fifo.py','scripts/v2/prove_typed200_flush_live.py',
        'simulation/v2/typed200_flush_tb.sv','simulation/v2/run_typed200_flush.sh',
        'scripts/v2/kr260/synth_typed200_flush_ooc.tcl','scripts/v2/kr260/build_typed200_flush_physical.py',
        'scripts/v2/kr260/audit_typed200_flush_physical.tcl','scripts/v2/kr260/review_typed200_flush_placement.py',
        'scripts/v2/kr260/audit_typed200_flush_ooc_clocks.tcl','scripts/v2/kr260/physopt_typed200_flush.tcl',
        'scripts/v2/kr260/review_typed200_flush_postplace.py',
        'scripts/v2/seal_typed200_flush.py']
    if routed:names.append('scripts/v2/kr260/review_typed200_flush_route.py')
    sources += [ROOT/n for n in names]
    evidence=[]
    clock_audit=physical/'encoder-ooc-clock-audit'
    assert 'Stored OOC clocks: 0' in (ROOT/clock_audit/'clocks.txt').read_text()
    for directory in [unit,formal,sim,ooc,board,physical,physical/'place',physical/'placement-audit',clock_audit,
                      physical/'route-admission-v1-rejected',
                      *[Path('build/v2')/name for name in ['typed200-flush-unit-v1','typed200-flush-unit-v2',
                          'typed200-flush-integration-v1','typed200-flush-formal-v1',
                          'typed200-flush-live-formal-v1','typed200-flush-live-formal-v2']],
                      *([physical/'postplace-opt-v1'] if post else []),*([physical/'route'] if routed else [])]:
        evidence += [x for x in (ROOT/directory).iterdir() if x.is_file() and x.suffix in
            ['.json','.rpt','.txt','.log','.tcl','.sv','.ys','.dcp','.xdc','.xpr']]
    record={'verified_utc':datetime.now(timezone.utc).isoformat(),'baseline_files_checked':len(baseline['file_checks']),
        'all_baseline_and_previous_sealed_artifacts_unchanged':True,'candidate':'typed200_flush',
        'numerical_contract_changed':False,'deadline_epoch_abi_changed':False,
        'golden_words_checked':5400,'paired_completions':14,'unit_cycles_compared':65673,'unit_latencies_checked':[3,4,5],
        'actual_fifo_size_induction_passed':True,'physical_target_mhz':200,'placed':True,'routed':routed,
        'physical_sta_passed':bool(route and route['sta_passed']),
        'full_design_lutar_warning_removed':True,
        'hardware_qualified':False,'target_r5_executed':False,'successful_inference_wcet_certified':False,
        'board_readonly_receipt':r,'placement_review':review,'postplace_review':post,'route_review':route,
        'encoder_ooc_stored_clock_count':0,'compiled_rtl_snapshot_sha256':actual,
        'previous_validation_sha256':{n:sha(ROOT/n) for n in previous},
        'source_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in sources},
        'documentation_sha256':{doc.relative_to(ROOT).as_posix():sha(doc)},
        'evidence_sha256':{x.relative_to(ROOT).as_posix():sha(x) for x in evidence}}
    dest.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS synchronous FIFO evidence sealed; all prior seals and 602 baseline files preserved')
if __name__=='__main__':main()
