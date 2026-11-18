#include "ownership.h"
#include "plan.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct {uint32_t addr,val;} cells[4096];
static size_t used,writes,fail_write;static int permit_bad;
static unsigned slot(uint32_t a) {
 for(unsigned i=0;i<used;i++)if(cells[i].addr==a)return i;
 assert(used<4096);cells[used].addr=a;return (unsigned)used++;
}
static uint32_t rd(void *ctx,uint32_t a) {(void)ctx;return cells[slot(a)].val;}
static void wr(void *ctx,uint32_t a,uint32_t v) {
 (void)ctx;
 if(a==AMP_PERMIT) {assert(v==0);cells[slot(a)].val=permit_bad?1:0;return;}
 writes++;if(writes==fail_write)return;
 cells[slot(a)].val=v;
}
static void barrier(void *ctx){(void)ctx;}
static void reset(void) {
 memset(cells,0,sizeof cells);used=0;writes=0;fail_write=0;permit_bad=0;
 /* Distinguish skipped zero-value writes from successful readbacks. */
 for(size_t i=0;i<sizeof amp_plan/sizeof *amp_plan;i++)
  cells[slot(amp_plan[i].address)].val=0xffffffffu;
}
static int reference(uint32_t api,uint32_t a,uint32_t b) {
 switch(api) {
  case 1:case 24:return a==0 && b==0;
  case 18:return a>=1000 && a<1120 && b==0;
  case 38:case 44:return a<=112 && b==0;
  case 40:return a<=112 && b<=1;
  default:return 0;
 }
}
int main(void) {
 struct amp_io io={0,rd,wr,barrier};struct amp_owner s={0};
 const size_t count=sizeof amp_plan/sizeof *amp_plan;
 reset();assert(amp_install(&io,&s,42,AMP_GATES,amp_plan,count));
 assert(s.phase==AMP_OWNED && s.session==42 && !rd(0,AMP_PERMIT));
 /* No caller can rebind or release an owned/quarantined one-shot lease. */
 assert(!amp_install(&io,&s,43,AMP_GATES,amp_plan,count));assert(s.phase==AMP_QUARANTINED);
 unsigned faults=0;
 for(unsigned g=0;g<7;g++) {
  reset();s=(struct amp_owner){0};
  assert(!amp_install(&io,&s,42,AMP_GATES^(1u<<g),amp_plan,count));
  assert(!writes && s.phase==AMP_QUARANTINED);faults++;
 }
 reset();s=(struct amp_owner){0};permit_bad=1;
 assert(!amp_install(&io,&s,42,AMP_GATES,amp_plan,count));assert(!writes);permit_bad=0;faults++;
 /* Inject write-loss at each operation where it changes masked state. Some
  * repeated lock/disable writes can already equal the requested value; only
  * observable failures must quarantine, never claim detecting invisible loss. */
 for(size_t i=1;i<=count;i++) {
  reset();s=(struct amp_owner){0};fail_write=i;
  int ok=amp_install(&io,&s,42,AMP_GATES,amp_plan,count);
  if(!ok){assert(s.phase==AMP_QUARANTINED && !rd(0,AMP_PERMIT));faults++;}
  else assert(s.phase==AMP_OWNED && !rd(0,AMP_PERMIT));
 }
 struct amp_write invalid={0xff5e00c0u,0xffffffffu,0};
 reset();s=(struct amp_owner){0};
 assert(!amp_install(&io,&s,42,AMP_GATES,&invalid,1));assert(!writes);faults++;
 s=(struct amp_owner){AMP_OWNED,0,42};uint32_t p[6]={0};unsigned queries=0;
 for(unsigned api=0;api<256;api++)for(unsigned a=0;a<1200;a++)for(unsigned b=0;b<3;b++) {
  p[0]=api;p[1]=a;p[2]=b;
  assert(amp_pm_allow(&s,0,1,p,6)==reference(api,a,b));queries++;
  p[0]|=0x01000000;assert(amp_pm_allow(&s,0,1,p,6)==reference(api,a,b));
  p[0]|=0x00010000;assert(!amp_pm_allow(&s,0,1,p,6));
 }
 memset(p,0,sizeof p);p[0]=1;
 for(unsigned i=0;i<32;i++) {
  if(i!=0 && i!=8)assert(!amp_pm_allow(&s,0,1u<<i,p,6));
  assert(!amp_pm_allow(&s,1u<<i,1,p,6));
 }
 for(unsigned i=0;i<6;i++){p[i]=~0u;assert(!amp_pm_allow(&s,0,1,p,6));p[i]=i==0?1:0;}
 assert(!amp_pm_allow(&s,0,1,p,5) && !amp_pm_allow(&s,0,1,p,7));
 for(unsigned phase=0;phase<4;phase++) {
  s.phase=phase;assert(amp_pm_allow(&s,0,1,p,6)==(phase==AMP_OWNED));
  assert(amp_pm_event_allow(&s,0)==(phase==AMP_BOOT));
  assert(amp_pm_event_allow(&s,1));
 }
 printf("PASS ownership: %zu plan writes; %u observable fault cases; %u API/resource/argument cases plus flags and origin checks\n",count,faults,queries);
 return 0;
}
