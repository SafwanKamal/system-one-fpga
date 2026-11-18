"""Preserve prior seals and bind local boot artifacts without inventing readiness."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-k26-boot-chain-v1'
DOC=ROOT/'docs/research'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))
def main():
    anchor=DOC/'2026-10-16-typed200-k26-boot-chain-validation.json'
    profilepath=DOC/'2026-10-16-typed200-target-qualification-profile-v3.json'
    assert not anchor.exists() and not profilepath.exists()
    preserved=json.loads((OUT/'preservation-before.json').read_text())['preserved_sha256']
    for path,digest in preserved.items():assert sha(ROOT/path)==digest,path
    for name,words in [('host-seal-test-final.log','479'),('host-integration-test-final.log','PASS'),
                       ('host-fsbl-test-final.log','23'),('typed-regression-final.log','474 passed')]:
        assert words in (OUT/name).read_text()
    binary=json.loads((OUT/'boot-binary-audit.json').read_text())
    layout=json.loads((OUT/'image-layout-audit.json').read_text())
    assert binary['local_pass'] and layout['local_layout_pass']
    sys.path.insert(0,str(ROOT/'src'))
    from sysone.v2.typed200_qualification import assess_preparation
    old=DOC/'2026-10-16-typed200-target-qualification-profile-v2.json'
    profile=json.loads(old.read_text());profile['previous_profile']=ref(old)
    profile['purpose']='Dedicated boot chain and static layout audited locally; physical cold-POR launch/recovery pending'
    paths={'fsbl':OUT/'app-fsbl-v1/build/typed200_fsbl.elf',
           'pmu':OUT/'app-pmu-v1/build/typed200_pmufw.elf',
           'fsbl_macros':OUT/'app-fsbl-v1-effective-macros.txt',
           'pmu_macros':OUT/'app-pmu-v1-effective-macros.txt',
           'pm_config':OUT/'pm-config-object.bin',
           'typed_bitstream':OUT/'typed200.bit','boot_recipe':OUT/'boot-recipe.json'}
    for role,path in paths.items():profile['artifacts'][role]=ref(path)
    bindings={role:item['sha256'] for role,item in profile['artifacts'].items()}
    evidence=[ref(OUT/n) for n in ['boot-binary-audit.json','image-layout-audit.json',
               'host-seal-test-final.log','host-integration-test-final.log','host-fsbl-test-final.log',
               'fsbl-disassembly-final.txt','pmu-disassembly-final.txt','staged-patches.json']]
    for scope in ['boot_memory_map','fsbl_handoff','pmu_ownership','csu_idle','debug_policy']:
        path=OUT/f'review-{scope}.json'
        receipt=dict(schema='sysone.typed200.qualification-review.v1',scope=scope,verdict='pass',
          artifact_sha256=bindings,evidence=evidence,
          scope_limit='Local source/binary/image review under the documented trusted cold-POR profile only; no physical launch, target execution, power-permission or timing proof',
          trusted_conditions=['No other normal pre-seal clients','BootROM/debug/loader trusted',
            'Actual cold-POR launch still open; do not substitute warm reset or clear reset history',
            'Safety shutdown/reset invalidates the run'])
        path.write_text(json.dumps(receipt,indent=2));profile['reviews'][scope]=ref(path)
    profile['relay_preparation']['ddr_reservation_static_validated']=True
    profile['relay_preparation']['ddr_reservation_target_approved']=False
    profile['local_boot_image']=ref(ROOT/layout['image_path'])
    profile['deployment_ready']=False
    profile['recovery_inventory']={'user_report':'SSH only; user plans JTAG later at home',
      'independent_recovery_verified':False,'board_contact_this_task':False}
    profile['cold_por_launch_route_verified']=False
    profilepath.write_text(json.dumps(profile,indent=2)+'\n')
    assessment=assess_preparation(profile,ROOT)
    assert not any(x.startswith('artifact:') for x in assessment['missing_or_invalid'])
    assert not assessment['artifact_review_complete'] and not assessment['wcet_certified']
    (OUT/'preparation-assessment-v3.json').write_text(json.dumps(assessment,indent=2)+'\n')
    (OUT/'failed-attempts-summary.json').write_text(json.dumps(dict(
      preserved=True,attempts=[
       'Vitis platform RPC failures ws/ws-v2/ws-v3; use successful direct empyro BSP/app flow',
       'Initial C: cwd Lopper include splitting; successful actual cwd S:',
       'Missing SDK AArch64 GCC; official Arm toolchain checksum verified and extracted candidate-locally',
       'Initial host UBSan runtime library absent; use UBSan trap without runtime',
       'First independent image audit used word-valued IHT pointer as byte offset; fixed audit, image unchanged',
       'Initial PMU state was not volatile across ISR/main; retained snapshots; final volatile fix rebuilt/retested and fresh v2 image audited']),indent=2))
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in Path(__file__).resolve().parent.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts}
    evidence={}
    for p in OUT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(OUT)
        if rel.parts[0].startswith('ws') or '.Xil' in rel.parts:continue
        if rel.parts[0]=='tools' and p.suffix.lower() not in ['.json','.sha256asc']:continue
        if p.name in ['.ninja_log','.ninja_deps']:continue
        evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    sdk=Path('C:/AMDDesignTools/2025.2')
    installed={}
    for folder in [sdk/'Vitis/data/embeddedsw/lib/sw_apps/zynqmp_fsbl/src',
                   sdk/'Vitis/data/embeddedsw/lib/sw_apps/zynqmp_pmufw/src']:
        for p in folder.iterdir():
            if p.is_file():installed[str(p)]=sha(p)
    for p in [sdk/'Vivado/gnu/microblaze/nt/bin/mb-gcc.exe',
              OUT/'tools/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-aarch64-none-elf/bin/aarch64-none-elf-gcc.exe']:
        installed[str(p)]=sha(p)
    docs={p.relative_to(ROOT).as_posix():sha(p) for p in [
       DOC/'2026-10-16-typed200-k26-boot-chain.md',profilepath]}
    for path,digest in preserved.items():assert sha(ROOT/path)==digest,path
    result=dict(local_boot_chain_built_audited=True,relay_static_reservation_validated=True,
       local_bitstream_created=True,local_boot_image_created=True,board_contact=False,
       deployment_ready=False,target_executed=False,wcet_certified=False,
       prior_preserved_unique_files=len(preserved),host_policy_cases=479,fsbl_hook_fault_cases=23,
       existing_typed_regression_passed=474,missing_artifact_roles=0,
       open_preparation_reviews=['power_permissions','recovery_procedure','physical_checks'],
       cold_por_launch_route_verified=False,passive_observer_ready=False,
       preserved_sha256=preserved,source_sha256=sources,evidence_sha256=evidence,
       documentation_sha256=docs,installed_primary_sha256=installed)
    anchor.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS local boot chain sealed; preserved',len(preserved),'prior files;',len(evidence),
          'new evidence files. NOT deployment-ready; independent recovery/cold-POR/physical gates remain.')
if __name__=='__main__':main()
