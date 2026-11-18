"""Reproduce exact vendor TCM cleanup limitations without target access."""
from pathlib import Path
import hashlib
import json
import subprocess
from check_amp_linux_r5_driver import function

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/v2/typed200-amp-linux-r5-v1'
PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define EINVAL 22
#define ENOMEM 12
#define SOC_ZYNQMP 0
#define SOC_VERSAL 1
#define SOC_VERSAL_NET 2
#define VERSAL_NET_CORES 4
#define PD_PROP "power-domains"
#define PM_USAGE_NO_MASTER 0
#define ZYNQMP_PM_CAPABILITY_ACCESS 1
#define ZYNQMP_PM_REQUEST_ACK_BLOCKING 2
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define IS_ERR_OR_NULL(x) (!(x))
struct device { struct device *parent; };
struct device_node { int banks; u32 ids[4]; };
struct sram_addr_data { u32 ids[4]; };
struct soc { int soc_type,max_banks,num_tcms; u32 tcm_bases[4]; };
struct xlnx_rpu_rproc { struct soc *soc_data; };
struct rproc { void *priv; struct device dev; };
struct rproc_mem_entry { void *va,*priv; unsigned long dma,da,len; };
static int leases[32],requests,fail_request,map_calls,fail_map,plain_maps,devm_maps;
static void *of_get_property(struct device_node *n,const char *p,void *l) {return n;}
static int of_count_phandle_with_args(struct device_node *n,const char *p,void *l) {return n->banks*2;}
static int of_property_read_u32_index(struct device_node *n,const char *p,int i,u32 *v) {*v=n->ids[i/2];return 0;}
static int zynqmp_pm_get_node_status(u32 id,u32 *s,void *r,u32 *u) {*s=0;*u=0;return 0;}
static int zynqmp_pm_request_node(u32 id,u32 c,u32 q,u32 a) {
 assert(id<32);requests++;if(requests==fail_request)return -5;leases[id]++;return 0;
}
static int zynqmp_pm_release_node(u32 id) {assert(leases[id]>0);leases[id]--;return 0;}
static void *ioremap_wc(unsigned long d,unsigned long l) {
 if(++map_calls==fail_map)return NULL;plain_maps++;return (void *)0x1000;
}
static void *devm_ioremap_wc(struct device *d,unsigned long a,unsigned long l) {
 if(++map_calls==fail_map)return NULL;devm_maps++;return (void *)0x2000;
}
static void iounmap(void *p) {assert(p && plain_maps>0);plain_maps--;}
static void clear(void) {
 memset(leases,0,sizeof leases);requests=fail_request=map_calls=fail_map=plain_maps=devm_maps=0;
}
'''
MAIN = r'''
int main(void) {
 struct device d={0};struct device_node node={2,{15,16}};
 struct sram_addr_data banks={0};struct soc soc={0,4,2,{0,0x20000}};
 struct xlnx_rpu_rproc z={&soc};struct rproc r={&z,{&d}};
 struct rproc_mem_entry mem={0,&banks,0xffe00000,0xffe00000,65536};
 int cases=0;
 /* Partial acquisition has no local rollback. No carveout yet owns this bank. */
 clear();fail_request=2;
 assert(xlnx_rpu_pm_request_sram(&d,&node,false,&banks)==-5);
 assert(leases[15]==1 && leases[16]==0 && banks.ids[0]==15);cases++;
 /* Failure before any acquisition does not leak. */
 clear();memset(&banks,0,sizeof banks);fail_request=1;
 assert(xlnx_rpu_pm_request_sram(&d,&node,false,&banks)==-5);
 assert(leases[15]==0 && leases[16]==0);cases++;
 /* A second mapping failure retains the first non-devm mapping. */
 clear();fail_map=2;
 assert(sram_mem_alloc(&r,&mem)==-ENOMEM);
 assert(plain_maps==1 && devm_maps==0 && mem.va);cases++;
 /* First-map failure has no mapping to release. */
 clear();mem.va=NULL;fail_map=1;
 assert(sram_mem_alloc(&r,&mem)==-ENOMEM);
 assert(plain_maps==0 && devm_maps==0 && !mem.va);cases++;
 /* Normal release removes one mapping, but devm mappings survive until unbind. */
 clear();memset(&banks,0,sizeof banks);
 for(int iteration=0;iteration<3;iteration++) {
  node.banks=1;mem.da=mem.dma=0xffe00000;
  assert(xlnx_rpu_pm_request_sram(&d,&node,false,&banks)==0);
  assert(sram_mem_alloc(&r,&mem)==0 && mem.da==0);
  assert(sram_mem_release(&r,&mem)==0);
  assert(leases[15]==0 && plain_maps==0 && devm_maps==iteration+1);cases++;
 }
 printf("PASS %d actual-function cleanup scenarios; partial lease and duplicate mapping lifetimes reproduced\n",cases);
}
'''


def main():
    out = BASE / 'cleanup-host-check-v1'
    out.mkdir(exist_ok=False)
    name = 'drivers/remoteproc/zynqmp_r5_remoteproc.c'
    source = (BASE / 'kernel-source-v3' / name).read_text()
    callbacks = '\n'.join(function(source, n) for n in [
        'xlnx_rpu_pm_request_sram', 'sram_mem_alloc', 'sram_mem_release'])
    (out / 'cleanup.c').write_bytes((PREFIX + callbacks + MAIN).encode())
    wsl = '/mnt/c/' + str(out.resolve())[3:].replace('\\', '/')
    for args, log in [(['gcc', '-std=c11', '-O2', wsl+'/cleanup.c', '-o', wsl+'/cleanup'], 'compile.log'),
                      ([wsl+'/cleanup'], 'scenarios.log')]:
        run = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', *args],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
        (out / log).write_bytes(run.stdout)
        assert run.returncode == 0, log
    receipt = dict(passed=True, actual_source_functions=True, software_only=True,
                   scenarios=7, partial_tcm_lease_not_locally_rolled_back=True,
                   second_mapping_failure_retains_first_mapping=True,
                   successful_cycles_retain_devm_mapping_until_device_unbind=True,
                   limitations='Host mocks model ownership and mapping counts; no hardware or full kernel lifecycle execution.',
                   driver_fixed=False, live_startup_admitted=False,
                   source_sha256={name: hashlib.sha256(source.encode()).hexdigest()})
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print((out / 'scenarios.log').read_text().strip())


if __name__ == '__main__':
    main()
