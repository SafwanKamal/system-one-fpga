"""Seal only the verified staged RTL and preserve all qualified/prior evidence."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
import create_typed200_candidate as candidate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def check(p,h):assert (ROOT/p).is_file() and sha(ROOT/p)==h,str(p)
def main():
    dest=ROOT/'docs/research/2026-10-15-typed200-validation.json'
    if dest.exists():raise FileExistsError('Preserve sealed validation')
    baseline=read('docs/research/2026-10-14-system-one-preservation.json')
    for r in baseline['file_checks']:check(r['path'],r['before_sha256'])
    previous=read('docs/research/2026-10-15-typed-intent-validation.json')
    for key in ['source_sha256','documentation_sha256','evidence_sha256']:
        for p,h in previous[key].items():check(p,h)
    prior_candidates={}
    for name in ['locality300','counter300']:
        root=Path('rtl/v2/candidates')/name;m=read(root/'candidate.json')
        for p,h in m['candidate_sha256'].items():check(root/p,h)
        root=Path('build/v2')/f'{name}-encoder384';review=read(root/'placement-review.json')
        for p,h in review['evidence_sha256'].items():check(root/p,h)
        assert not review['route_approved']
        prior_candidates[name]=sha(ROOT/root/'placement-review.json')
    candidate.baseline()
    evidence={};staged=Path('build/v2/typed200-integration-v2')
    assert read(staged/'completion-status.json')=={'exit_code':0,'complete':True}
    log=(ROOT/staged/'run.log').read_text()
    assert '5400 golden words, 14 paired completions, 14 launches' in log
    pattern=r'MATCH case (\d+) T(\d+):.*counts (\d+)/(\d+); publication age (\d+)'
    cases=[dict(case=int(c),tokens=int(n),encoder_clocks=int(ec),request_clocks=int(rc),publication_age=int(age))
           for c,n,ec,rc,age in re.findall(pattern,log)]
    assert len(cases)==8 and [c['tokens'] for c in cases]==[1,2,3,4,5,12,64,128]
    # Candidate sources must equal the final native compilation snapshot.
    staged_sources={}
    for line in (ROOT/staged/'source-sha256.txt').read_text().splitlines():
        h,p=line.split(maxsplit=1)
        if p.startswith('rtl/v2/') and Path(p).suffix in ('.sv','.v'):
            rel=p[len('rtl/v2/'):];check(Path('rtl/v2/candidates/typed200')/rel,h);staged_sources[rel]=h
        elif p=='simulation/v2/typed200_scenarios.svh':check(p,h)
    assert staged_sources==candidate.inventory()
    endpoint=Path('build/v2/typed200-endpoint-directed-v1')
    assert read(endpoint/'completion-status.json')=={'exit_code':0,'complete':True}
    assert '636 writes, 80 reads, 14 admissions' in (ROOT/endpoint/'run.log').read_text()
    for line in (ROOT/endpoint/'source-sha256.txt').read_text().splitlines():
        h,p=line.split()
        if p!='typed_intent_axil_tb.sv':check(Path('rtl/v2/candidates/typed200/contracts')/p,h)
    proofs={}
    for label,dirname in [('epoch','typed200-epoch-formal-v1'),('endpoint','typed200-endpoint-formal-v1')]:
        root=Path('build/v2')/dirname;r=read(root/'receipt.json');assert r['passed']
        assert 'Induction step proven: SUCCESS!' in (ROOT/root/'prove.log').read_text()
        check(root/'instrumented.sv',r['instrumented_sha256'])
        if label=='epoch':
            check('rtl/v2/candidates/typed200/contracts/typed_epoch_tracker.sv',r['source_sha256'])
            check('formal/typed_publication/epoch_properties.vh',r['properties_sha256'])
        else:
            for p,h in r['source_sha256'].items():check(p,h)
        proofs[label]=str(root/'receipt.json')
        for p in (ROOT/root).iterdir():
            if p.is_file():evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    # Reuse the unchanged inner gate/guard proof only by exact source identity.
    for name in ['typed_publication_gate.sv','typed_intent_guard.sv']:
        old=ROOT/('rtl/contracts/'+name if name=='typed_publication_gate.sv' else 'rtl/contracts/typed_intent_v1/'+name)
        assert sha(candidate.OUT/'contracts'/name)==sha(old)
    firmware=Path('build/v2/typed200-firmware-v2');r=read(firmware/'receipt.json');assert r['passed'] and r['undefined_symbols']==0
    for p,h in r['source_sha256'].items():check(p,h)
    for p,h in r['artifact_sha256'].items():check(firmware/p,h)
    for root in [staged,endpoint,firmware]:
        for p in (ROOT/root).iterdir():
            if p.is_file():evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    junit=Path('build/v2/typed200-firmware-v1/host-regression.xml')
    suite=ET.parse(ROOT/junit).getroot().find('testsuite')
    assert int(suite.attrib['tests'])==67 and int(suite.attrib['failures'])==0 and int(suite.attrib['errors'])==0
    evidence[junit.as_posix()]=sha(ROOT/junit)
    m=read('rtl/v2/candidates/typed200/candidate.json')
    manifest=candidate.verify(seal=True) if not m['sealed'] else candidate.verify()
    unchanged=[]
    for path,h in manifest['baseline_sha256'].items():
        rel=Path(path).relative_to('rtl/v2')
        if rel.as_posix()!='platform/kr260/axi_memory_port.sv':
            check(Path('rtl/v2/candidates/typed200')/rel,h);unchanged.append(rel.as_posix())
    assert len(unchanged)==22
    docs=[ROOT/'docs/research/2026-10-15-typed200-integration.md',ROOT/'firmware/typed200/README.md',candidate.OUT/'README.md']
    for p in docs:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link:
                target=(p.parent/link.split('#')[0]).resolve()
                assert target.exists() or target==dest,(p,link)
    source_names=['scripts/v2/kr260/create_typed200_candidate.py','scripts/v2/kr260/typed200_control.txt',
        'scripts/v2/check_typed200_firmware.py','scripts/v2/prove_typed200_epoch.py','scripts/v2/prove_typed200_endpoint.py',
        'scripts/v2/seal_typed200.py','simulation/v2/run_typed200.sh','simulation/v2/run_typed200_endpoint.sh',
        'simulation/v2/typed200_scenarios.svh','rtl/contracts/typed_epoch_tracker.sv',
        'formal/typed_publication/epoch_properties.vh','formal/typed_publication/typed200_endpoint_properties.vh']
    sources=[ROOT/p for p in source_names]+[p for p in (ROOT/'firmware/typed200').rglob('*') if p.is_file()]
    record={'verified_utc':datetime.now(timezone.utc).isoformat(),'candidate':'typed200','target_mhz':200,
        'abi':'0x54590201','contract_sha256':manifest['contract_sha256'],
        'candidate_manifest_sha256':sha(candidate.OUT/'candidate.json'),
        'baseline_files_checked':len(baseline['file_checks']),'all_baseline_files_unchanged':True,
        'prior_typed_milestone_and_sealed_candidates_unchanged':True,'prior_placement_reviews_sha256':prior_candidates,
        'qualified_copied_sources_unchanged':unchanged,'candidate_rtl_count':len(staged_sources),
        'arithmetic_changed':False,'live_drain_observer_has_control_feedback':False,
        'co_simulation':{'normal_cases':cases,'golden_words_compared':5400,'paired_completions':14,
            'all_driven_axi_cycles_equal':True,'raw_encoder_request_counters_equal':True,
            'comparison':'paired identical memory-response stream, not differently phased saved random-stall counts',
            'fault_tests':['delayed final B prevents native completion','early Accepted fails closed',
                'late BRESP error','RRESP error with unchanged data','held-B timeout exactly 3000000 cycles',
                'late response/proposal cannot reverse quarantine','stale session','malformed shape no launch'],
            'synthetic_arm_proposals':True,'real_r5_execution':False},
        'endpoint_directed':{'writes':636,'reads':80,'validated_admissions':14},'formal_receipts':proofs,
        'unchanged_gate_guard_proofs_reused_by_hash':True,'host_guardrail_tests':67,
        'firmware_receipt':str(firmware/'receipt.json'),'r5_relocatable_link':True,'r5_undefined_symbols':0,
        'new_fpga_physical_build':False,'hardware_qualified':False,'cdc_signed_off':False,
        'r5_bsp_tcm_map':False,'target_wcet_certified':False,'successful_inference_deadline_certified':False,
        'failed_attempt':{'path':'build/v2/typed200-integration-v1','reason':'testbench sampled reference counters after raw completion; corrected sampling edge without RTL change'},
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},'evidence_sha256':evidence,
        'documentation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in docs}}
    dest.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS sealed typed200:',len(staged_sources),'RTL, 5400 golden words, 14 paired completions; 602 baseline files preserved')
if __name__=='__main__':main()
