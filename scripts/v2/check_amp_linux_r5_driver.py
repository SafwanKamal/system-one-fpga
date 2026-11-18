"""Compile actual pinned driver callbacks with PM-call fault injection."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/v2/typed200-amp-linux-r5-v1'
SOURCE = BASE/'kernel-source-v3'


def function(text, name):
    match = re.search(r'(?m)^(?:static )?(?:noinline )?int '+name+r'\(',text)
    assert match, name
    begin = text.index('{',match.start())
    depth = 1
    end = begin+1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}')
        end += 1
    return text[match.start():end]


PREFIX = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32; typedef uint64_t u64; typedef uint8_t u8;
#define noinline
#define lower_32_bits(x) ((u32)(x))
#define upper_32_bits(x) ((u32)((u64)(x)>>32))
#define EINVAL 22
#define XST_PM_SUCCESS 0
#define PAYLOAD_ARG_CNT 7
#define PM_IOCTL 34
#define IOCTL_GET_RPU_OPER_MODE 0
#define dev_dbg(...) ((void)0)
#define ZYNQMP_PM_REQUEST_ACK_NO 1
#define ZYNQMP_PM_REQUEST_ACK_BLOCKING 2
enum rpu_oper_mode { PM_RPU_MODE_LOCKSTEP=0, PM_RPU_MODE_SPLIT=1 };
enum rpu_tcm_comb { PM_RPU_TCM_SPLIT=0, PM_RPU_TCM_COMB=1 };
enum rpu_boot_mem { PM_RPU_BOOTMEM_LOVEC=0, PM_RPU_BOOTMEM_HIVEC=1 };
enum { SOC_ZYNQMP=0, SOC_VERSAL=1, SOC_VERSAL_NET=2 };
struct device { struct device *parent; };
struct soc { int soc_type; };
struct xlnx_rpu_rproc { u32 pnode_id; struct soc *soc_data; };
struct rproc { void *priv; u64 bootaddr; struct device dev; };
struct call { int op; u32 node,a,b,c; };
static struct call calls[16]; static int used,cases;
static int query_ret,down_ret,wake_ret,set_ret,tcm_ret;
static u32 node_status,mode;
static void call(int op,u32 node,u32 a,u32 b,u32 c) {
 assert(used<16); calls[used++]=(struct call){op,node,a,b,c};
}
static int zynqmp_pm_get_rpu_mode(u32 node,enum rpu_oper_mode *out) {
 call(1,node,0,0,0); *out=mode; return query_ret;
}
static int zynqmp_pm_set_rpu_mode(u32 node,enum rpu_oper_mode v) {
 call(2,node,v,0,0); return set_ret;
}
static int zynqmp_pm_set_tcm_config(u32 node,enum rpu_tcm_comb v) {
 call(3,node,v,0,0); return tcm_ret;
}
static int zynqmp_pm_get_node_status(u32 node,u32 *status,void *a,void *b) {
 call(4,node,0,0,0); *status=node_status; return query_ret;
}
static int zynqmp_pm_force_pwrdwn(u32 node,u32 ack) {
 call(5,node,ack,0,0); return down_ret;
}
static int zynqmp_pm_request_wake(u32 node,int set,u64 address,u32 ack) {
 call(6,node,set,(u32)address,ack); return wake_ret;
}
static void clear(void) {used=0;query_ret=down_ret=wake_ret=set_ret=tcm_ret=0;}
'''

MAIN = r'''
int main(void) {
 struct soc soc={SOC_ZYNQMP}; struct xlnx_rpu_rproc z={7,&soc};
 struct rproc r={&z,0,{0}};
 const u64 addresses[]={0,0x63f00000,0xf0000000,0xffff0000};
 for(int s=0;s<3;s++) for(int a=0;a<4;a++) for(int status=0;status<2;status++)
 for(int q=0;q<2;q++) for(int d=0;d<2;d++) for(int w=0;w<2;w++) {
  clear(); soc.soc_type=s; r.bootaddr=addresses[a];node_status=status;
  query_ret=q?-13:0;down_ret=d?-22:0;wake_ret=w?-5:0;
  int ret=xlnx_rpu_rproc_start(&r);cases++;
  assert(calls[0].op==4 && calls[0].node==7);
  int stop_needed=status && s!=SOC_VERSAL_NET;
  if(q){assert(ret==-13 && used==1);continue;}
  if(stop_needed){assert(calls[1].op==5 && calls[1].a==2);if(d){assert(ret==-22 && used==2);continue;}}
  assert(ret==wake_ret && used==(stop_needed?3:2));
  struct call last=calls[used-1];
  assert(last.op==6 && last.node==7 && last.a==1 && last.c==1);
  assert(last.b==(s==SOC_VERSAL_NET?0:((addresses[a]&0xf0000000ULL)==0xf0000000ULL)));
 }
 for(int d=0;d<2;d++){
  clear();down_ret=d?-5:0;assert(xlnx_rpu_rproc_stop(&r)==down_ret);
  assert(used==1 && calls[0].op==5 && calls[0].node==7 && calls[0].a==2);cases++;
 }
 for(int current=0;current<2;current++) for(int desired=0;desired<2;desired++)
 for(int q=0;q<2;q++) for(int sr=0;sr<2;sr++) for(int tr=0;tr<2;tr++) {
  clear(); soc.soc_type=SOC_ZYNQMP;mode=current;query_ret=q?-13:0;set_ret=sr?-22:0;tcm_ret=tr?-5:0;
  int ret=rpu_set_mode(&z,desired);cases++;
  if(q){assert(ret==-13 && used==1);continue;}
  if(current!=desired){assert(calls[1].op==2);if(sr){assert(ret==-22 && used==2);continue;}}
  assert(ret==tcm_ret && used==(current!=desired?3:2));
  assert(calls[used-1].op==3 && calls[used-1].a==(desired==0));
 }
 printf("PASS %d actual callback fault/ordering cases\n",cases);
 return 0;
}
'''

SMC_PREFIX = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32; typedef uint64_t u64; typedef uint8_t u8;
#define noinline
#define EINVAL 22
#define lower_32_bits(x) ((u32)(x))
#define upper_32_bits(x) ((u32)((u64)(x)>>32))
enum pm_ret_status { PM_SUCCESS=0 };
struct arm_smccc_res {u64 a0,a1,a2,a3;};
static void arm_smccc_smc(u64 a,u64 b,u64 c,u64 d,u64 e,u64 f,u64 g,u64 h,struct arm_smccc_res *r) {
 *r=(struct arm_smccc_res){0x100000000ULL,0x300000002ULL,0x500000004ULL,6};
}
static int zynqmp_pm_ret_code(enum pm_ret_status status){return status;}
'''
SMC_MAIN = r'''
int main(void) {
 /* Backing storage is seven words so the demonstration itself is in bounds;
  * words4..6 model the caller's neighboring stack objects, not output storage.
  */
 u32 storage[7]={0,0,0,0,0xabad1dea,0xabad1dea,0xabad1dea};
 assert(do_fw_call_smc(storage,0)==0);
 assert(storage[0]==0 && storage[1]==1);
 assert(storage[4]==4 && storage[5]==5 && storage[6]==6);
 puts("CONFIRMED helper writes seven words; debugfs IOCTL caller declares only four");
 return 0;
}
'''


def main():
    out=BASE/'driver-host-check-v1'
    out.mkdir(exist_ok=False)
    driver=(SOURCE/'drivers/remoteproc/zynqmp_r5_remoteproc.c').read_text()
    firmware=(SOURCE/'drivers/firmware/xilinx/zynqmp.c').read_text()
    callbacks='\n'.join(function(driver,n) for n in ['rpu_set_mode','xlnx_rpu_rproc_start','xlnx_rpu_rproc_stop'])
    (out/'callbacks.c').write_bytes((PREFIX+callbacks+MAIN).encode())
    (out/'smc-buffer.c').write_bytes((SMC_PREFIX+function(firmware,'do_fw_call_smc')+SMC_MAIN).encode())
    wsl='/mnt/c/'+str(out.resolve())[3:].replace('\\','/')
    results={}
    for name in ['callbacks','smc-buffer']:
        r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','gcc','-std=c11','-O2',wsl+'/'+name+'.c','-o',wsl+'/'+name],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (out/(name+'-compile.log')).write_bytes(r.stdout);assert not r.returncode,name
        r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--',wsl+'/'+name],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
        (out/(name+'.log')).write_bytes(r.stdout);assert not r.returncode,name
        results[name]=r.stdout.decode().strip()
    getter=function(firmware,'zynqmp_pm_get_rpu_mode')
    assert '*rpu_mode = ret_payload[0]' in getter
    debug=(SOURCE/'drivers/firmware/xilinx/zynqmp-debug.c').read_text()
    assert 'u32 pm_api_ret[4]' in debug
    assert 'pm_api_arg[4], &pm_api_ret[0]' in debug
    receipt=dict(passed=True,actual_source_callbacks=True,results=results,
        mode_getter_status_slot_limitation=True,debugfs_ioctl_seven_into_four_buffer_issue=True,
        debugfs_ioctl_admitted=False,software_only=True,live_startup_qualified=False,
        source_sha256={n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in [
            'drivers/remoteproc/zynqmp_r5_remoteproc.c','drivers/firmware/xilinx/zynqmp.c','drivers/firmware/xilinx/zynqmp-debug.c']})
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(results))


if __name__=='__main__':main()
