"""Host-check and R5-link ABI successor without changing the frozen head code."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-firmware-v1');a=ap.parse_args()
    out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False);rel=out.relative_to(ROOT).as_posix()
    previous=ROOT/'build/v2/typed-intent-r5-sealed-v4'
    old=json.loads((previous/'receipt.json').read_text())
    for p,h in old['source_sha256'].items():assert sha(ROOT/p)==h,p
    assert sha(previous/'typed_service.o')==old['artifact_sha256']['typed_service.o']
    tools=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin')
    env=os.environ.copy();env['PATH']='C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'+os.pathsep+str(tools)+os.pathsep+env['PATH']
    wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
    commands=[['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--','gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
        '-fno-fast-math','-ffp-contract=off','-fsanitize=address,undefined','-fno-sanitize-recover=all',
        'firmware/typed_intent/typed_intent.c','firmware/typed_intent/typed_mailbox.c',
        'firmware/typed200/typed200.c','firmware/typed200/test_driver.c','-o',rel+'/driver-test'],
        ['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--',rel+'/driver-test'],
        [str(tools/'clang.exe'),'--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard',
        '-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-ffreestanding','-fno-builtin','-fno-fast-math',
        '-ffp-contract=off','-fstack-usage','-c','firmware/typed200/typed200.c','-o',str(out/'typed200.o')],
        [str(tools/'ld.lld.exe'),'-r',str(previous/'typed_service.o'),str(out/'typed200.o'),'-o',str(out/'typed200_service.o')],
        [str(tools/'llvm-objdump.exe'),'-h','-t','-r',str(out/'typed200_service.o')],
        [str(tools/'llvm-objdump.exe'),'-d',str(out/'typed200_service.o')]]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/f'command-{i}.log').write_bytes(r.stdout)
        if r.returncode:raise RuntimeError(f'Command {i} failed; preserve logs')
    assert '*UND*' not in (out/'command-4.log').read_text()
    sources=[p for p in (ROOT/'firmware/typed200').rglob('*') if p.is_file()]
    (out/'receipt.json').write_text(json.dumps({'passed':True,'sanitizers':['address','undefined'],
        'r5_relocatable_link':True,'undefined_symbols':0,'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'frozen_head_service_sha256':sha(previous/'typed_service.o'),'compiler_sha256':sha(tools/'clang.exe'),
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'commands':commands,'limits':['no BSP or TCM map','no target execution or WCET','DDR/cache/mapping ownership is a deployment assumption']},indent=2)+'\n')
    print('PASS typed200 host driver + sanitizers and R5 relocatable service; no undefined symbols')
if __name__=='__main__':main()
