"""Build new PMU objects/image without invoking or mutating the frozen BSP build."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,shutil,subprocess,shlex,hashlib,argparse,re
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-ownership-v1'
OLD=ROOT/'build/v2/typed200-k26-boot-chain-v1'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--staged',required=True);opt=parser.parse_args()
 assert re.fullmatch(r'pmu-image-v[0-9]+',opt.attempt) and re.fullmatch(r'pmu-staged-v[0-9]+',opt.staged)
 out=BASE/opt.attempt;out.mkdir(exist_ok=False);src=out/'src';src.mkdir();obj=out/'objects';obj.mkdir()
 sdk=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw/lib/sw_apps/zynqmp_pmufw/src')
 entries=json.loads((OLD/'app-pmu-v1/build/compile_commands.json').read_text())
 commands=[]
 for entry in entries:
  name=Path(entry['file'].replace('\\','/')).name
  if name=='pmu_seal.c':continue
  original=sdk/name
  if name=='xpfw_core.c':original=BASE/opt.staged/'xpfw_core.c'
  assert original.exists(),name
  shutil.copyfile(original,src/name)
  args=shlex.split(entry['command'].replace('\\','/'),posix=True)
  args[args.index('-c')+1]='S:/'+(src/name).relative_to(ROOT).as_posix()
  args[args.index('-o')+1]='S:/'+(obj/(name+'.o')).relative_to(ROOT).as_posix()
  args += ['-I'+str(sdk),'-IS:/firmware/typed200_amp_ownership','-DXPFW_PRINT_VAL=0']
  commands.append((name,args))
 template=next(args for name,args in commands if name=='xpfw_core.c')
 for name in ['ownership.c','pmu_guard.c','pmu_lease.c']:
  shutil.copyfile(ROOT/'firmware/typed200_amp_ownership'/name,src/name)
  args=template[:];args[args.index('-c')+1]='S:/'+(src/name).relative_to(ROOT).as_posix()
  args[args.index('-o')+1]='S:/'+(obj/(name+'.o')).relative_to(ROOT).as_posix();commands.append((name,args))
 for h in ['ownership.h','pmu_guard.h','pmu_lease.h']:shutil.copyfile(ROOT/'firmware/typed200_amp_ownership'/h,src/h)
 for n in ['lscript.ld']:shutil.copyfile(OLD/'app-pmu-v1/src'/n,src/n)
 def compile_one(job):
  name,args=job
  r=subprocess.run(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
  (out/(name+'.log')).write_bytes(r.stdout)
  return dict(source=name,command=args,exit=r.returncode)
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(compile_one,commands))
 (out/'compile-receipt.json').write_text(json.dumps(results,indent=2)+'\n')
 assert all(r['exit']==0 for r in results),[r['source'] for r in results if r['exit']]
 # Exact pinned platform link recipe, new linker script and new output/map.
 ninja=(OLD/'app-pmu-v1/build/build.ninja').read_text()
 line=next(l.split(' = ',1)[1] for l in ninja.splitlines() if l.startswith('  LINK_LIBRARIES = '))
 libs=shlex.split(line.replace('\\','/'),posix=True)
 libs=[x.replace('S:/build/v2/typed200-k26-boot-chain-v1/app-pmu-v1/src/lscript.ld',
  'S:/'+(src/'lscript.ld').relative_to(ROOT).as_posix()) for x in libs]
 cmd=[template[0],*[('S:/'+p.relative_to(ROOT).as_posix()) for p in sorted(obj.glob('*.o'))],
  '-o','S:/'+(out/'typed200_amp_pmufw.elf').relative_to(ROOT).as_posix(),
  '-Wl,-Map=S:/'+(out/'typed200.map').relative_to(ROOT).as_posix(),'-Wl,-u,AmpPmuCommit',*libs]
 result=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
 (out/'link.log').write_bytes(result.stdout);assert result.returncode==0,'link.log'
 compiler=Path(template[0]);size=compiler.with_name('mb-size.exe');dump=compiler.with_name('mb-objdump.exe')
 for args,log in [([size,out/'typed200_amp_pmufw.elf'],'size.log'),([dump,'-d',out/'typed200_amp_pmufw.elf'],'disassembly.log')]:
  r=subprocess.run([str(x) for x in args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
  (out/log).write_bytes(r.stdout);assert r.returncode==0
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,compiled_units=len(results),
  elf_sha256=hashlib.sha256((out/'typed200_amp_pmufw.elf').read_bytes()).hexdigest(),link_command=cmd,
  bsp_read_only=True,pmu_main_loop_transport_integrated=True,atf_r5_activation_not_composed=True,deployable=False),indent=2)+'\n')
 print('PASS native PMU image:',len(results),'units; print disabled; retained trusted commit; NOT deployable')
if __name__=='__main__':main()
