#include "pmu_lease.h"
#include "xpfw_ipi_manager.h"
#include "pm_defs.h"
#include "mb_interface.h"
static volatile u32 pending;
static volatile u64 pending_session;
int AmpPmuLeaseIpi(u32 ipi,u32 source,const u32 *p,u32 n) {
 if(!p || !n || ((p[0]>>16)&255u)!=127u)return 0;
 u32 response[8]={XST_PM_NO_ACCESS,0,0,AMP_LEASE_ABI,0,0,0,0};
 if(ipi==0 && source==0x100 && n==8 &&
    (p[0]==AMP_LEASE_CLOSE || p[0]==AMP_LEASE_STATUS) &&
    p[3]==AMP_LEASE_ABI && p[4]==AMP_GATES && !p[5] && !p[6] && !p[7]) {
  u64 session=(u64)p[1]|(u64)p[2]<<32;
  if(session) {
   response[1]=p[1];response[2]=p[2];
   if(AmpPmuMatches(session))response[0]=AMP_LEASE_ACK;
   else if(!AmpPmuClosed()) {
    if(!pending && p[0]==AMP_LEASE_CLOSE) {
     pending_session=session;pending=1;
    }
    if(pending && pending_session==session)response[0]=AMP_LEASE_PENDING;
   }
  }
 }
 (void)XIpiPsu_WriteMessage(Ipi0InstPtr,source,response,8,XIPIPSU_BUF_TYPE_RESP);
 return 1;
}
void AmpPmuLeasePoll(void) {
 u32 previous=mfmsr();microblaze_disable_interrupts();
 if(pending) {
  u64 session=pending_session;
  /* No old scheduler callback can be suspended on this main-loop stack.
   * Interrupts stay masked through commit; inner commit preserves that mask. */
  (void)AmpPmuCommit(session,AMP_GATES);pending=0;
 }
 if(previous&2u)microblaze_enable_interrupts();
}
