"""Build, inspect and host-check a reset-entry R5/TCM candidate; never execute it."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-r5-elf-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    cmds=[]
    def run(cmd,filename):
        r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/filename).write_bytes(r.stdout);cmds.append(cmd)
        if r.returncode:raise RuntimeError(f'Failed {filename}; preserve attempt')
        return r.stdout.decode().strip()
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
    run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fno-fast-math','-ffp-contract=off',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','firmware/typed_intent/typed_intent.c',
        'firmware/typed200_v2/typed200.c','firmware/typed200_r5/service.c','firmware/typed200_r5/test_service.c',
        '-o',rel+'/service-test'],'host-compile.log')
    run([*prefix,rel+'/service-test'],'host-run.log')
    run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
        '-fsanitize=address,undefined','firmware/typed200_r5/sha256.c','firmware/typed200_r5/test_sha.c',
        '-o',rel+'/sha-test'],'sha-compile.log')
    lengths=[0,1,3,55,56,63,64,65,127,1000]
    for n in lengths:
        p=out/f'sha-{n}.bin';p.write_bytes(bytes((i*37+11)%256 for i in range(n)))
        actual=run([*prefix,rel+'/sha-test',p.relative_to(ROOT).as_posix()],f'sha-{n}.log');assert actual==sha(p)
    image=ROOT/'export/v2/image/minilm-l12-v1-kr260/minilm-l12-v1-kr260.img'
    actual=run([*prefix,rel+'/sha-test',image.relative_to(ROOT).as_posix()],'sha-model.log')
    assert actual==sha(image)=='4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb'
    flags=['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard','-O2',
        '-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-fast-math','-ffp-contract=off',
        '-ffunction-sections','-fdata-sections','-fstack-usage']
    units=['firmware/typed_intent/typed_intent.c','firmware/typed200_v2/typed200.c',
        *[f'firmware/typed200_r5/{n}' for n in ['sha256.c','service.c','platform.c','runtime.c','start.S']]]
    objects=[]
    for i,unit in enumerate(units):
        obj=out/f'unit-{i}.o';objects.append(str(obj))
        run([str(tools/'clang.exe'),*flags,'-c',unit,'-o',str(obj)],f'compile-{i}.log')
    elf=out/'typed200-r5.elf'
    run([str(tools/'ld.lld.exe'),'-T','firmware/typed200_r5/tcm.ld','--gc-sections','--no-undefined',
        '-Map='+str(out/'typed200-r5.map'),*objects,'-o',str(elf)],'link.log')
    run([str(tools/'llvm-readelf.exe'),'-h','-l','-S','-s',str(elf)],'elf-audit.txt')
    run([str(tools/'llvm-objdump.exe'),'-d',str(elf)],'disassembly.txt')
    (out/'receipt.json').write_text(json.dumps({'passed':True,'host_service_sanitizers':['address','undefined'],
        'sha_fixture_lengths':lengths,'full_model_sha256_verified':actual,'elf_linked':True,
        'target_executed':False,'wcet_certified':False,'boot_loader_prerequisites':['R5_0 split TCM initialized','reset ARM privileged entry','MPU/caches off','PS DDR/PL initialized'],
        'commands':cmds,'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in
          [ROOT/u for u in units]+[p for p in (ROOT/'firmware/typed200_r5').iterdir() if p.suffix in ('.c','.h','.S','.ld')]},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('PASS service policy/sanitizers, 11 SHA vectors including full model, linked R5 reset-entry ELF; NOT target executed')
if __name__=='__main__':main()
