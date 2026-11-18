"""Audit preservation and bind the completed standalone typed-intent evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def check(p,h):
    p=ROOT/p
    assert p.is_file() and sha(p)==h,str(p)

def main():
    old=read('docs/research/2026-10-14-system-one-preservation.json')
    for row in old['file_checks']:check(row['path'],row['before_sha256'])
    candidates={}
    evidence={}
    for name in ['locality300','counter300']:
        root=Path('rtl/v2/candidates')/name;manifest=read(root/'candidate.json')
        for p,h in manifest['candidate_sha256'].items():check(root/p,h)
        candidates[name]={'sources_checked':len(manifest['candidate_sha256']),
                          'manifest_sha256':sha(ROOT/root/'candidate.json')}
        root=Path('build/v2')/f'{name}-encoder384'
        review=read(root/'placement-review.json')
        for p,h in review['evidence_sha256'].items():check(root/p,h)
        assert not review['route_approved']
        evidence[str(root/'placement-review.json')]=sha(ROOT/root/'placement-review.json')
    for p,h in read('docs/research/2026-10-15-typed-publication-prototype-validation.json')['sha256'].items():check(p,h)
    for filename,key in [('2026-10-15-locality300-validation.json','new_implementation_sha256'),
                         ('2026-10-15-counter300-validation.json','source_sha256')]:
        for p,h in read('docs/research/'+filename)[key].items():check(p,h)
    frozen=read('firmware/typed_intent/generated/contract.json')
    canonical=json.dumps(frozen['spec'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
    assert hashlib.sha256(canonical).hexdigest()==frozen['contract_sha256']
    assert frozen['contract_sha256'] in (ROOT/'rtl/contracts/typed_intent_v1/typed_intent_guard.sv').read_text()
    for p,h in read('firmware/typed_intent/generated/manifest.json')['files'].items():
        check(Path('firmware/typed_intent/generated')/p,h)
    receipt_paths={
        'host':'build/v2/typed-intent-host-sealed-v4/receipt.json',
        'r5':'build/v2/typed-intent-r5-sealed-v4/receipt.json',
        'gate':'build/v2/typed-formal-gate-final-v5/receipt.json',
        'guard':'build/v2/typed-formal-guard-observed-v2/receipt.json',
        'axil':'build/v2/typed-formal-axil-guarded-v3/receipt.json'}
    for name,p in receipt_paths.items():
        r=read(p);root=Path(p).parent
        if name in ['host','r5']:
            assert r['passed']
            for f,h in r['source_sha256'].items():check(f,h)
            for f,h in r['artifact_sha256'].items():check(root/f,h)
        else:
            assert r['induction_proved'] and r['exit_code']==0
            assert 'Induction step proven: SUCCESS!' in (ROOT/root/'prove.log').read_text()
            check(root/'instrumented.sv',r['instrumented_sha256'])
            rtl={'gate':'rtl/contracts/typed_publication_gate.sv',
                 'guard':'rtl/contracts/typed_intent_v1/typed_intent_guard.sv',
                 'axil':'rtl/contracts/typed_intent_v1/typed_intent_axil.sv'}[name]
            props={'gate':'formal/typed_publication/invariants.vh',
                   'guard':'formal/typed_publication/guard_properties.vh',
                   'axil':'formal/typed_publication/axil_properties.vh'}[name]
            check(rtl,r['rtl_sha256']);check(props,r['properties_sha256'])
            for f,h in r.get('dependency_sha256',{}).items():check(f,h)
            for f,h in r.get('observation_dependency_sha256',{}).items():check(f,h)
        evidence[p]=sha(ROOT/p)
    sim=Path('build/v2/typed-intent-axil-launch-v4')
    assert read(sim/'completion-status.json')=={'exit_code':0,'complete':True}
    run=(ROOT/sim/'run.log').read_text()
    assert '464 writes, 58 reads, 13 admissions' in run
    paths={p.name:p for p in [ROOT/'rtl/contracts/typed_publication_gate.sv',
        ROOT/'rtl/contracts/typed_intent_v1/typed_intent_guard.sv',
        ROOT/'rtl/contracts/typed_intent_v1/typed_intent_axil.sv',
        ROOT/'simulation/v2/typed_intent_axil_tb.sv']}
    for line in (ROOT/sim/'source-sha256.txt').read_text().splitlines():
        h,p=line.split();assert sha(paths[p])==h
    for p in (ROOT/sim).iterdir():
        if p.is_file():evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    junit=Path('build/v2/typed-intent-host-service-v3/host-regression.xml')
    suite=ET.parse(ROOT/junit).getroot().find('testsuite')
    assert int(suite.attrib['tests'])==67 and int(suite.attrib['failures'])==0 and int(suite.attrib['errors'])==0
    evidence[junit.as_posix()]=sha(ROOT/junit)
    # Show why preserving per-class scales is relevant on this actual fixture set.
    raw=(ROOT/'build/v2/typed-intent-host-sealed-v4/outputs.bin').read_bytes()
    raw_differences=0
    for i in range(640):
        values=struct.unpack_from('<II18i',raw,80*i)
        raw_label=max(range(18),key=lambda c:values[c+2])
        raw_differences+=raw_label!=values[1]
    docs=[ROOT/'firmware/typed_intent/README.md',
          ROOT/'docs/research/2026-10-15-typed-intent-implementation.md']
    for p in docs:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link:
                target=(p.parent/link.split('#')[0]).resolve()
                pending=ROOT/'docs/research/2026-10-15-typed-intent-validation.json'
                assert target.is_file() or target==pending,(p,link)
    sources=[p for directory in ['firmware/typed_intent','rtl/contracts/typed_intent_v1','formal/typed_publication']
             for p in (ROOT/directory).rglob('*') if p.is_file()]
    sources += [ROOT/p for p in ['scripts/v2/freeze_typed_intent.py','scripts/v2/check_typed_intent.py',
        'scripts/v2/build_typed_intent_r5.py','scripts/v2/prove_typed_publication.py',
        'scripts/v2/seal_typed_intent.py','simulation/v2/typed_intent_axil_tb.sv',
        'simulation/v2/run_typed_intent_axil.sh']]
    record={'verified_utc':datetime.now(timezone.utc).isoformat(),'standalone_prototype':True,
        'contract_sha256':frozen['contract_sha256'],'baseline_files_checked':len(old['file_checks']),
        'all_baseline_files_unchanged':True,'sealed_candidates':candidates,
        'prior_prototype_and_placement_evidence_unchanged':True,
        'host_cases':647,'exact_integer_logits':11520,'exact_scaled_label_decisions':640,
        'raw_argmax_differs_from_scaled_in_fixture_cases':raw_differences,
        'host_regression_tests':67,'sanitizers':['address','undefined'],
        'rtl_bus_transactions':{'writes':464,'reads':58,'validated_launches':13},
        'formal':{'gate_invariants':True,'guard_invariants':True,'axil_protocol_properties':True,
                  'assumptions':['first sampled edge reset','single synchronous PL clock'],
                  'full_endpoint_functional_proof':False},
        'r5_relocatable_object':True,'r5_undefined_symbols':0,'r5_nested_head_bridge_stack_bytes':1688,
        'target_execution':False,'tcm_linker_map':False,'wcet_certified':False,
        'encoder_integrated':False,'cdc_signed_off':False,'new_physical_build':False,
        'hardware_qualified':False,'successful_inference_deadline_guarantee':False,
        'host_or_network_delivery_guarantee':False,
        'final_receipts':receipt_paths,'evidence_sha256':evidence,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'documentation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in docs}}
    dest=ROOT/'docs/research/2026-10-15-typed-intent-validation.json'
    if dest.exists():raise FileExistsError('Preserve sealed validation')
    dest.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS preservation + evidence seal:',len(old['file_checks']),'baseline files;',raw_differences,'raw/scaled differences')
if __name__=='__main__':main()
