"""Pin primary boot sources, export actual ownership rules and prepare offline gates."""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-boot-ownership-review-v1'
VENDOR=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw/lib/sw_apps')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    old=json.loads((ROOT/'docs/research/2026-10-16-typed200-arm-ownership-mvp-validation.json').read_text())
    preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256'):
        for p,h in old[k].items():assert sha(ROOT/p)==h,p;preserved[p]=h
    seal=ROOT/'docs/research/2026-10-16-typed200-arm-ownership-mvp-validation.json'
    preserved[seal.relative_to(ROOT).as_posix()]=sha(seal)
    refs={}
    files={'zynqmp_fsbl':['lscript.ld','xfsbl_config.h','xfsbl_hw.h','xfsbl_handoff.c','xfsbl_exit.S',
                          'xfsbl_bs.c','xfsbl_initialization.c','xfsbl_misc.c'],
           'zynqmp_pmufw':['xpfw_config.h','pm_core.c','pm_config.c','pm_clock.c','pm_reset.c',
                          'pm_master.c','pm_csudma.c','pm_ddr.c','pm_mmio_access.c',
                          'xpfw_mod_em.c','xpfw_error_manager.c','xpfw_restart.c',
                          'xpfw_mod_overtemp.c','csu.h','csudma.h','ipi.h']}
    for app,names in files.items():
        for n in names:
            p=VENDOR/app/'src'/n;dest=OUT/'primary'/app/n;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,dest);assert sha(dest)==sha(p)
            refs[dest.relative_to(ROOT).as_posix()]={'original':str(p),'sha256':sha(dest)}
    (OUT/'primary-sources.json').write_text(json.dumps(refs,indent=2)+'\n')
    rel=OUT.relative_to(ROOT).as_posix()
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
    commands=[]
    def run(argv,name):
        r=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/name).write_bytes(r.stdout);commands.append({'argv':argv,'returncode':r.returncode,'log':name})
        assert r.returncode==0,name
        return r.stdout.decode()
    # Preprocessor examples, intentionally NOT asserted to be the board ELF build flags.
    stub=OUT/'preprocessor-stubs';stub.mkdir();(stub/'xparameters.h').write_text('/* Empty source-review stub: not a deployable BSP. */\n')
    run([*prefix,'gcc','-E','-dM','-x','c','-DK26_SOM','-I'+rel+'/preprocessor-stubs',
         rel+'/primary/zynqmp_pmufw/xpfw_config.h'],'pmu-k26-source-defaults.macros')
    run([*prefix,'gcc','-E','-dM','-x','c',rel+'/primary/zynqmp_fsbl/xfsbl_config.h'],'fsbl-source-defaults.macros')
    export=OUT/'export-rules.c';export.write_text('#include "ownership.h"\n#include <stdio.h>\nint main(void){for(size_t i=0;i<mvp_rule_count;i++)printf("%08x,%08x,%08x\\n",mvp_rules[i].address,mvp_rules[i].mask,mvp_rules[i].expected);return 0;}\n')
    run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Ifirmware/typed200_mvp',
         'firmware/typed200_mvp/ownership.c',rel+'/export-rules.c','-o',rel+'/export-rules'],'rules-compile.log')
    rows=[tuple(int(s,16) for s in line.split(',')) for line in run([*prefix,rel+'/export-rules'],'runtime-rules.log').splitlines()]
    assert len(rows)==20 and sum(mask.bit_count() for _,mask,_ in rows)==131
    with (OUT/'runtime-register-checks.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['source_rule','address','mask','expected'])
        for i,row in enumerate(rows):w.writerow([i+1,*[f'0x{x:08x}' for x in row]])
    manifest=json.loads((ROOT/'build/v2/typed200-mvp-review-v1/candidate-manifest.json').read_text())
    fsbl_reserved=(0xfffc0000,0xfffe9e00)
    a53loads=json.loads((ROOT/'build/v2/typed200-mvp-host-v5/validation.json').read_text())['a53_segments']
    overlaps=[s for s in a53loads if s['address']<fsbl_reserved[1] and fsbl_reserved[0]<s['address']+s['memsz']]
    assert len(overlaps)==2,'Both A53 code and stack overlap reserved FSBL OCM'
    mapping={'fsbl_reserved_half_open':list(fsbl_reserved),'a53_actual_loads':a53loads,
             'overlaps':overlaps,'ordinary_direct_fsbl_load_allowed':False,
             'required_resolution':'Separately built/audited DDR relay after final FSBL exit, or separately reviewed nonoverlapping relink; neither exists yet'}
    (OUT/'memory-map-review.json').write_text(json.dumps(mapping,indent=2)+'\n')
    sys.path.insert(0,str(ROOT/'src'))
    from sysone.v2.typed200_qualification import ARTIFACTS,PREPARATION,FUNCTIONAL,TIMING,assess_preparation
    existing={'recovery':'build/v2/kr260-app-attention-context-capture-large.tar.gz',
        'typed_dcp':'build/v2/typed200-row-range-csa-route-v1/routed.dcp',
        'a53':'build/v2/typed200-mvp-host-v5/a53.elf','r5':'build/v2/typed200-mvp-host-v5/r5.elf',
        'model':'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img',
        'contract':'firmware/typed_intent/generated/contract.json',
        'ps_init':'firmware/typed200_mvp/reference/psu_init.c'}
    profile={'schema':'sysone.typed200.qualification-preparation.v1','target_run_id':None,
             'purpose':'Offline preparation, not a boot image or hardware permission',
             'artifacts':{k:({'path':existing[k],'sha256':sha(ROOT/existing[k])} if k in existing else None) for k in ARTIFACTS},
             'reviews':{k:None for k in PREPARATION+FUNCTIONAL+TIMING},
             'runtime_register_checks':[{'rule':i+1,'address':a,'mask':m,'expected':v} for i,(a,m,v) in enumerate(rows)],
             'additional_pre_admission_observations':[
                 {'name':'CSUDMA_SRC_STS','address':0xffc80008,'mask':0x1fff,'expected':0},
                 {'name':'CSUDMA_DST_STS','address':0xffc80808,'mask':0x1fff,'expected':0},
                 {'name':'CSU_PCAP_RESET','address':0xffca300c,'mask':1,'expected':1},
                 {'name':'CSU_PCAP_STATUS_PL_DONE','address':0xffca3010,'mask':8,'expected':8},
                 {'name':'CSU_STATUS','address':0xffca0000,'policy':'record authentication/encryption; lab trust is not secure-boot proof'},
                 {'name':'CSU_JTAG_CHAIN_STATUS','address':0xffca0034,'policy':'record only; no security/lock writes'},
                 {'name':'CSU_JTAG_SEC','address':0xffca0038,'policy':'record only; decode against exact debug policy'},
                 {'name':'CSU_JTAG_DAP_CFG','address':0xffca003c,'policy':'record only; enabled DAP is not disconnected or noninterfering'},
                 *[{'name':f'PMU_IPI_{i}_ISR','address':0xff330010+i*0x1000,'mask':0xffffffff,'expected':0} for i in range(4)]],
             'capture_symbols':manifest['r5_symbols'],
             'r5_global_alias_note':'local TCM address + 0xffe00000 for R5_0 split-mode debug captures; prove mapping on target',
             'lab_security_policy':'Trusted physical lab boot/debug; no eFuse or debug/security lock writes; no secure-boot claim'}
    p=ROOT/'docs/research/2026-10-16-typed200-target-qualification-profile.json'
    assert not p.exists();p.write_text(json.dumps(profile,indent=2)+'\n')
    assessment=assess_preparation(profile,ROOT)
    assert not assessment['artifact_review_complete'] and len([k for k in assessment['missing_or_invalid'] if k.startswith('artifact:')])==8
    (OUT/'preparation-assessment.json').write_text(json.dumps(assessment,indent=2)+'\n')
    run(['uv','run','--no-sync','python','-m','pytest','-q','tests/test_typed200_qualification.py','tests/test_typed200_mvp.py','tests/test_typed200_timed.py','tests/test_typed200_trace.py','tests/test_typed200_capture.py','tests/test_contract_service.py'],'pytest.log')
    for p,h in preserved.items():assert sha(ROOT/p)==h,p
    result={'review_complete':True,'deployment_ready':False,'target_executed':False,'target_contacted':False,
            'prior_preserved_unique_files':len(preserved),'preserved_sha256':preserved,
            'commands':commands,'source_sha256':{n:sha(ROOT/n) for n in ['scripts/v2/review_typed200_boot_ownership.py','src/sysone/v2/typed200_qualification.py','tests/test_typed200_qualification.py']},
            'profile_sha256':sha(ROOT/'docs/research/2026-10-16-typed200-target-qualification-profile.json'),
            'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
    (OUT/'review-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS pinned primary review, actual C rule export, OCM overlap detected, offline preparation gates/tests; deployment blocked, baseline intact')
if __name__=='__main__':main()
