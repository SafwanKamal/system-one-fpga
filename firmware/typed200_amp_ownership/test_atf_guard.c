#include "atf_guard.h"
#include <assert.h>
#include <stdio.h>
unsigned amp_test_lock;
int main(void) {
 assert(AmpAtfLockAllow(34,0,0,0));assert(amp_test_lock);AmpAtfUnlock();
 assert(AmpAtfCommit(42,AMP_GATES));assert(!amp_test_lock);
 unsigned cases=0;
 for(unsigned fid=0;fid<65536;fid++) {
  int allow=(fid==1 || fid==24 || fid==38 || fid==40 || fid==44);
  assert(AmpAtfLockAllow(0xc2000000u|fid,0,0,0)==allow);
  assert(amp_test_lock);AmpAtfUnlock();assert(!amp_test_lock);cases++;
 }
 assert(!AmpAtfLockAllow(0xc2000022u,0x0000000100000000ull,0,0));AmpAtfUnlock();
 assert(!AmpAtfLockAllow(0xc2000001u,1,0,0));AmpAtfUnlock();
 unsigned ipi_cases=0;
 for(unsigned id=0xfff;id<=0x1007;id++)for(unsigned local=0;local<16;local++)
  for(unsigned remote=0;remote<16;remote++)for(unsigned flag=0;flag<4;flag++) {
   int expected=id>=0x1000 && id<=0x1006 && local==0 && (remote==3||remote==4) && flag<=1;
   assert(AmpAtfIpiLockAllow(0xc2000000u|id,local,remote,flag,0)==expected);
   assert(amp_test_lock);AmpAtfUnlock();ipi_cases++;
  }
 assert(!AmpAtfIpiLockAllow(0xc2001000u,1ull<<32,3,0,0));AmpAtfUnlock();
 assert(!AmpAtfCommit(42,AMP_GATES));
 assert(!AmpAtfLockAllow(0xc2000001u,0,0,0));AmpAtfUnlock();
 printf("PASS actual atf_guard.c: %u function IDs; %u IPI route/flag cases; direct RPU/TCM IOCTL denial, balanced service lock, one-way quarantine\n",cases,ipi_cases);
 return 0;
}
