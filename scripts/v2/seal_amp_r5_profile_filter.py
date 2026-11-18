"""Seal the local compatibility fix and explicitly retain provenance blockers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-amp-r5-profile-filter-v1'
REPORT='docs/research/2026-10-17-typed200-amp-r5-profile-filter.md'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,data):
    assert not p.exists(),p
    p.write_text(json.dumps(data,indent=2)+'\n')

def main():
    before=json.loads((BASE/'preservation-before.json').read_text())
    prior=json.loads((BASE/'prior-validation.json').read_text());preserved={}
    for group in ['preserved_sha256','candidate_sha256']:
        for name,digest in prior[group].items():
            assert name not in preserved or preserved[name]==digest
            preserved[name]=digest
    assert sha(ROOT/before['anchor'])==before['anchor_sha256']
    preserved[before['anchor']]=before['anchor_sha256']
    assert len(preserved)==before['files']==10910
    def check(item):
        name,digest=item;assert sha(ROOT/name)==digest,name
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,preserved.items()))
    receipts={}
    for name in ['filter-check-v1','policy-check-v1','composition-check-v2','source-audit-v1','inventory-v1','dashboard-v1']:
        r=json.loads((BASE/name/'receipt.json').read_text());assert r['passed'],name
        receipts[name]=r
    assert not receipts['filter-check-v1']['source_path_qualified']
    assert receipts['filter-check-v1']['user_prot_combinations']==524288
    assert receipts['policy-check-v1']['cases']==262233
    assert not receipts['composition-check-v2']['bootable_filtered_smoke_firmware_ready']
    health=json.loads((BASE/'inventory-v1/health.stdout').read_text())
    assert health['boot_id']=='6c80ec1a-e7ae-473f-b169-d54f129615d1'
    assert health['taint']=='12288' and health['cpus_online']=='0-3'
    assert not health['r5_module_present'] and not health['remoteproc']
    assert health['manager']=='operating' and '0->0,' in health['xmutil']['stdout']
    assert (BASE/'dashboard-v1/dashboard.stdout').read_text().strip()=='active'
    assert any(line.split()[0]=='pl0_ref' and line.split()[1:5]==['0','0','0','99999999'] for line in health['clock'])
    write(BASE/'source-audit-v1/visual-review.json',dict(passed=True,pages_visually_reviewed=[63,411],
        complete_page_rendering=True,source_changed=False,upper_bit_semantics_qualified=False))
    write(BASE/'readiness.json',dict(local_profile_compatibility_passed=True,workload_validator_passed=True,
        shared_mid_zero_collision_documented=True,source_authentication_qualified=False,
        source_path_qualified_parameter_required_value=0,enable_r5_default=0,
        upper_bit_semantics_qualified=False,bootable_filtered_smoke_firmware_ready=False,
        physical_composition_qualified=False,target_filter_deployed=False,
        full_inference_ready=False,jtag_used=False,raw_ps_mmio_used=False,
        target_operations='Pinned SSH read-only health inventory only',
        blockers=['Resolve CCI/TCU shared MID0 for protected endpoint and threat model',
                  'Qualify new zero-count filtered smoke firmware and negative APU observation',
                  'Physical/netlist metadata provenance, trusted boot/session/firewalls/output and full target qualification']))
    write(BASE/'failed-attempt-ledger.json',dict(originals_retained=True,attempts=[
        dict(path='composition-check-v1',issue='Generator expected43 ports; actual39; stopped before compilation or target action',superseded_by='composition-check-v2'),
        dict(path='inventory-v1',issue='Dashboard alias query returned inactive; correct snap unit confirmed active separately; no service mutation',superseded_by='dashboard-v1')]))
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files+=list((ROOT/'rtl/v2/candidates/typed200_amp_r5_profile').glob('*'))
    names=['prepare_amp_r5_profile_filter.py','check_amp_r5_profile_filter.py',
        'amp_r5_profile_policy.py','check_amp_r5_profile_policy.py',
        'audit_amp_r5_profile_sources.py','check_amp_r5_profile_composition.py',
        'prepare_amp_r5_profile_inventory.py','seal_amp_r5_profile_filter.py']
    files+=[ROOT/'scripts/v2'/name for name in names]+[ROOT/REPORT]
    candidate={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files)) if p.is_file()}
    write(ROOT/'docs/research/2026-10-17-typed200-amp-r5-profile-filter-validation.json',dict(
        passed=True,scope='Local observed-profile compatibility, source-collision audit and evidence integrity',
        observed_utc=datetime.now(timezone.utc).isoformat(),preserved_unique_files=len(preserved),
        preserved_sha256=preserved,candidate_files=len(candidate),candidate_sha256=candidate,
        source_authentication_qualified=False,upper_bit_semantics_qualified=False,
        full_inference_ready=False,target_filter_deployed=False,handoff_mutable_unsealed=True))
    print(f'PASS {len(preserved)} preserved + {len(candidate)} new files sealed; source-path gate stays zero')

if __name__=='__main__':main()
