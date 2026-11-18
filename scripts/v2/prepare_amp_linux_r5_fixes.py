"""Stage narrowly scoped exact-kernel fixes and regress their actual functions."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
from check_amp_linux_r5_driver import function, SMC_PREFIX

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'


def main():
    out = BASE/'kernel-fixes-v1'
    out.mkdir(exist_ok=False)
    source = BASE/'kernel-source-v3'
    edits = {
        'drivers/firmware/xilinx/zynqmp.c':('*rpu_mode = ret_payload[0];','*rpu_mode = ret_payload[1];'),
        'drivers/firmware/xilinx/zynqmp-debug.c':('u32 pm_api_ret[4] = {0, 0, 0, 0};','u32 pm_api_ret[PAYLOAD_ARG_CNT] = {0};'),
    }
    patch = []
    records = {}
    for name,(old,new) in edits.items():
        before = (source/name).read_text()
        assert before.count(old) == 1
        after = before.replace(old,new)
        p = out/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(after.encode())
        patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                                         fromfile='a/'+name,tofile='b/'+name))
        records[name]=dict(before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest())
    (out/'fixes.patch').write_bytes(''.join(patch).encode())
    original = (source/'drivers/firmware/xilinx/zynqmp.c').read_text()
    fixed = (out/'drivers/firmware/xilinx/zynqmp.c').read_text()
    # Reuse the actual SMC function; the mock only supplies firmware responses.
    prefix = SMC_PREFIX.replace('struct arm_smccc_res {u64 a0,a1,a2,a3;};',
        'struct arm_smccc_res {u64 a0,a1,a2,a3;}; static u32 response_mode=1,response_status;')
    prefix = prefix.replace('0x100000000ULL,0x300000002ULL,0x500000004ULL,6',
        '((u64)response_mode<<32)|response_status,0x300000002ULL,0x500000004ULL,6')
    prefix = prefix.replace('return status;','return status?-13:0;')
    harness = prefix + '\n#define PAYLOAD_ARG_CNT 7\n#define PM_IOCTL 34\n#define IOCTL_GET_RPU_OPER_MODE 0\n#define XST_PM_SUCCESS 0\nenum rpu_oper_mode { LOCKSTEP=0,SPLIT=1 };\n'
    harness += function(original,'do_fw_call_smc')
    harness += '\nstatic int zynqmp_pm_invoke_fn(u32 api,u32 *out,u32 count,...) { assert(api==34 && count==2);return do_fw_call_smc(out,0); }\n'
    harness += function(original,'zynqmp_pm_get_rpu_mode').replace('zynqmp_pm_get_rpu_mode','original_get_mode')
    harness += '\n'+function(fixed,'zynqmp_pm_get_rpu_mode')
    harness += r'''
int main(void) {
 int cases=0; enum rpu_oper_mode mode;
 response_status=0;response_mode=1;mode=0;
 assert(original_get_mode(7,&mode)==0 && mode==0);
 for(u32 m=0;m<2;m++) for(u32 s=0;s<3;s++) {
  response_mode=m;response_status=s;mode=77;
  int ret=zynqmp_pm_get_rpu_mode(7,&mode);
  if(s) assert(ret==-13 && mode==77); else assert(ret==0 && mode==m);
  cases++;
 }
 response_status=0;response_mode=1;
 u32 storage[10]={0,0,0,0,0,0,0,0xabad1dea,0xabad1dea,0xabad1dea};
 assert(do_fw_call_smc(storage,0)==0);
 assert(storage[1]==1 && storage[6]==6);
 assert(storage[7]==0xabad1dea && storage[8]==0xabad1dea && storage[9]==0xabad1dea);
 printf("PASS %d mode/error cases and seven-word output guard; original split-mode misread reproduced\n",cases);
}
'''
    (out/'regression.c').write_bytes(harness.encode())
    wsl='/mnt/c/'+str(out.resolve())[3:].replace('\\','/')
    for args,name in [(['gcc','-std=c11','-O2',wsl+'/regression.c','-o',wsl+'/regression'],'compile.log'),
                      ([wsl+'/regression'],'regression.log')]:
        r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
        (out/name).write_bytes(r.stdout)
        assert not r.returncode,name
    receipt=dict(passed=True,exact_source_package='6.8.0-1036.37',files=records,
                 changes='mode output slot and debugfs response-buffer bound only',
                 original_split_misread_reproduced=True,fixed_mode_and_buffer_regression_passed=True,
                 kernel_built=False,target_kernel_changed=False,live_startup_admitted=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print((out/'regression.log').read_text().strip())


if __name__=='__main__':main()
