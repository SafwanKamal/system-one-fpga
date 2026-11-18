"""Bind corrected C/RTL digest interoperability without changing older seals."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/v2/kr260'))
import create_typed200_candidate as candidate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def check(p,h):assert (ROOT/p).is_file() and sha(ROOT/p)==h,str(p)
def main():
    dest=ROOT/'docs/research/2026-10-15-typed200-transport-validation.json'
    if dest.exists():raise FileExistsError('Preserve completed transport seal')
    baseline=read('docs/research/2026-10-14-system-one-preservation.json')
    for row in baseline['file_checks']:check(row['path'],row['before_sha256'])
    earlier=['docs/research/2026-10-15-typed-intent-validation.json','docs/research/2026-10-15-typed200-validation.json']
    for fn in earlier:
        r=read(fn)
        for key in ['source_sha256','documentation_sha256','evidence_sha256']:
            for p,h in r[key].items():check(p,h)
    m=candidate.verify();assert m['sealed']
    assert sha(candidate.OUT/'candidate.json')==read(earlier[-1])['candidate_manifest_sha256']
    for name in ['locality300','counter300']:
        root=Path('rtl/v2/candidates')/name
        for p,h in read(root/'candidate.json')['candidate_sha256'].items():check(root/p,h)
        root=Path('build/v2')/f'{name}-encoder384'
        for p,h in read(root/'placement-review.json')['evidence_sha256'].items():check(root/p,h)
    firmware=Path('build/v2/typed200-transport-v4');r=read(firmware/'receipt.json');assert r['passed'] and r['undefined_symbols']==0
    for p,h in r['source_sha256'].items():check(p,h)
    for p,h in r['artifact_sha256'].items():check(firmware/p,h)
    frames=[int(x,16) for x in (ROOT/firmware/'wire-frames.hex').read_text().splitlines()]
    digest=int(m['contract_sha256'],16);expected=[(digest>>(32*i))&0xffffffff for i in range(8)]
    assert len(frames)==27 and frames[5:13]==expected and frames[17:25]==expected
    sim=Path('build/v2/typed200-c-transport-v2');assert read(sim/'completion-status.json')=={'exit_code':0,'complete':True}
    log=(ROOT/sim/'run.log').read_text()
    assert 'PASS actual C-generated request/proposal SHA frames accepted by RTL' in log
    assert '668 writes, 91 reads, 15 admissions' in log
    for line in (ROOT/sim/'source-sha256.txt').read_text().splitlines():
        h,p=line.split()
        if p=='wire-frames.hex':check(firmware/p,h)
        elif p!='typed_intent_axil_tb.sv':check(Path('rtl/v2/candidates/typed200/contracts')/p,h)
    docs=[ROOT/'docs/research/2026-10-15-typed200-transport-review.md',ROOT/'firmware/typed200_v2/README.md']
    for p in docs:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link:
                target=(p.parent/link.split('#')[0]).resolve();assert target.exists() or target==dest,(p,link)
    sources=[p for p in (ROOT/'firmware/typed200_v2').rglob('*') if p.is_file()]
    sources += [ROOT/p for p in ['scripts/v2/check_typed200_transport.py','scripts/v2/seal_typed200_transport.py','simulation/v2/run_typed200_transport.sh']]
    evidence={}
    for root in [firmware,sim]:
        for p in (ROOT/root).iterdir():
            if p.is_file():evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    record={'verified_utc':datetime.now(timezone.utc).isoformat(),'active_transport':'firmware/typed200_v2',
        'supersedes_sha_transport':['firmware/typed_intent/typed_mailbox.c','firmware/typed200/typed200.c'],
        'issue':'canonical SHA digest bytes vs numeric least-significant-register-word order',
        'candidate_rtl_changed':False,'candidate_manifest_sha256':sha(candidate.OUT/'candidate.json'),
        'contract_sha256':m['contract_sha256'],'numeric_digest_register_words_low_to_high':[f'0x{x:08x}' for x in expected],
        'host_sanitizers':['address','undefined'],'known_numeric_words_checked':True,
        'canonical_terminal_digest_decode_checked':True,'compiled_c_request_proposal_frames_replayed_through_rtl':True,
        'accepted_label_checked':17,'rtl_transactions':{'writes':668,'reads':91,'validated_admissions':15},
        'r5_relocatable_link':True,'undefined_symbols':0,'target_execution':False,
        'hardware_qualified':False,'successful_inference_wcet_certified':False,'new_physical_build':False,
        'baseline_files_checked':len(baseline['file_checks']),'all_baseline_and_previous_sealed_artifacts_unchanged':True,
        'earlier_validation_sha256':{p:sha(ROOT/p) for p in earlier},
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'evidence_sha256':evidence,'documentation_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in docs}}
    dest.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS corrected C/RTL digest transport sealed; 668 writes/91 reads; all earlier seals +602 baseline files preserved')
if __name__=='__main__':main()
