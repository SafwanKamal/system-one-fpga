#include "pmu_guard.h"
#include <assert.h>
#include <stdio.h>
static XPfw_Module_t em={1},normal={2};
const XPfw_Module_t *EmModPtr=&em;
void *Ipi0InstPtr=(void *)1;
static unsigned replies;
static unsigned msr=2;
uint32_t mfmsr(void){return msr;}
void microblaze_disable_interrupts(void){msr&=~2u;}
void microblaze_enable_interrupts(void){msr|=2u;}
int XIpiPsu_WriteMessage(void *inst,u32 src,u32 *p,u32 words,unsigned kind) {
 assert(inst==Ipi0InstPtr && src && words==8 && kind==1);
 assert(p[0]==XST_PM_NO_ACCESS);for(unsigned i=1;i<8;i++)assert(!p[i]);replies++;return 0;
}
int main(void) {
 uint32_t p[8]={1};assert(!AmpPmuClosed() && !AmpPmuIpi(0,1,p,8));
 assert(AmpPmuCommit(42,AMP_GATES) && AmpPmuClosed());
 assert(msr==2);
 assert(!AmpPmuIpi(0,1,p,8) && !AmpPmuIpi(0,256,p,8));
 for(unsigned api=0;api<256;api++) {
  p[0]=api;
  int query=(api==1 || api==24 || api==38 || api==40 || api==44);
  assert(AmpPmuIpi(0,1,p,8)==!query);
  p[0]=api|0x10000;assert(AmpPmuIpi(0,1,p,8));
 }
 p[0]=1;assert(AmpPmuIpi(1,1,p,8) && AmpPmuIpi(0,512,p,8));
 assert(AmpPmuIpi(0,1,p,7));
 for(unsigned e=0;e<83;e++) {
  assert(!AmpPmuEvent(&normal,e));assert(AmpPmuEvent(&em,e)==(e==4||e==5));
 }
 msr=0;assert(!AmpPmuCommit(43,AMP_GATES));assert(msr==0);assert(AmpPmuIpi(0,1,p,8));
 printf("PASS actual pmu_guard.c: all256 API IDs/modules, source/length,83 events, sticky quarantine; %u denied replies\n",replies);
 return 0;
}
