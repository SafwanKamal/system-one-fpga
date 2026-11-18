"""Build a separate DDR relay; preserve both frozen MVP and qualified baseline."""
from pathlib import Path
import hashlib,json,os,subprocess
from check_typed200_mvp import segments
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-boot-relay-v1'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    OUT.mkdir(exist_ok=False);rel=OUT.relative_to(ROOT).as_posix()
    anchor=ROOT/'docs/research/2026-10-16-typed200-boot-ownership-validation.json'
    prev=json.loads(anchor.read_text());preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256'):
        for p,h in prev[k].items():assert sha(ROOT/p)==h,p;preserved[p]=h
    preserved[anchor.relative_to(ROOT).as_posix()]=sha(anchor)
    a53=ROOT/'build/v2/typed200-mvp-host-v5/a53.elf'
    assert sha(a53)=='63558ce920b53d32078c866fa223149f151f98cd41e3dbf54e37e9b92861ebb2'
    entry,segs=segments(a53);assert entry==0xfffc0000 and len(segs)==2
    data=a53.read_bytes();lines=['#include <stdint.h>\n#include <stddef.h>\nstruct a53_segment {uint64_t address;size_t filesz,memsz;const uint8_t *data;};']
    for i,s in enumerate(segs):
        b=data[s['offset']:s['offset']+s['filesz']]
        lines.append('static const uint8_t a53_%d[]={%s};'%(i,','.join(str(v) for v in b) if b else '0'))
    lines.append('static const struct a53_segment a53_segments[]={'+','.join('{UINT64_C(%d),%d,%d,a53_%d}'%(s['address'],s['filesz'],s['memsz'],i) for i,s in enumerate(segs))+'};')
    lines.append('#define A53_SEGMENTS %d'%len(segs));(OUT/'a53_payload.h').write_text('\n'.join(lines)+'\n')
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    commands=[]
    def run(cmd,name):
        cmd=[str(v) for v in cmd];r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/name).write_bytes(r.stdout);commands.append({'argv':cmd,'returncode':r.returncode,'log':name})
        assert r.returncode==0,name
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
    run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
        '-fsanitize=undefined','-fno-sanitize-recover=all','-DRELAY_HOST_TEST','-I'+rel,
        'firmware/typed200_boot_relay/relay.c','firmware/typed200_boot_relay/test_relay.c','-o',rel+'/relay-test'],'host-compile.log')
    run([*prefix,rel+'/relay-test'],'host-test.log')
    objects=[]
    for i,u in enumerate(['firmware/typed200_boot_relay/relay.c','firmware/typed200_boot_relay/start.S']):
        o=OUT/f'unit-{i}.o';objects.append(o)
        run([tools/'clang.exe','--target=aarch64-none-elf','-mcpu=cortex-a53','-mgeneral-regs-only',
            '-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fstack-usage',
            '-ffunction-sections','-fdata-sections','-I'+str(OUT),'-c',u,'-o',o],f'compile-{i}.log')
    elf=OUT/'relay.elf'
    run([tools/'ld.lld.exe','-T','firmware/typed200_boot_relay/relay.ld','--gc-sections','--no-undefined',
        '-Map='+str(OUT/'relay.map'),*objects,'-o',elf],'link.log')
    run([tools/'llvm-readelf.exe','-h','-l','-S','-s',elf],'elf-audit.txt')
    run([tools/'llvm-objdump.exe','-d',elf],'disassembly.txt')
    rentry,loads=segments(elf);assert rentry==0x10000000 and len(loads)==2
    for s in loads:assert 0x10000000<=s['address'] and s['address']+s['memsz']<=0x100d0000
    dis=(OUT/'disassembly.txt').read_text()
    assert 'ic\tiallu' in dis or 'ic iallu' in dis or 'ic\t\tiallu' in dis
    assert 'relay_main' in dis and 'dsb\tsy' in dis
    for p,h in preserved.items():assert sha(ROOT/p)==h,p
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'firmware/typed200_boot_relay').iterdir() if p.is_file()}
    sources[Path(__file__).relative_to(ROOT).as_posix()]=sha(Path(__file__))
    result={'local_verification_passed':True,'target_executed':False,'deployed':False,
        'boot_recipe_ready':False,'fsbl_pmu_built':False,'ddr_reservation_target_proved':False,
        'elf_sha256':sha(elf),'frozen_a53_elf_sha256':sha(a53),'entry':rentry,'load_segments':loads,
        'input_address':0x100f0000,'input_bytes':448,'status_address':0x100f1000,
        'conditional_ocm_overlap_resolution':'DDR relay entered after final FSBL exit before OCM copy; real FSBL scratch/config/resume policy still open',
        'preserved_sha256':preserved,'source_sha256':sources,'commands':commands,
        'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in OUT.iterdir() if p.is_file()}}
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS new DDR relay: actual C host tests, frozen A53 bytes, separate DDR RX/RW ELF; NO target/boot image; FSBL/PMU policy and reservation still required')
if __name__=='__main__':main()
