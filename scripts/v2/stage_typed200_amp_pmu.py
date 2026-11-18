"""Patch fresh vendor copies only; compile dispatcher against pinned BSP."""
from pathlib import Path
import json,hashlib,subprocess,os,argparse,re
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/v2/typed200-amp-ownership-v1'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 assert re.fullmatch(r'pmu-staged-v[0-9]+',a.attempt)
 out=OUT/a.attempt;out.mkdir(exist_ok=False)
 sdk=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw/lib/sw_apps/zynqmp_pmufw/src')
 original=(sdk/'xpfw_core.c').read_text();text=original
 patches=[('#include "pm_qspi.h"','#include "pm_qspi.h"\n#include "pmu_guard.h"\n#include "pmu_lease.h"'),
 ('CorePtr->ModList[Idx].EventHandler != NULL)) {',
  'CorePtr->ModList[Idx].EventHandler != NULL) &&\n\t\t\t    AmpPmuEvent(&CorePtr->ModList[Idx], EventId)) {'),
 ('\t\t\t/* Dispatch based on IPI ID',
  '\t\t\tif (AmpPmuLeaseIpi(IpiNum, Ipi0InstPtr->Config.TargetList[MaskIndex].Mask,\n'
  '\t\t\t              Payload, XPFW_IPI_MAX_MSG_LEN)) { CallCount++; continue; }\n'
  '\t\t\tif (AmpPmuIpi(IpiNum, Ipi0InstPtr->Config.TargetList[MaskIndex].Mask,\n'
  '\t\t\t              Payload, XPFW_IPI_MAX_MSG_LEN)) { CallCount++; continue; }\n'
  '\t\t\t/* Dispatch based on IPI ID'),
 ('\t\t\t\tmb_sleep();',
  '\t\t\t\t/* AMP candidate polls deferred closure. Sleeping here could lose\n'
  '\t\t\t\t * a request interrupt arriving after the previous loop poll.\n'
  '\t\t\t\t * PMU idle-power impact is not yet measured. */'),
 ('\t\t#ifdef ENABLE_SCHEDULER\n\t\t\tif((u32)TRUE == CorePtr->Scheduler.Enabled){',
  '\t\t\tAmpPmuLeasePoll();\n\t\t#ifdef ENABLE_SCHEDULER\n\t\t\tif(!AmpPmuClosed() && (u32)TRUE == CorePtr->Scheduler.Enabled){')]
 for old,new in patches:assert text.count(old)==1,old;text=text.replace(old,new)
 assert 'mb_sleep();' not in text
 (out/'xpfw_core.c').write_text(text)
 # Independent mocks only for hardware API boundaries; actual guard/owner C used.
 stubs=out/'stubs';stubs.mkdir()
 (stubs/'xpfw_default.h').write_text('#ifndef AMP_TEST_DEFAULT\n#define AMP_TEST_DEFAULT\n#include <stdint.h>\ntypedef uint32_t u32;typedef uint64_t u64;\n#define XST_PM_NO_ACCESS 2002u\n#endif\n')
 (stubs/'xpfw_module.h').write_text('#ifndef AMP_TEST_MODULE\n#define AMP_TEST_MODULE\ntypedef struct {unsigned ModId;} XPfw_Module_t;\n#endif\n')
 (stubs/'pm_defs.h').write_text('#include "xpfw_default.h"\n')
 (stubs/'mb_interface.h').write_text('#include <stdint.h>\nuint32_t mfmsr(void);\nvoid microblaze_disable_interrupts(void);\nvoid microblaze_enable_interrupts(void);\n')
 (stubs/'xpfw_ipi_manager.h').write_text('#include "xpfw_default.h"\n#define XPFW_IPI_MAX_MSG_LEN 8u\n#define XIPIPSU_BUF_TYPE_RESP 1u\nextern void *Ipi0InstPtr;\nint XIpiPsu_WriteMessage(void *,u32,u32 *,u32,unsigned);\n')
 wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:];rel=out.relative_to(ROOT).as_posix()
 src='firmware/typed200_amp_ownership';commands=[]
 def run(cmd,name):
  result=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
  (out/name).write_bytes(result.stdout);commands.append(dict(command=[str(x) for x in cmd],exit=result.returncode,log=name))
  assert result.returncode==0,name
  return result.stdout.decode(errors='replace')
 prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--']
 print(run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
  '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+rel+'/stubs','-I'+src,
  src+'/ownership.c',src+'/pmu_guard.c',src+'/test_pmu_guard.c','-o',rel+'/test-guard'],'host-compile.log'))
 print(run([*prefix,rel+'/test-guard'],'host-run.log'))
 print(run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
  '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+rel+'/stubs','-I'+src,
  src+'/ownership.c',src+'/pmu_guard.c',src+'/pmu_lease.c',src+'/test_pmu_lease.c',
  '-o',rel+'/test-lease'],'lease-compile.log'))
 print(run([*prefix,rel+'/test-lease'],'lease-run.log'))
 # Reuse exact compiler/ABI and read-only BSP from the sealed K26 chain.
 old=ROOT/'build/v2/typed200-k26-boot-chain-v1/app-pmu-v1/build/compile_commands.json'
 entry=next(e for e in json.loads(old.read_text()) if e['file'].endswith('xpfw_core.c'))
 # Parse Windows commandline using command-line-aware splitting; all original
 # tokens use no-space S: paths. Preserve defines/ISA/specs, replace source/output.
 import shlex
 args=shlex.split(entry['command'].replace('\\','/'),posix=True)
 cindex=args.index('-c');oindex=args.index('-o');compiler=args[0]
 base=args[:];base[cindex+1]='S:/'+rel+'/xpfw_core.c';base[oindex+1]='S:/'+rel+'/xpfw_core.o'
 base += ['-I'+str(sdk),'-IS:/firmware/typed200_amp_ownership']
 run(base,'native-core-compile.log')
 for name in ('ownership','pmu_guard','pmu_lease'):
  cmd=base[:];cmd[cindex+1]='S:/'+src+'/'+name+'.c';cmd[oindex+1]='S:/'+rel+'/'+name+'.o'
  run(cmd,'native-'+name+'-compile.log')
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,commands=commands,
  original_core_sha256=hashlib.sha256((sdk/'xpfw_core.c').read_bytes()).hexdigest(),
  patched_core_sha256=hashlib.sha256((out/'xpfw_core.c').read_bytes()).hexdigest(),
  pmu_main_loop_transport_integrated=True,atf_r5_activation_not_composed=True,deployable=False),indent=2)+'\n')
 print('PASS staged native dispatcher/PMU deferred lease objects; ATF/R5 boot activation still unbound')
if __name__=='__main__':main()
