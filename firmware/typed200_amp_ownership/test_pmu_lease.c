#include "pmu_lease.h"
#include <assert.h>
#include <stdio.h>
static XPfw_Module_t em={1};
const XPfw_Module_t *EmModPtr=&em;
void *Ipi0InstPtr=(void *)1;
static u32 msr=2,last[8],replies;
uint32_t mfmsr(void){return msr;}
void microblaze_disable_interrupts(void){msr&=~2u;}
void microblaze_enable_interrupts(void){msr|=2u;}
int XIpiPsu_WriteMessage(void *inst,u32 source,u32 *p,u32 n,unsigned kind) {
 assert(inst==Ipi0InstPtr && source && n==8 && kind==1);
 for(unsigned i=0;i<8;i++)last[i]=p[i];
 replies++;return 0;
}
int main(void) {
 u32 p[8]={AMP_LEASE_CLOSE,0x12345678,0xabcdef01,AMP_LEASE_ABI,AMP_GATES,0,0,0};
 /* Every controller source except authenticated R5 must be unable to close. */
 for(unsigned source=1;source<=1024;source++)if(source!=256) {
  assert(AmpPmuLeaseIpi(0,source,p,8));assert(last[0]==XST_PM_NO_ACCESS);
  AmpPmuLeasePoll();assert(!AmpPmuClosed() && msr==2);
 }
 /* All lengths and every bit in command payload are checked. Mutations can
  * select a different nonzero session, so test malformed fields separately. */
 for(unsigned n=0;n<8;n++) {
  assert(AmpPmuLeaseIpi(0,256,p,n)==(n!=0));assert(!AmpPmuClosed());
 }
 for(unsigned word=3;word<8;word++)for(unsigned bit=0;bit<32;bit++) {
  p[word]^=UINT32_C(1)<<bit;assert(AmpPmuLeaseIpi(0,256,p,8));
  assert(last[0]==XST_PM_NO_ACCESS);p[word]^=UINT32_C(1)<<bit;
  AmpPmuLeasePoll();assert(!AmpPmuClosed());
 }
 assert(AmpPmuLeaseIpi(1,256,p,8) && last[0]==XST_PM_NO_ACCESS);
 p[0]=AMP_LEASE_STATUS;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==XST_PM_NO_ACCESS);
 p[0]=AMP_LEASE_CLOSE;assert(AmpPmuLeaseIpi(0,256,p,8));
 assert(last[0]==AMP_LEASE_PENDING && !AmpPmuClosed());
 /* A status read cannot perform activation, nor can a conflicting request
  * replace the pending session. Closure occurs only at explicit loop poll. */
 p[1]++;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==XST_PM_NO_ACCESS);p[1]--;
 p[0]=AMP_LEASE_STATUS;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==AMP_LEASE_PENDING);
 assert(!AmpPmuClosed());msr=0;AmpPmuLeasePoll();assert(msr==0 && AmpPmuClosed());
 assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==AMP_LEASE_ACK);
 assert(last[1]==p[1] && last[2]==p[2] && last[3]==AMP_LEASE_ABI);
 for(unsigned i=4;i<8;i++)assert(!last[i]);
 p[0]=AMP_LEASE_CLOSE;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==AMP_LEASE_ACK);
 msr=2;AmpPmuLeasePoll();assert(msr==2 && AmpPmuMatches(UINT64_C(0xabcdef0112345678)));
 p[1]++;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==XST_PM_NO_ACCESS);
 u32 mutation[8]={2};assert(AmpPmuIpi(0,1,mutation,8) && last[0]==XST_PM_NO_ACCESS);
 assert(!AmpPmuCommit(9,AMP_GATES));assert(!AmpPmuMatches(UINT64_C(0xabcdef0112345678)));
 p[1]--;assert(AmpPmuLeaseIpi(0,256,p,8) && last[0]==XST_PM_NO_ACCESS);
 printf("PASS deferred PMU closure: 1023 unauthorized sources,160 malformed-field mutations, session-bound idempotent ACK, preserved IRQ mask; %u replies\n",replies);
 return 0;
}
