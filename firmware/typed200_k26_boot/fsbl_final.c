#ifdef TB_HOST_TEST
#include "test_fsbl_stubs.h"
#else
#include "fsbl_final.h"
#endif
#include "seal_policy.h"
#ifndef TB_HOST_TEST
#include "xfsbl_main.h"
#include "xfsbl_misc.h"
#include "xipipsu.h"
#include "xil_io.h"
#include "sleep.h"
#endif
#define RD(a) Xil_In32(a)
static void sync_io(void){
#ifndef TB_HOST_TEST
    __asm__ volatile("dsb sy\n isb":::"memory");
#endif
}
static void fail(u32 code) __attribute__((noreturn));
static void fail(u32 code){
    /* PL must already be present before this hook. Diagnostic receipt only. */
    Xil_Out32(0xa0001000u,0);sync_io();
    Xil_Out32(0x100f1000u,0xe1000000u|code);sync_io();
#ifdef TB_HOST_TEST
    tb_host_fail(code);
#else
    for(;;)__asm__ volatile("wfi");
#endif
}
static void masked(u32 a,u32 mask,u32 value,u32 code){
    Xil_Out32(a,(RD(a)&~mask)|value);sync_io();if((RD(a)&mask)!=value)fail(code);
}
void TypedBootFinal(u64 address,u32 flags){
    u64 mpidr,el;XIpiPsu ipi;XIpiPsu_Config *cfg;
    u32 p[XIPIPSU_MAX_MSG_LEN]={0},r[XIPIPSU_MAX_MSG_LEN]={0};
#ifdef TB_HOST_TEST
    mpidr=tb_host_mpidr;el=tb_host_el;
#else
    __asm__ volatile("mrs %0,mpidr_el1":"=r"(mpidr));
    __asm__ volatile("mrs %0,CurrentEL":"=r"(el));
#endif
    if(address!=0x10000000u || flags!=XFSBL_HANDOFFEXIT ||
       (mpidr&0xffffffu) || el!=12u)fail(1);
    if(!(RD(0xff5e0220u)&3u) || (RD(0xff5e0220u)&0x807cu))fail(2);
    if(RD(0xa00000c0u)!=0x54590201u || RD(0xa0001000u) ||
       (RD(0xa0000004u)&30u) || !(RD(0xa00000ccu)&2u))fail(3);
    /* Power both TCM islands while normal PMU boot services are still available. */
    if(XFsbl_PowerUpIsland(PMU_GLOBAL_PWR_STATE_R5_0_MASK|PMU_GLOBAL_PWR_STATE_R5_1_MASK)
       !=XFSBL_SUCCESS)fail(4);
    masked(0xfd1a0104u,14u,14u,5);
    masked(0xff9a0100u,1u,0u,6);masked(0xff9a0200u,1u,0u,6);
    masked(0xff5e023cu,7u,3u,7); /* both CPUs reset, AMBA enabled */
    /* Final hook occurs after FSBL completed flag and watchdog shutdown. */
    u32 n;
    for(n=0;n<2000000u;n++){
        if((RD(0xffd80044u)&15u)==11u)break;
        usleep(1);
    }
    if(n==2000000u)fail(8);
    if((RD(0xffc80008u)&0x1fffu) || (RD(0xffc80808u)&0x1fffu) ||
       !(RD(0xffca300cu)&1u) || !(RD(0xffca3010u)&8u))fail(9);
    /* Bind handshake to the exact provisioned request; relay checks complete ABI. */
    if(RD(0x100f0000u)!=0x4d565031u || RD(0x100f0004u)!=1u ||
       !(RD(0x100f0008u)|RD(0x100f000cu)))fail(10);
    p[0]=TB_REQUEST;p[1]=TB_MAGIC;p[2]=RD(0x100f0008u);p[3]=RD(0x100f000cu);p[4]=TB_VERSION;
    cfg=XIpiPsu_LookupConfig(0xff300000u);
    if(!cfg || XIpiPsu_CfgInitialize(&ipi,cfg,cfg->BaseAddress)!=XST_SUCCESS)fail(11);
    if(XIpiPsu_WriteMessage(&ipi,0x10000u,p,XIPIPSU_MAX_MSG_LEN,XIPIPSU_BUF_TYPE_MSG)!=XST_SUCCESS ||
       XIpiPsu_TriggerIpi(&ipi,0x10000u)!=XST_SUCCESS ||
       XIpiPsu_PollForAck(&ipi,0x10000u,2000000u)!=XST_SUCCESS)fail(12);
    /* Hardware IRQ acknowledgement precedes deferred response. A fresh cold-boot
       session and exact response identity prevent accepting an earlier ACK. */
    for(n=0;n<2000000u;n++){
        if(XIpiPsu_ReadMessage(&ipi,0x10000u,r,XIPIPSU_MAX_MSG_LEN,XIPIPSU_BUF_TYPE_RESP)==XST_SUCCESS &&
           r[0]==(TB_MODULE<<16) && r[1]==TB_MAGIC && r[2]==p[2] && r[3]==p[3] && r[4]==TB_VERSION){
            u32 i;for(i=5;i<XIPIPSU_MAX_MSG_LEN;i++)if(r[i])break;
            if(i==XIPIPSU_MAX_MSG_LEN)break;
        }
        usleep(1);
    }
    if(n==2000000u)fail(13);
    sync_io();Xil_Out32(0x100f1000u,0x5345414cu);sync_io();
    /* No clock/reset/CSU work after seal. Exit assembly disables MMU/I/D caches. */
}
