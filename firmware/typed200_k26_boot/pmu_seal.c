#include "pmu_seal.h"
#include "seal_policy.h"
#include "xpfw_ipi_manager.h"
#include "pmu_global.h"
#include "mb_interface.h"
extern const XPfw_Module_t *EmModPtr;
/* ISR/main-loop communication: every state access must remain observable under LTO. */
static volatile struct tb_seal seal;
static void response(u32 source,u32 code,u32 lo,u32 hi) {
    u32 p[XPFW_IPI_MAX_MSG_LEN]={0};
    p[0]=(TB_MODULE<<16)|code;p[1]=TB_MAGIC;p[2]=lo;p[3]=hi;p[4]=TB_VERSION;
    /* No ACK success can escape before closed is committed. Failed write -> FSBL timeout. */
    (void)XIpiPsu_WriteMessage(Ipi0InstPtr,source,p,XPFW_IPI_MAX_MSG_LEN,XIPIPSU_BUF_TYPE_RESP);
}
int TypedBootIpi(u32 ipi,u32 source,const u32 *p,u32 words) {
    u32 code;
    if(((p[0]>>16)&0xffu)!=TB_MODULE && !seal.closed)return 0;
    code=tb_request(&seal,ipi,source,p,words,XPfw_Read32(PMU_GLOBAL_GLOBAL_GEN_STORAGE5));
    if(code!=TB_OK)response(source,code,0,0);
    /* Successful request is answered from main loop, never from an interrupted callback. */
    return 1;
}
int TypedBootClosed(void) {return seal.closed!=0;}
int TypedBootEvent(const XPfw_Module_t *mod,u32 event) {
    return tb_event_allowed(&seal,mod==EmModPtr,event);
}
void TypedBootService(void) {
    /* Main-loop only: no interrupted scheduler callback may resume after ACK. */
    microblaze_disable_interrupts();
    if(tb_commit(&seal,XPfw_Read32(PMU_GLOBAL_GLOBAL_GEN_STORAGE5)))
        response(1u,TB_OK,seal.lo,seal.hi);
    microblaze_enable_interrupts();
}
