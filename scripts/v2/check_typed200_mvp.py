"""Local-only MVP build/fault injection. No Vivado, boot image or target access."""
from pathlib import Path
import argparse,hashlib,json,os,struct,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def segments(p):
    b=p.read_bytes();assert b[:4]==b'\x7fELF' and b[5]==1
    if b[4]==1:
        entry,off=struct.unpack_from('<II',b,24);size,num=struct.unpack_from('<HH',b,42)
        rows=[struct.unpack_from('<IIIIIIII',b,off+i*size) for i in range(num)]
        seg=[dict(offset=r[1],address=r[2],physical=r[3],filesz=r[4],memsz=r[5],flags=r[6]) for r in rows if r[0]==1]
        machine=40
    else:
        entry,off=struct.unpack_from('<QQ',b,24);size,num=struct.unpack_from('<HH',b,54)
        rows=[struct.unpack_from('<IIQQQQQQ',b,off+i*size) for i in range(num)]
        seg=[dict(offset=r[2],address=r[3],physical=r[4],filesz=r[5],memsz=r[6],flags=r[1]) for r in rows if r[0]==1]
        machine=183
    assert struct.unpack_from('<H',b,18)[0]==machine
    for s in seg:
        assert s['physical']==s['address'] and s['filesz']<=s['memsz']
        assert s['flags']&3!=3,'writable executable segment'
        assert s['offset']+s['filesz']<=len(b)
    for a,c in zip(sorted(seg,key=lambda s:s['address']),sorted(seg,key=lambda s:s['address'])[1:]):
        assert a['address']+a['memsz']<=c['address'],'overlapping segments'
    return entry,seg
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);a=ap.parse_args()
    import re
    assert re.fullmatch(r'typed200-mvp-host-v[0-9]+',a.name)
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    prior=json.loads((ROOT/'docs/research/2026-10-16-typed200-row-range-csa-route-validation.json').read_text())
    preserved={}
    for k in ('preserved_sha256','source_sha256','documentation_sha256','evidence_sha256'):
        for p,h in prior[k].items():
            assert p not in preserved or preserved[p]==h;preserved[p]=h
    for p,h in preserved.items():assert sha(ROOT/p)==h,p
    (out/'preservation-before.json').write_text(json.dumps({'files':len(preserved),'passed':True},indent=2))
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    commands=[]
    def run(cmd,name):
        r=subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/name).write_bytes(r.stdout);commands.append([str(x) for x in cmd])
        if r.returncode:raise RuntimeError(name+' failed; retain directory')
        return r.stdout.decode(errors='replace')
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
    host=['-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fno-fast-math','-ffp-contract=off','-fsanitize=address,undefined','-fno-sanitize-recover=all']
    base=['firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c']
    def hosttest(name,units,flags=(),args=()):
        run([*prefix,'gcc',*host,*flags,*units,'-o',rel+'/'+name],name+'-compile.log')
        run([*prefix,rel+'/'+name,*args],name+'.log')
    hosttest('ownership',['firmware/typed200_mvp/ownership.c','firmware/typed200_mvp/test_ownership.c'])
    hosttest('service',[*base,'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c','firmware/typed200_r5/test_service.c'])
    hosttest('driver',[*base,'firmware/typed200_v2/test_driver.c'],args=[rel+'/driver-wire.txt'])
    run([*prefix,'gcc',*host,'firmware/typed_intent/typed_intent.c','firmware/typed_intent/typed_mailbox.c','firmware/typed_intent/test_runner.c','-lm','-o',rel+'/head'],'head-compile.log')
    golden='build/v2/typed-intent-host-sealed-v4'
    run([*prefix,rel+'/head',golden+'/inputs.bin',rel+'/head-outputs.bin'],'head.log')
    assert (out/'head-outputs.bin').read_bytes()==(ROOT/golden/'outputs.bin').read_bytes(),'numerical head regression'
    hosttest('pmu',['firmware/typed200_trace/trace.c','firmware/typed200_timed/pmu.c','firmware/typed200_timed/test_pmu.c'],['-DTY_PMU_HOST_TEST'])
    hosttest('supervisor',[*base,'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c','firmware/typed200_mvp/ownership.c','firmware/typed200_mvp/supervisor.c','firmware/typed200_mvp/test_supervisor.c'])
    run(['uv','run','--no-sync','python','-m','pytest','-q','tests/test_contract_service.py','tests/test_typed200_timed.py','tests/test_typed200_trace.py','tests/test_typed200_capture.py','tests/test_typed200_mvp.py'],'pytest.log')
    flags=['-O2','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-fstack-usage']
    def build(name,target,units,ld,extra=()):
        objs=[]
        for i,u in enumerate(units):
            obj=out/f'{name}-{i}.o';objs.append(obj)
            run([tools/'clang.exe',*target,*flags,*extra,'-c',u,'-o',obj],f'{name}-compile-{i}.log')
        elf=out/(name+'.elf')
        run([tools/'ld.lld.exe','-T',ld,'--gc-sections','--no-undefined','-Map='+str(out/(name+'.map')),*objs,'-o',elf],name+'-link.log')
        run([tools/'llvm-readelf.exe','-h','-l','-S','-s',elf],name+'-audit.txt')
        run([tools/'llvm-objdump.exe','-d',elf],name+'-disassembly.txt')
        return elf
    r5units=[*base,'firmware/typed200_r5/sha256.c','firmware/typed200_r5/runtime.c',
             'firmware/typed200_trace/service.c','firmware/typed200_trace/trace.c','firmware/typed200_timed/pmu.c',
             *['firmware/typed200_mvp/'+n for n in ('ownership.c','supervisor.c','platform.c','start.S')]]
    r5=build('r5',['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard'],r5units,'firmware/typed200_mvp/tcm.ld')
    entry,seg=segments(r5);assert entry==0
    b=r5.read_bytes();header=['#include <stdint.h>\n#include <stddef.h>\nstruct r5_segment {uint32_t address;size_t filesz,memsz;const uint8_t *data;};']
    for i,s in enumerate(seg):
        x=s['address'];assert (x<0x10000 and x+s['memsz']<=0x10000) or (0x20000<=x and x+s['memsz']<=0x30000)
        data=b[s['offset']:s['offset']+s['filesz']]
        header.append('static const uint8_t payload_%d[]={%s};'%(i,','.join(str(v) for v in data) if data else '0'))
    header.append('static const struct r5_segment r5_segments[]={'+','.join('{%d,%d,%d,payload_%d}'%(s['address'],s['filesz'],s['memsz'],i) for i,s in enumerate(seg))+'};')
    header.append('#define R5_SEGMENTS %d'%len(seg));(out/'r5_payload.h').write_text('\n'.join(header)+'\n')
    a53units=['firmware/typed200_mvp/a53.c','firmware/typed200_mvp/ownership.c','firmware/typed200_mvp/a53_start.S']
    a53=build('a53',['--target=aarch64-none-elf','-mcpu=cortex-a53','-mgeneral-regs-only'],a53units,'firmware/typed200_mvp/a53.ld',['-I'+str(out)])
    aentry,aseg=segments(a53);assert aentry==0xfffc0000
    for s in aseg:assert 0xfffc0000<=s['address'] and s['address']+s['memsz']<=0xfffec000
    # mmap tests execute actual A53 C handoff with mocked MMIO, not ARM instructions.
    hostub=[v for v in host if v!='-fsanitize=address,undefined']+['-fsanitize=undefined']
    run([*prefix,'gcc',*hostub,'-DMVP_HOST_TEST','-I'+rel,'firmware/typed200_mvp/a53.c','firmware/typed200_mvp/ownership.c','firmware/typed200_mvp/test_boot.c','-o',rel+'/boot'],'boot-compile.log')
    run([*prefix,rel+'/boot'],'boot.log')
    dis=(out/'r5-disassembly.txt').read_text();assert 'wfi' in dis and 'mvp_step' in dis and 'ty_exception' in dis
    assert 'c9, c13' in dis and 'c6, c1' in dis
    for p,h in preserved.items():assert sha(ROOT/p)==h,p
    used=[ROOT/u for u in set(r5units+a53units)]+list((ROOT/'firmware/typed200_mvp').rglob('*'))
    used += [ROOT/'src/sysone/v2/typed200_mvp.py',ROOT/'tests/test_typed200_mvp.py',ROOT/'firmware/typed_intent/typed_mailbox.c']
    source={p.relative_to(ROOT).as_posix():sha(p) for p in used if p.is_file()}
    source[Path(__file__).relative_to(ROOT).as_posix()]=sha(Path(__file__))
    report={'local_verification_passed':True,'target_executed':False,'deployed':False,'wcet_certified':False,
            'r5_entry':entry,'r5_segments':seg,'a53_entry':aentry,'a53_segments':aseg,
            'preserved_unique_files':len(preserved),'preserved_sha256':preserved,'source_sha256':source,
            'commands':commands,'evidence_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS separate cold-boot MVP: host fault injection, service/PMU regression, R5+A53 reset-entry ELF audits; baseline intact; NO target execution/WCET/deployment')
if __name__=='__main__':main()
