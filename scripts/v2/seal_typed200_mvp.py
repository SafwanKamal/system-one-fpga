"""Review actual candidate ELFs and seal local evidence. Never target/deploy."""
from pathlib import Path
import hashlib,json,shutil,struct
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-mvp-review-v1'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def check(mapping):
    for p,h in mapping.items():assert sha(ROOT/p)==h,p
def elf32_symbols(path):
    b=path.read_bytes();h=struct.unpack_from('<16sHHIIIIIHHHHHH',b)
    assert h[0][:7]==b'\x7fELF\x01\x01\x01' and h[1:3]==(2,40) and h[4]==0
    sections=[struct.unpack_from('<10I',b,h[6]+i*h[11]) for i in range(h[12])]
    ns=sections[h[13]];names=b[ns[4]:ns[4]+ns[5]]
    def string(blob,n):return blob[n:blob.index(b'\0',n)].decode()
    sec={string(names,s[0]):s for s in sections if s[0]}
    sy=sec['.symtab'];ss=sections[sy[6]];strings=b[ss[4]:ss[4]+ss[5]]
    symbols={}
    for i in range(1,sy[5]//sy[9]):
        n,value,size,info,other,index=struct.unpack_from('<IIIBBH',b,sy[4]+i*sy[9])
        assert index!=0,'Unresolved symbol'
        symbols[string(strings,n)]={'address':value,'size':size}
    assert not any(n.startswith('ti_mmio_') for n in symbols)
    for name,address,size in [('ty_shared',0x2f000,384),('ty_pmu_config',0x2f180,32),
                              ('mvp_boot',0x2f1c0,64),('mvp_owner',0x2f300,12)]:
        assert symbols[name]==dict(address=address,size=size)
    for n,a,size in [('.bss',0x20000,51216),('.svc_stack',0x2d000,8192),
                     ('.exception_stacks',0xf000,1280),('.shared',0x2f000,780)]:
        assert (sec[n][1],sec[n][3],sec[n][5])==(8,a,size),n
    return symbols
def main():
    dest=ROOT/'docs/research/2026-10-16-typed200-arm-ownership-mvp-validation.json'
    assert not dest.exists() and OUT.is_dir()
    build=ROOT/'build/v2/typed200-mvp-host-v5'
    receipt=json.loads((build/'validation.json').read_text())
    for field in ('preserved_sha256','source_sha256','evidence_sha256'):check(receipt[field])
    for name,h in receipt['source_sha256'].items():
        q=OUT/'final-v5-sources'/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,q);assert sha(q)==h
    v4=json.loads((ROOT/'build/v2/typed200-mvp-host-v4/validation.json').read_text())
    check(v4['evidence_sha256'])
    for p,h in v4['source_sha256'].items():assert sha(OUT/'superseded-v4-sources'/p)==h,p
    refs=json.loads((ROOT/'firmware/typed200_mvp/reference/sources.json').read_text())
    for n,r in refs.items():
        assert sha(ROOT/'firmware/typed200_mvp/reference'/n)==r['snapshot_sha256']==r['sha256']
        assert sha(Path(r['source']))==r['sha256']
    extra=[ROOT/'build/v2/typed200-row-range-csa-physical-v1/sysone_v2_kr260.srcs/sources_1/bd/system/ip/system_zynq_ultra_ps_e_0_0/system_zynq_ultra_ps_e_0_0.xci',
           Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw/XilinxProcessorIPLib/drivers/zdma_v1_21/src/xzdma_hw.h')]
    provenance={}
    for p in extra:
        q=OUT/'primary-review'/p.name;q.parent.mkdir(exist_ok=True);shutil.copyfile(p,q)
        provenance[str(p)]={'sha256':sha(p),'snapshot':q.relative_to(ROOT).as_posix()}
    (OUT/'additional-primary-sources.json').write_text(json.dumps(provenance,indent=2)+'\n')
    symbols=elf32_symbols(build/'r5.elf')
    frames={}
    for p in build.glob('r5-*.su'):
        for line in p.read_text().splitlines():
            location,size,kind=line.split('\t');assert kind=='static'
            frames[location.rsplit(':',1)[1]]=int(size)
    head_chain=['ty_r5_main','mvp_step','ty_service_poll','ti_bridge_core','ti_head']
    stack=sum(frames[n] for n in head_chain);assert stack<8192
    exception_chain=['ty_exception','mvp_off','wr'];assert sum(frames[n] for n in exception_chain)<256
    # Existing exact numerical reference: 647 fixed-width records, byte-for-byte.
    numerical=ROOT/'build/v2/typed-intent-host-sealed-v4/outputs.bin'
    assert sha(build/'head-outputs.bin')==sha(numerical) and numerical.stat().st_size==647*80
    assert '467 passed' in (build/'pytest.log').read_text()
    assert '131 single-bit faults' in (build/'ownership.log').read_text()
    manifest={'candidate':'cold-boot-sole-R5-typed-MVP-v5','target_executed':False,'deployed':False,
        'boot_image_created':False,'wcet_certified':False,'concurrent_a53_linux_supported':False,
        'r5_elf_sha256':sha(build/'r5.elf'),'a53_elf_sha256':sha(build/'a53.elf'),
        'routed_typed_dcp_sha256':sha(ROOT/'build/v2/typed200-row-range-csa-route-v1/routed.dcp'),
        'r5_symbols':{n:symbols[n] for n in ['ty_shared','ty_trace','ty_pmu_config','ty_pmu_evidence','mvp_boot','mvp_owner']},
        'r5_entry':0,'a53_entry':0xfffc0000,'ocm_input':0xfffee000,'ocm_input_bytes':448,
        'parked_shared_boot_status':2,'r5_nominal_hz':533328000,'reference_declared_hz':33333000,
        'frequency_measured':False,'head_chain_static_frame_sum':stack,'head_chain':head_chain,
        'stack_note':'Compiler static frames plus stated call chain only; no runtime high-water/WCET proof',
        'tcb':['trusted cold-boot producer','stable preinitialized PS/PL clocks/reset/power/permissions',
               'quiescent PMU/CSU/debug and no additional PL master','working responding permit/MMIO path'],
        'head_outputs_sha256':sha(numerical)}
    (OUT/'candidate-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    preserved=dict(receipt['preserved_sha256'])
    p=ROOT/'docs/research/2026-10-16-typed200-row-range-csa-route-validation.json';preserved[p.relative_to(ROOT).as_posix()]=sha(p)
    check(preserved)
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'firmware/typed200_mvp').rglob('*') if p.is_file()}
    for name in ['scripts/v2/create_typed200_mvp_candidate.py','scripts/v2/check_typed200_mvp.py',
                 'scripts/v2/seal_typed200_mvp.py','src/sysone/v2/typed200_mvp.py','tests/test_typed200_mvp.py']:
        sources[name]=sha(ROOT/name)
    docs={'docs/research/2026-10-16-typed200-arm-ownership-mvp.md':sha(ROOT/'docs/research/2026-10-16-typed200-arm-ownership-mvp.md')}
    evidence={}
    for directory in [OUT,*[ROOT/f'build/v2/typed200-mvp-host-v{i}' for i in range(1,6)]]:
        for p in directory.rglob('*'):
            if p.is_file():evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    final={'experiment_complete':True,'local_verification_passed':True,'target_executed':False,
        'deployed':False,'wcet_certified':False,'pytest_passed':467,'head_cases_exact':647,
        'ownership_bit_faults':131,'preserved_unique_files':len(preserved),
        'preserved_sha256':preserved,'source_sha256':sources,'documentation_sha256':docs,'evidence_sha256':evidence}
    dest.write_text(json.dumps(final,indent=2)+'\n')
    print('PASS final native ELF/policy review, snapshots and all preservation hashes; local-only candidate sealed')
if __name__=='__main__':main()
