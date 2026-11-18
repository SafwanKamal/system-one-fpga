#include "pmu_seal.h"
#include "seal_policy.h"
#include <assert.h>
#include <stdio.h>
static XPfw_Module_t em={1},normal={2};
const XPfw_Module_t *EmModPtr=&em;
void *Ipi0InstPtr=(void *)1;
static unsigned complete=11,masked,callback_running,replies;
static uint32_t last[8];
u32 XPfw_Read32(u32 address){assert(address==0xffd80044u);return complete;}
void microblaze_disable_interrupts(void){assert(!masked);masked=1;}
void microblaze_enable_interrupts(void){assert(masked);masked=0;}
int XIpiPsu_WriteMessage(void *ipi,u32 source,u32 *p,u32 words,unsigned kind){
    assert(ipi==Ipi0InstPtr && source && words==8 && kind==1);
    if(p[0]==(TB_MODULE<<16))assert(masked && TypedBootClosed() && !callback_running);
    for(unsigned i=0;i<8;i++)last[i]=p[i];
    replies++;return 0;
}
int main(void){
    uint32_t p[8]={TB_REQUEST,TB_MAGIC,42,99,1,0,0,0};
    uint32_t ordinary[8]={1,0,0,0,0,0,0,0};
    assert(!TypedBootIpi(0,1,ordinary,8) && !replies);
    complete=3;assert(TypedBootIpi(0,1,p,8) && last[0]==((TB_MODULE<<16)|TB_NOT_READY));
    complete=11;assert(TypedBootIpi(1,1,p,8) && last[0]==((TB_MODULE<<16)|TB_INVALID));
    assert(TypedBootIpi(0,256,p,8) && last[0]==((TB_MODULE<<16)|TB_INVALID));
    assert(TypedBootEvent(&normal,10) && !TypedBootClosed());
    callback_running=1;unsigned before=replies;
    assert(TypedBootIpi(0,1,p,8) && replies==before && !TypedBootClosed());
    /* Core scheduler returns to main-loop service before success response. */
    callback_running=0;TypedBootService();
    assert(replies==before+1 && last[0]==(TB_MODULE<<16) && last[2]==42 && last[3]==99);
    assert(TypedBootClosed() && !masked);
    assert(TypedBootIpi(0,1,ordinary,8) && (last[0]&0xffff)==TB_INVALID);
    assert(TypedBootIpi(0,1,p,8) && (last[0]&0xffff)==TB_BUSY);
    assert(TypedBootEvent(&em,4) && TypedBootEvent(&em,5));
    for(unsigned e=0;e<83;e++){
        assert(!TypedBootEvent(&normal,e));
        assert(TypedBootEvent(&em,e)==(e==4||e==5));
    }
    before=replies;TypedBootService();assert(replies==before && TypedBootClosed());
    puts("actual pmu_seal.c integration PASS: deferred ACK, all event IDs, ordinary IPI denial, sticky seal");
}
