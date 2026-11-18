"""Snapshot primary startup/register sources into a separate ARM MVP candidate."""
from pathlib import Path
import ast,hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'firmware/typed200_mvp'
VENDOR=Path('C:/AMDDesignTools/2025.2/Vitis/data/embeddedsw')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    out=OUT/'reference';out.mkdir(parents=True,exist_ok=False)
    refs={n:VENDOR/'lib/sw_apps/zynqmp_pmufw/src'/n for n in ('crl_apb.h','crf_apb.h','rpu.h','pmu_global.h')}
    refs.update({n:VENDOR/'lib/sw_apps/zynqmp_fsbl/src'/n for n in ('xfsbl_initialization.c','xfsbl_handoff.c','xfsbl_hw.h')})
    refs['boot.S']=VENDOR/'lib/bsp/standalone_v9_4/src/arm/cortexr5/gcc/boot.S'
    refs['psu_init.c']=ROOT/'build/v2/typed200-row-range-csa-physical-v1/sysone_v2_kr260.gen/sources_1/bd/system/ip/system_zynq_ultra_ps_e_0_0/psu_init.c'
    for n,p in refs.items():shutil.copyfile(p,out/n)
    definitions={}
    for n in ('crl_apb.h','crf_apb.h','rpu.h','pmu_global.h','xfsbl_hw.h'):
        for name,value in re.findall(r'^#define\s+(\w+)\s+([^\n]+)',(out/n).read_text(),re.M):
            definitions.setdefault(name,value.split('/*')[0].strip())
    def value(name):
        s=re.sub(r'\(\s*u(?:32|64)\s*\)','',definitions[name]);s=re.sub(r'(?<=[0-9A-Fa-f])[UuLl]+\b','',s)
        for ident in set(re.findall(r'\b[A-Z_][A-Z_0-9]*\b',s)):
            s=re.sub(r'\b'+ident+r'\b',str(value(ident)),s)
        node=ast.parse(s,mode='eval')
        def ev(n):
            if isinstance(n,ast.Expression):return ev(n.body)
            if isinstance(n,ast.Constant) and isinstance(n.value,int):return n.value
            if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):return ev(n.left)+ev(n.right)
            raise ValueError((name,s))
        return ev(node)
    names=['CRL_APB_'+n for n in ('IOPLL_CTRL','IOPLL_FRAC_CFG','RPLL_CTRL','RPLL_FRAC_CFG','PLL_STATUS','CPU_R5_CTRL','PL0_REF_CTRL','PL1_REF_CTRL','RESET_REASON','RST_LPD_IOU0','RST_LPD_IOU2','RST_LPD_TOP','RST_LPD_DBG')]
    names+=['CRF_APB_RST_FPD_TOP','CRF_APB_RST_FPD_APU','CRF_APB_DPDMA_REF_CTRL','RPU_RPU_GLBL_CNTL','RPU_RPU_0_CFG','RPU_RPU_1_CFG','PMU_GLOBAL_PWR_STATE']
    for prefix in ('CRL_APB_RST_LPD_IOU0_','CRL_APB_RST_LPD_IOU2_','CRL_APB_RST_LPD_TOP_','CRF_APB_RST_FPD_TOP_'):
        names.extend(n for n in definitions if n.startswith(prefix) and n.endswith('_MASK'))
    names.extend(n for n in definitions if n.startswith('ADMA_CH0_ZDMA_CH_') and ('MASK' not in n and 'MODE_' not in n and 'POINT_TYPE_' not in n and 'STATE_' not in n))
    header='/* Numeric definitions extracted from pinned AMD primary sources in reference/. */\n#ifndef MVP_VENDOR_REGS_H\n#define MVP_VENDOR_REGS_H\n'
    for n in sorted(set(names)):header+=f'#define V_{n} UINT32_C(0x{value(n):08x})\n'
    header+='#endif\n';(OUT/'vendor_regs.h').write_text(header)
    (out/'sources.json').write_text(json.dumps({n:{'source':str(p),'sha256':sha(p),'snapshot_sha256':sha(out/n)} for n,p in refs.items()},indent=2)+'\n')
    print('PASS separate MVP primary-source snapshots and numeric register definitions')
if __name__=='__main__':main()
