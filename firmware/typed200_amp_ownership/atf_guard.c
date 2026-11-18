#include "atf_guard.h"
#include <lib/spinlock.h>
static spinlock_t service_lock;
static volatile struct amp_owner owner;
int AmpAtfCommit(uint64_t session,uint32_t gates) {
 int ok=0;spin_lock(&service_lock);
 if(owner.phase==AMP_BOOT && session && gates==AMP_GATES) {
  owner.session=session;owner.phase=AMP_OWNED;ok=1;
 } else owner.phase=AMP_QUARANTINED;
 spin_unlock(&service_lock);return ok;
}
int AmpAtfLockAllow(uint32_t fid,uint64_t x1,uint64_t x2,uint64_t x3) {
 spin_lock(&service_lock);
 if(owner.phase==AMP_BOOT)return 1;
 struct amp_owner snapshot={owner.phase,owner.failed_step,owner.session};
 uint32_t id=fid&0xffffu;
 if(id>255)return 0;
 uint32_t p[6]={id,(uint32_t)x1,(uint32_t)(x1>>32),(uint32_t)x2,
  (uint32_t)(x2>>32),(uint32_t)x3};
 return amp_pm_allow(&snapshot,0,1,p,6);
}
void AmpAtfUnlock(void) {spin_unlock(&service_lock);}
int AmpAtfIpiLockAllow(uint32_t fid,uint64_t local,uint64_t remote,
 uint64_t flags,uint64_t unused) {
 spin_lock(&service_lock);
 if(owner.phase==AMP_BOOT)return 1;
 if(owner.phase!=AMP_OWNED || !owner.session)return 0;
 /* Raw secure-monitor IPI services must not impersonate R5 or PMU sources.
  * PMU0/PMU1 remote agents only; firmware still validates its own channel map. */
 uint32_t id=fid&0xffffu;
 return id>=0x1000 && id<=0x1006 && local==0 &&
  (remote==3 || remote==4) && flags<=1 && unused==0;
}
