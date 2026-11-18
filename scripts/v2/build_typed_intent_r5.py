"""Cross-compile isolated bounded head/bridge objects; never build/deploy a BSP."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',default='typed-intent-r5-service-v3')
    p.add_argument('--tools',type=Path,default=Path('C:/AMDDesignTools/2025.2/win64/tools/clang-16/bin'))
    p.add_argument('--dlls',type=Path,default=Path('C:/AMDDesignTools/2025.2/Vitis/lib/win64.o'))
    a=p.parse_args();out=ROOT/'build/v2'/a.name;out.mkdir(exist_ok=False)
    env=os.environ.copy();env['PATH']=str(a.dlls)+os.pathsep+str(a.tools)+os.pathsep+env['PATH']
    compiler=a.tools/'clang.exe';objdump=a.tools/'llvm-objdump.exe';linker=a.tools/'ld.lld.exe'
    flags=['--target=arm-none-eabi','-mcpu=cortex-r5','-mfpu=vfpv3-d16','-mfloat-abi=hard',
           '-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-ffreestanding',
           '-fno-builtin','-fno-fast-math','-ffp-contract=off','-fstack-usage']
    commands=[[str(compiler),'--version']]
    for unit in ['typed_intent','typed_mailbox']:
        commands.append([str(compiler),*flags,'-c',f'firmware/typed_intent/{unit}.c',
                         '-o',str(out/f'{unit}.o')])
    commands += [[str(linker),'-r',str(out/'typed_intent.o'),str(out/'typed_mailbox.o'),
                  '-o',str(out/'typed_service.o')],
                 [str(objdump),'-h','-t','-r',str(out/'typed_service.o')],
                 [str(objdump),'-d',str(out/'typed_service.o')]]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/f'command-{i}.log').write_bytes(r.stdout)
        if r.returncode:raise RuntimeError(f'Command {i} failed')
    audit=(out/'command-4.log').read_text();assert '*UND*' not in audit
    stack=(out/'typed_intent.su').read_text()+(out/'typed_mailbox.su').read_text()
    usage={line.split('\t')[0].rsplit(':',1)[-1]:int(line.split('\t')[1]) for line in stack.splitlines()}
    sources=[p for p in (ROOT/'firmware/typed_intent').rglob('*') if p.is_file() and p.name!='test_runner.c']
    receipt={'passed':True,'target':'Cortex-R5, ARM EABI, hard-float VFPv3-D16',
        'compiler_sha256':sha(compiler),'commands':commands,'stack_bytes_per_function':usage,
        'bridge_core_plus_head_stack_bytes':usage['ti_bridge_core']+usage['ti_head'],
        'undefined_symbols':[],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'artifact_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'limits':['Relocatable object only; no BSP/startup/linker map or TCM residency proof',
                  'No target execution, WCET, interruption or bus-service bound',
                  'Stack excludes caller, exception, interrupt and future MMIO driver frames']}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS R5 object; no undefined symbols; nested bridge/head stack',receipt['bridge_core_plus_head_stack_bytes'])
if __name__=='__main__':main()
