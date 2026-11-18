"""Seal the new DDR relay and updated preparation inventory; no board action."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'build/v2/typed200-boot-relay-v1'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-boot-preparation-validation.json'
    profile_path=ROOT/'docs/research/2026-10-16-typed200-target-qualification-profile-v2.json'
    assert not dest.exists() and not profile_path.exists()
    receipt=json.loads((BUILD/'validation.json').read_text())
    for k in ('preserved_sha256','source_sha256','evidence_sha256'):
        for p,h in receipt[k].items():assert sha(ROOT/p)==h,p
    assert '70 single-bit precondition faults' in (BUILD/'host-test.log').read_text()
    assert (BUILD/'link.log').read_text()==''
    assert receipt['entry']==0x10000000 and not receipt['target_executed']
    assert receipt['load_segments'][0]['filesz']==35548
    assert receipt['load_segments'][1]['address']==0x100c0000
    assert receipt['load_segments'][1]['memsz']==16384
    assert '\t496\tstatic' in (BUILD/'unit-0.su').read_text()
    import sys
    sys.path.insert(0,str(ROOT/'src'))
    from sysone.v2.typed200_qualification import assess_preparation
    old_path=ROOT/'docs/research/2026-10-16-typed200-target-qualification-profile.json'
    profile=json.loads(old_path.read_text())
    profile['previous_profile']={'path':old_path.relative_to(ROOT).as_posix(),'sha256':sha(old_path)}
    elf=BUILD/'relay.elf'
    profile['artifacts']['boot_relay']={'path':elf.relative_to(ROOT).as_posix(),'sha256':sha(elf)}
    profile['relay_preparation']={'target_executed':False,'entry':0x10000000,
        'input_source':0x100f0000,'input_bytes':448,'status_word':0x100f1000,
        'a53_input_destination':0xfffee000,'ddr_reservation_half_open':[0x10000000,0x10100000],
        'ddr_reservation_target_approved':False,'entry_requires_final_fsbl_exit':True,
        'note':'Provision input in DDR after loader writes; do not overwrite live FSBL OCM. All real FSBL/PMU/scratch/policy gates remain open.'}
    profile_path.write_text(json.dumps(profile,indent=2)+'\n')
    result=assess_preparation(profile,ROOT)
    assert not result['artifact_review_complete']
    assert len([x for x in result['missing_or_invalid'] if x.startswith('artifact:')])==7
    (BUILD/'preparation-assessment-v2.json').write_text(json.dumps(result,indent=2)+'\n')
    preserved=dict(receipt['preserved_sha256'])
    sources=dict(receipt['source_sha256'])
    for p in (ROOT/'firmware/typed200_boot_relay').iterdir():
        if p.is_file():sources[p.relative_to(ROOT).as_posix()]=sha(p)
    sources[Path(__file__).relative_to(ROOT).as_posix()]=sha(Path(__file__))
    docs={p.relative_to(ROOT).as_posix():sha(p) for p in [profile_path,ROOT/'docs/research/2026-10-16-typed200-ddr-relay-preparation.md']}
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in BUILD.iterdir() if p.is_file()}
    report={'review_complete':True,'qualification_procedure_prepared':True,'separate_relay_locally_verified':True,
        'deployment_ready':False,'target_contacted':False,'target_executed':False,'deployed':False,
        'boot_image_created':False,'bitstream_created':False,'fsbl_pmu_built':False,'wcet_certified':False,
        'prior_review_pytest_passed':510,'relay_host_fault_bits':70,'relay_range_checks':786432,
        'missing_boot_artifact_roles':7,'prior_preserved_unique_files':len(preserved),
        'preserved_sha256':preserved,'source_sha256':sources,'documentation_sha256':docs,'evidence_sha256':evidence}
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS sealed separate DDR relay and updated seven-missing-artifact preparation gate; all prior evidence/baseline unchanged; no board or deployment')
if __name__=='__main__':main()
