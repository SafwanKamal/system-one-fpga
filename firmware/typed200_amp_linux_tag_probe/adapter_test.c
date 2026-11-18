/* SPDX-License-Identifier: GPL-2.0-only */
/* Prefix + tests around extracted, byte-identical Linux adapter functions. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdlib.h>
#include <sys/types.h>
#include "session.h"
typedef uint32_t u32;typedef uint64_t u64;
#define __iomem
#define TCMA_PA 0xffe00000ULL
#define TCMA_SIZE 65536U
#define RPU0 7U
#define RPU1 8U
#define TCMA0 15U
#define TCMA1 17U
#define TRACE_OFFSET 0x1000U
#define TRACE_SIZE 128U
#define RECOVERY_MS 5000U
#define PM_SIP_SVC 0xc2000000U
#define PM_IOCTL 34U
#define PM_USAGE_NO_MASTER 0U
#define PM_USAGE_CURRENT_MASTER 1U
#define ZYNQMP_PM_CAPABILITY_ACCESS 1U
#define ZYNQMP_PM_REQUEST_ACK_BLOCKING 2U
#define ZYNQMP_PM_REQUEST_ACK_NO 1U
#define PM_RPU_BOOTMEM_LOVEC 0U
#define CAP_SYS_RAWIO 17
#define PM_SUSPEND_PREPARE 1
#define PM_HIBERNATION_PREPARE 2
#define PM_RESTORE_PREPARE 3
#define NOTIFY_OK 1
#define NOTIFY_BAD 0x8002
#define THIS_MODULE NULL
#define lower_32_bits(x) ((u32)(x))
#define upper_32_bits(x) ((u32)((u64)(x)>>32))
#define pr_info(...) ((void)printf(__VA_ARGS__))
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
struct device {int unused;};struct device_attribute {int unused;};
struct notifier_block {int unused;};
struct resource {u64 start,end;};struct work_struct {int unused;};
struct clk {int unused;};
struct device_node { const char *compatible; int available; };
struct arm_smccc_res {unsigned long a0,a1,a2,a3;};
static struct device_node mock_nodes[2];
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define for_each_compatible_node(node,type,compat) for(node=mock_nodes;node<mock_nodes+2;node++) if(of_device_is_compatible(node,compat))
static int of_device_is_available(struct device_node *n){return n->available;}
static int of_device_is_compatible(struct device_node *n,const char *s){return n->compatible && !strcmp(n->compatible,s);}
static void of_node_put(struct device_node *n){(void)n;}
static int smoke_lock,recover_work,system_wq;
static struct resource resource;
static struct resource *tcma_resource;
static struct clk mock_clock,*probe_clock;
static struct device_node probe_node={"sysone,axi-origin-probe-v1",1};
static int clock_held,clock_refs,no_probe,bad_range,clock_get_error,clock_enable_error;
static unsigned long clock_rate=99999999;
#define IS_ERR(p) ((uintptr_t)(p)>(uintptr_t)-4096)
#define PTR_ERR(p) ((int)(intptr_t)(p))
static struct device_node *of_find_compatible_node(void *a,void *b,const char *compat)
{assert(!a && !b && !strcmp(compat,probe_node.compatible));return no_probe?NULL:&probe_node;}
static int of_address_to_resource(struct device_node *node,int index,struct resource *range)
{assert(node==&probe_node && !index);range->start=0xa0000000ULL+bad_range;range->end=range->start+4095;return 0;}
static u64 resource_size(struct resource *r){return r->end-r->start+1;}
static struct clk *of_clk_get(struct device_node *node,int index)
{assert(node==&probe_node && !index);if(clock_get_error)return (void *)(intptr_t)-ENODEV;clock_refs++;return &mock_clock;}
static unsigned long clk_get_rate(struct clk *clk){assert(clk==&mock_clock);return clock_rate;}
static int clk_prepare_enable(struct clk *clk)
{assert(clk==&mock_clock && clock_refs==1 && !clock_held);if(clock_enable_error)return -EIO;clock_held=1;return 0;}
static void clk_disable_unprepare(struct clk *clk){assert(clk==&mock_clock && clock_held);clock_held=0;}
static void clk_put(struct clk *clk){assert(clk==&mock_clock && clock_refs==1 && !clock_held);clock_refs=0;}
static void *tcma;
static char saved_trace[129];
static unsigned int audit_mode,audit_r0,audit_r1,audit_usage,audit_usage1;
static int audit_result;
static bool initialized;
static struct smoke_session session;
static u64 memory[8192];
static u32 mock_mode,smc_status,state0,state1,usage;
static int refcount,reserved,mapped,writes,reads,armed,privileged=1;
static int fail_request,fail_release,fail_stop,fail_wake,fail_map,corrupt;
static int mutations,wakes,stops,requests,foreign_bank;
static void arm_smccc_smc(unsigned long a,unsigned long b,unsigned long c,unsigned long d,
 unsigned long e,unsigned long f,unsigned long g,unsigned long h,struct arm_smccc_res *res)
{
 assert(a==(PM_SIP_SVC|PM_IOCTL) && b==7 && !c && !d && !e && !f && !g && !h);
 res->a0=((u64)mock_mode<<32)|smc_status;
}
static int zynqmp_pm_get_node_status(u32 node,u32 *state,void *req,u32 *use)
{
 assert(!req && (node==7 || node==8 || node==15 || node==17));
 *state=node==7?state0:node==8?state1:1;
 if(use)*use=foreign_bank?2:!!(usage & (node==17?2:1));
 return 0;
}
static int try_module_get(void *p){(void)p;refcount++;return 1;}
static void module_put(void *p){(void)p;assert(refcount==1);refcount--;}
static struct resource *request_mem_region(u64 pa,u32 size,const char *name)
{
 assert(pa==TCMA_PA && size==TCMA_SIZE && name && !reserved);reserved=1;return &resource;
}
static void release_mem_region(u64 pa,u32 size)
{
 assert(pa==TCMA_PA && size==TCMA_SIZE && reserved && !mapped && !usage && !state0 && !clock_held && !clock_refs);reserved=0;
}
static int zynqmp_pm_request_node(u32 node,u32 cap,u32 qos,u32 ack)
{
 u32 bit=node==17?2:1;
 assert(armed && refcount && reserved && !(usage & bit) && (node==15 || node==17) && cap==1 && !qos && ack==2);
 mutations++;requests++;usage|=bit;return fail_request==requests?-EIO:0;
}
static int zynqmp_pm_release_node(u32 node)
{
 u32 bit=node==17?2:1;
 assert((node==15 || node==17) && (usage & bit) && !mapped && !state0);mutations++;
 if(fail_release)return -EIO;usage&=~bit;return 0;
}
static int zynqmp_pm_force_pwrdwn(u32 node,u32 ack)
{
 assert(node==7 && ack==2 && refcount && reserved);mutations++;stops++;
 if(fail_stop)return -EIO;state0=0;return 0;
}
static int zynqmp_pm_request_wake(u32 node,bool set,u64 address,u32 ack)
{
 assert(node==7 && set && address==0 && ack==1 && armed && mapped && usage==3);
 mutations++;wakes++;state0=1;return fail_wake?-EIO:0;
}
static void *ioremap(u64 pa,u32 size)
{
 assert(pa==TCMA_PA && size==TCMA_SIZE && usage==3 && !state0 && !mapped);
 if(fail_map)return NULL;mapped=1;return memory;
}
static void iounmap(void *p){assert(p==memory && mapped && !state0);mapped=0;}
static void writeq(u64 value,void *address)
{
 ptrdiff_t offset=(char *)address-(char *)memory;
 assert(mapped && !state0 && offset>=0 && offset%8==0 && offset<65536);
 memcpy(address,&value,8);writes++;
}
static u64 readq(void *address)
{
 u64 value;ptrdiff_t offset=(char *)address-(char *)memory;
 assert(mapped && writes==8192 && offset>=0 && offset%8==0 && offset<65536);
 memcpy(&value,address,8);reads++;
 return corrupt && offset==64?value^1:value;
}
static u32 readl(void *address)
{
 u32 value;ptrdiff_t offset=(char *)address-(char *)memory;
 assert(mapped && initialized && offset>=4096 && offset<4224 && offset%4==0);
 memcpy(&value,address,4);return value;
}
static void wmb(void){}
static int capable(int cap){assert(cap==17);return privileged;}
static int sysfs_streq(const char *a,const char *b)
{size_t n=strlen(b);return !strncmp(a,b,n) && (!a[n] || (a[n]=='\n' && !a[n+1]));}
static int mod_delayed_work(int queue,int *work,unsigned long delay)
{(void)queue;assert(work==&recover_work && delay==5000);armed=1;return 0;}
static unsigned long msecs_to_jiffies(unsigned long n){return n;}
static ssize_t sysfs_emit(char *buf,const char *fmt,...)
{va_list args;va_start(args,fmt);int n=vsnprintf(buf,4096,fmt,args);va_end(args);return n;}
#include "smoke_image.h"
#include "adapter_functions.inc"

static void reset(void)
{
 memset(&session,0,sizeof session);session.ops=&ops;
 memset(memory,0xcc,sizeof memory);memset(mock_nodes,0,sizeof mock_nodes);
 tcma=NULL;initialized=false;memset(saved_trace,0,sizeof saved_trace);
 refcount=reserved=mapped=writes=reads=armed=0;
 fail_request=fail_release=fail_stop=fail_wake=fail_map=corrupt=0;
 mock_mode=1;state0=state1=usage=smc_status=0;mutations=wakes=stops=requests=foreign_bank=0;privileged=1;
 clock_held=clock_refs=no_probe=bad_range=clock_get_error=clock_enable_error=0;clock_rate=99999999;
}
static int command(const char *text){return command_store(NULL,NULL,text,strlen(text));}
int main(void)
{
 int cases=0;char buf[4096];
 reset();
 for(unsigned long event=1;event<=4;event++) {
  session.pinned=0;assert(smoke_pm_event(NULL,event,NULL)==NOTIFY_OK);cases++;
  session.pinned=1;assert(smoke_pm_event(NULL,event,NULL)==(event<=3?NOTIFY_BAD:NOTIFY_OK));cases++;
 }
 session.pinned=0;
 for(u32 mode=0;mode<3;mode++)for(u32 status=0;status<3;status++) {
  u32 out=77;mock_mode=mode;smc_status=status;
  int ret=correct_mode(&out);
  assert(status?ret==-EIO:mode>1?ret==-EPROTO:ret==0 && out==mode);cases++;
 }
 reset();assert(command("audit")==5 && mutations==0);cases++;
 mock_mode=0;assert(command("audit")==5 && mutations==0);cases++;
 reset();state1=1;assert(command("audit")==-EBUSY && mutations==0);cases++;
 reset();foreign_bank=1;assert(command("audit")==-EBUSY && mutations==0);cases++;
 reset();mock_nodes[0]=(struct device_node){"xlnx,zynqmp-r5-remoteproc",1};
 assert(command("audit")==-EBUSY && mutations==0);cases++;
 reset();privileged=0;assert(command("audit")==-EPERM && mutations==0);cases++;
 reset();assert(command("unknown")==-EINVAL && mutations==0);cases++;
 if(!SYSONE_R5_PREPARE_ADMITTED) {
  assert(command("prepare")==-EOPNOTSUPP && command("start")==-EOPNOTSUPP);
  assert(!mutations && !mapped && !refcount && !armed);cases++;
 } else if(!SYSONE_R5_LIVE_ADMITTED) {
  assert(command("prepare")==7 && initialized && usage==3 && armed);
  assert(command("start")==-EOPNOTSUPP && !wakes && !state0);cases++;
  recover_workfn(NULL);assert(!usage && !mapped && !refcount);cases++;
 } else {
  for(int fault=0;fault<5;fault++) {
   reset();no_probe=fault==0;bad_range=fault==1;clock_get_error=fault==2;
   clock_rate=fault==3?100000001:99999999;clock_enable_error=fault==4;
   assert(command("prepare")<0 && !reserved && !refcount && !clock_refs && !clock_held && !requests);cases++;
  }
  reset();
  assert(command("prepare")==7 && initialized && writes==8192 && reads==8192);
  assert(memcmp(memory,smoke_image,sizeof smoke_image)==0);
  for(unsigned int i=sizeof(smoke_image)/8;i<8192;i++)assert(memory[i]==0);
  assert(command("start")==5 && state0==1 && wakes==1);cases++;
  memcpy((char *)memory+4096,"R5: PASS\n",9);
  assert(trace_show(NULL,NULL,buf)==9 && !strcmp(buf,"R5: PASS\n"));cases++;
  fail_stop=1;assert(command("stop")==-EIO);
  assert(session.quarantined && session.pinned && mapped && usage==3);
  assert(clock_held && clock_refs==1);
  assert(command("start")==-EINVAL && command("prepare")==-EBUSY && wakes==1);cases++;
  fail_stop=0;assert(command("stop")==4 && !mapped && !refcount && !usage);cases++;
  for(int bank=1;bank<=2;bank++) {
   reset();fail_request=bank;assert(command("prepare")==-EIO);
   assert(!usage && !mapped && !refcount && !session.quarantined);cases++;
  }
  reset();corrupt=1;assert(command("prepare")==-EIO);
  assert(!usage && !mapped && !refcount && !initialized);cases++;
  reset();fail_map=1;assert(command("prepare")==-ENOMEM && !mapped && !refcount && !usage);cases++;
  reset();assert(command("prepare")==7);fail_wake=1;fail_stop=1;
  assert(command("start")==-EIO && mapped && usage==3 && session.quarantined);
  fail_stop=0;fail_release=1;assert(command("stop")==-EIO);
  assert(!mapped && usage==3 && refcount && session.lease_pending);cases++;
  fail_release=0;assert(command("stop")==4 && !usage && !refcount);cases++;
  reset();assert(command("prepare")==7 && command("start")==5 && armed);
  recover_workfn(NULL);assert(!state0 && !usage && !mapped && !refcount);cases++;
 }
 printf("PASS %d actual-adapter scenarios (host live path=%d); mode ABI, admission, TCM bounds/readback and recovery ordering\n",cases,SYSONE_R5_LIVE_ADMITTED);
}
