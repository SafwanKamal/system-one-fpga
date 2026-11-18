"""Patch/build a new, pinned AMD 2025.2 secure monitor; no target action."""
from pathlib import Path
import json,shutil,subprocess,hashlib,difflib,argparse,re
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-ownership-v1'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 assert re.fullmatch(r'atf-staged-v[0-9]+',a.attempt)
 out=BASE/a.attempt;out.mkdir(exist_ok=False)
 receipt=json.loads((BASE/'atf-candidate-v1/source-receipt.json').read_text())
 original=BASE/'atf-candidate-v1'/('arm-trusted-firmware-'+receipt['commit'])
 tree=out/'source';shutil.copytree(original,tree)
 src=ROOT/'firmware/typed200_amp_ownership';dst=tree/'plat/xilinx/zynqmp/pm_service'
 for name in ['ownership.c','ownership.h','atf_guard.c','atf_guard.h']:shutil.copyfile(src/name,dst/name)
 path=dst/'zynqmp_pm_svc_main.c';before=path.read_text();after=before
 anchor='uint64_t pm_smc_handler(uint32_t smc_fid,';assert after.count(anchor)==1
 after=after.replace(anchor,'static uint64_t amp_original_pm_smc_handler(uint32_t smc_fid,')
 after=after.replace('#include <errno.h>','#include <errno.h>\n#include "atf_guard.h"',1)
 after+='''
/* Separate AMP candidate. Serialize policy activation with the whole PM
 * handler, including its direct secure RPU/TCM MMIO paths. */
uint64_t pm_smc_handler(uint32_t smc_fid, uint64_t x1, uint64_t x2, uint64_t x3,
                       uint64_t x4, const void *cookie, void *handle, uint64_t flags)
{
    if (!AmpAtfLockAllow(smc_fid, x1, x2, x3)) {
        AmpAtfUnlock();
        SMC_RET1(handle, (uint64_t)PM_RET_ERROR_ACCESS);
    }
    uint64_t result = amp_original_pm_smc_handler(smc_fid,x1,x2,x3,x4,cookie,handle,flags);
    AmpAtfUnlock();
    return result;
}
'''
 path.write_text(after)
 ipipath=tree/'plat/xilinx/common/ipi_mailbox_service/ipi_mailbox_svc.c'
 text=ipipath.read_text();needle='uint64_t ipi_smc_handler(uint32_t smc_fid,';assert text.count(needle)==1
 text=text.replace(needle,'static uint64_t amp_original_ipi_smc_handler(uint32_t smc_fid,')
 text=text.replace('#include <errno.h>','#include <errno.h>\n#include "atf_guard.h"',1)
 text+='''
uint64_t ipi_smc_handler(uint32_t smc_fid, uint64_t x1, uint64_t x2,
 uint64_t x3, uint64_t x4, const void *cookie, void *handle, uint64_t flags)
{
    if (!AmpAtfIpiLockAllow(smc_fid,x1,x2,x3,x4)) {
        AmpAtfUnlock();
        SMC_RET1(handle, -EPERM);
    }
    uint64_t result=amp_original_ipi_smc_handler(smc_fid,x1,x2,x3,x4,cookie,handle,flags);
    AmpAtfUnlock();
    return result;
}
'''
 ipipath.write_text(text)
 mk=tree/'plat/xilinx/zynqmp/libpm.mk';text=mk.read_text();anchor='$(eval $(call MAKE_LIB,pm))';assert text.count(anchor)==1
 mk.write_text(text.replace(anchor,'LIBPM_SRCS += plat/xilinx/zynqmp/pm_service/ownership.c plat/xilinx/zynqmp/pm_service/atf_guard.c\n'+anchor))
 # Retain the trusted activation symbol for later boot integration; no NS entry.
 mk=tree/'plat/xilinx/zynqmp/platform.mk';mk.write_text(mk.read_text()+'\nPLAT_INCLUDES += -Iplat/xilinx/zynqmp/pm_service\nTF_LDFLAGS += -Wl,--undefined=AmpAtfCommit\n')
 (out/'patch.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))))
 stubs=out/'stubs/lib';stubs.mkdir(parents=True)
 (stubs/'spinlock.h').write_text('#include <assert.h>\ntypedef unsigned spinlock_t;\nextern unsigned amp_test_lock;\nstatic inline void spin_lock(spinlock_t *p){(void)p;assert(!amp_test_lock);amp_test_lock=1;}\nstatic inline void spin_unlock(spinlock_t *p){(void)p;assert(amp_test_lock);amp_test_lock=0;}\n')
 wslroot='/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:];rel=out.relative_to(ROOT).as_posix()
 prefix=['wsl','-d','Ubuntu-24.04','--cd',wslroot,'--'];commands=[]
 def run(cmd,name,timeout=600):
  result=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  (out/name).write_bytes(result.stdout);commands.append(dict(command=[str(x) for x in cmd],exit=result.returncode))
  assert result.returncode==0,name
  return result.stdout.decode(errors='replace')
 print(run([*prefix,'gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic',
  '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+rel+'/stubs',
  '-Ifirmware/typed200_amp_ownership','firmware/typed200_amp_ownership/ownership.c',
  'firmware/typed200_amp_ownership/atf_guard.c','firmware/typed200_amp_ownership/test_atf_guard.c',
  '-o',rel+'/test-atf'],'host-compile.log'),flush=True)
 print(run([*prefix,rel+'/test-atf'],'host-run.log'),flush=True)
 # GNU make resolves CURDIR and cannot build this tree below the spaced Windows
 # workspace. Use a fresh actual Linux directory; preserve candidate source copy.
 temporary='/tmp/sysone-amp-'+a.attempt+'-'+receipt['commit'][:8]
 run([*prefix,'test','!','-e',temporary],'temporary-unused.log')
 archive=BASE/'atf-candidate-v1/source.tar.gz'
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256']
 run([*prefix,'mkdir',temporary],'temporary-create.log')
 run([*prefix,'tar','-xzf',wslroot+'/'+archive.relative_to(ROOT).as_posix(),'-C',temporary,'--strip-components=1'],'temporary-extract.log')
 overlays=['plat/xilinx/zynqmp/pm_service/'+x for x in
  ['ownership.c','ownership.h','atf_guard.c','atf_guard.h','zynqmp_pm_svc_main.c']]
 overlays += ['plat/xilinx/common/ipi_mailbox_service/ipi_mailbox_svc.c','plat/xilinx/zynqmp/libpm.mk','plat/xilinx/zynqmp/platform.mk']
 for i,name in enumerate(overlays):run([*prefix,'cp',wslroot+'/'+rel+'/source/'+name,temporary+'/'+name],f'overlay-{i}.log')
 build=[*prefix,'make','-C',temporary,'-j4','PLAT=zynqmp','CROSS_COMPILE=aarch64-linux-gnu-',
  'DEBUG=0','ZYNQMP_CONSOLE=cadence1','ZYNQMP_WDT_RESTART=0','bl31']
 print('Building separate ATF candidate',flush=True);run(build,'build.log')
 run([*prefix,'cp','-a',temporary+'/build',wslroot+'/'+rel+'/native-build'],'build-preserve.log')
 elf=out/'native-build/zynqmp/release/bl31/bl31.elf';assert elf.exists()
 run([*prefix,'aarch64-linux-gnu-readelf','-lW',str(elf.relative_to(ROOT)).replace('\\','/')],'segments.log')
 run([*prefix,'aarch64-linux-gnu-nm','-n',str(elf.relative_to(ROOT)).replace('\\','/')],'symbols.log')
 (out/'receipt.json').write_text(json.dumps(dict(passed=True,commit=receipt['commit'],commands=commands,
  elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),activation_not_integrated=True,
  secure_boot_and_all_service_paths_not_yet_composed=True,deployable=False),indent=2)+'\n')
 print('PASS native ATF built; NOT deployable; trusted activation and boot composition pending',flush=True)
if __name__=='__main__':main()
