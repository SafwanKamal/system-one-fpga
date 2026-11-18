#include "pmu_guard.h"
#include "xpfw_ipi_manager.h"
#include "pm_defs.h"
#include "mb_interface.h"
extern const XPfw_Module_t *EmModPtr;
static volatile struct amp_owner owner;
int AmpPmuCommit(u64 session,u32 gates) {
 u32 previous=mfmsr();
 microblaze_disable_interrupts();
 int ok=0;
 if(owner.phase!=AMP_BOOT || !session || gates!=AMP_GATES) {
  owner.phase=AMP_QUARANTINED;
 } else {owner.session=session;owner.phase=AMP_OWNED;ok=1;}
 /* MSR.IE is bit1. Preserve prior masking, including callers already masked. */
 if(previous&2u)microblaze_enable_interrupts();
 return ok;
}
int AmpPmuClosed(void) {return owner.phase!=AMP_BOOT;}
int AmpPmuMatches(u64 session) {
 return owner.phase==AMP_OWNED && session && owner.session==session;
}
int AmpPmuIpi(u32 ipi,u32 source,const u32 *p,u32 n) {
 if(!AmpPmuClosed())return 0;
 /* Controller-local payload snapshot; vendor dispatcher delivers 8 words and
  * PM handlers consume at most 6. Trailing two words cannot select an action. */
 struct amp_owner snapshot={owner.phase,owner.failed_step,owner.session};
 if(n==XPFW_IPI_MAX_MSG_LEN && n>=6 && amp_pm_allow(&snapshot,ipi,source,p,6))return 0;
 u32 response[XPFW_IPI_MAX_MSG_LEN]={0};response[0]=XST_PM_NO_ACCESS;
 (void)XIpiPsu_WriteMessage(Ipi0InstPtr,source,response,XPFW_IPI_MAX_MSG_LEN,XIPIPSU_BUF_TYPE_RESP);
 return 1;
}
int AmpPmuEvent(const XPfw_Module_t *mod,u32 event) {
 /* Match the reviewed EM safety IDs; ordinary wake/sleep/DAP and recovery
  * callbacks cannot mutate owned clocks/resets through this dispatch path. */
 return !AmpPmuClosed() || (mod==EmModPtr && (event==4 || event==5));
}
