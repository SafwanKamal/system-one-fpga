"""Patch only generated candidate copies; never the AMD installation or frozen MVP."""
from pathlib import Path
import hashlib, json, shutil, difflib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2/typed200-k26-boot-chain-v1'
SRC=Path(__file__).resolve().parent
records=[]
def patch(path,old,new):
    before=path.read_text()
    assert before.count(old)==1,(path,old)
    after=before.replace(old,new)
    records.append({'path':str(path.relative_to(ROOT)),
        'before':hashlib.sha256(before.encode()).hexdigest(),
        'after':hashlib.sha256(after.encode()).hexdigest(),
        'diff':''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True)))})
    path.write_text(after)
for app,files in [('app-pmu-v1',['pmu_seal.c','pmu_seal.h','seal_policy.h']),
                  ('app-fsbl-v1',['fsbl_final.c','fsbl_final.h','seal_policy.h'])]:
    for name in files:shutil.copyfile(SRC/name,OUT/app/'src'/name)
p=OUT/'app-pmu-v1/src/xpfw_core.c'
patch(p,'#include "pm_qspi.h"','#include "pm_qspi.h"\n#include "pmu_seal.h"')
patch(p,'CorePtr->ModList[Idx].EventHandler != NULL)) {',
        'CorePtr->ModList[Idx].EventHandler != NULL) &&\n'
        '\t\t\t    TypedBootEvent(&CorePtr->ModList[Idx], EventId)) {')
patch(p,'\t\t\t/* Dispatch based on IPI ID',
        '\t\t\tif (TypedBootIpi(IpiNum, Ipi0InstPtr->Config.TargetList[MaskIndex].Mask,\n'
        '\t\t\t                 Payload, XPFW_IPI_MAX_MSG_LEN)) { CallCount++; continue; }\n'
        '\t\t\t/* Dispatch based on IPI ID')
patch(p,'if((u32)TRUE == CorePtr->Scheduler.Enabled){',
        'if(!TypedBootClosed() && (u32)TRUE == CorePtr->Scheduler.Enabled){')
patch(p,'\t\t} while (TRUE);','\t\t\tTypedBootService();\n\t\t} while (TRUE);')
p=OUT/'app-fsbl-v1/src/xfsbl_handoff.c'
patch(p,'#include "xfsbl_bs.h"','#include "xfsbl_bs.h"\n#include "fsbl_final.h"')
patch(p,'\tXFsbl_Exit((PTRSIZE) HandoffAddress, Flags);',
        '\tTypedBootFinal(HandoffAddress, Flags);\n\tXFsbl_Exit((PTRSIZE) HandoffAddress, Flags);')
defs={
 'app-pmu-v1':['K26_SOM','ENABLE_FPGA_LOAD_VAL=0','ENABLE_FPGA_READ_CONFIG_DATA_VAL=0',
 'ENABLE_FPGA_READ_CONFIG_REG_VAL=0','USE_DDR_FOR_APU_RESTART_VAL=0',
 'ENABLE_UNUSED_RPU_PWR_DWN_VAL=0','ENABLE_RECOVERY_VAL=0',
 'ENABLE_RECOVERY_RESET_SYSTEM_VAL=0','ENABLE_RECOVERY_RESET_PS_ONLY_VAL=0',
 'ENABLE_ESCALATION_VAL=0','ENABLE_WDT_VAL=0','ENABLE_DDR_SR_WR_VAL=0',
 'ENABLE_RPU_RUN_MODE_VAL=0'],
 'app-fsbl-v1':['K26_SOM','FSBL_USB_EXCLUDE_VAL=1','FSBL_NAND_EXCLUDE_VAL=1',
 'FSBL_EARLY_HANDOFF_EXCLUDE_VAL=1']}
for app,flags in defs.items():
    p=OUT/app/'src/UserConfig.cmake'
    patch(p,'set(USER_COMPILE_DEFINITIONS\n""\n)',
          'set(USER_COMPILE_DEFINITIONS\n'+''.join('"'+f+'"\n' for f in flags)+')')
    patch(p,'set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -Os)')
    patch(p,'set(USER_LINK_OTHER_FLAGS\n)',
          'set(USER_LINK_OTHER_FLAGS "-Wl,-Map=${CMAKE_BINARY_DIR}/typed200.map")')
(OUT/'staged-patches.json').write_text(json.dumps({'definitions':defs,'patches':records},indent=2))
print('Staged',len(records),'exact-match patches; vendor installation unchanged')
