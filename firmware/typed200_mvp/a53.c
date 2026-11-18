#include "ownership.h"
#include "vendor_regs.h"
#include "../typed200_r5/service.h"
#include "../typed200_timed/pmu.h"
/* Generated from the freshly linked R5 ELF, not a second independently built image. */
#include "r5_payload.h"
struct mvp_input {struct mvp_boot boot;struct ty_shared request;};
#ifdef MVP_HOST_TEST
extern uint32_t mvp_mock_read(void *,uint32_t);
extern void mvp_mock_write(void *,uint32_t,uint32_t);
extern void mvp_mock_barrier(void *);
extern void mvp_mock_fault(uint32_t) __attribute__((noreturn));
#define rd mvp_mock_read
#define wr mvp_mock_write
#define sync_io mvp_mock_barrier
#else
static uint32_t rd(void *c,uint32_t a){(void)c;return *(volatile uint32_t *)(uintptr_t)a;}
static void wr(void *c,uint32_t a,uint32_t v){(void)c;*(volatile uint32_t *)(uintptr_t)a=v;}
static void sync_io(void *c){(void)c;__asm__ volatile("dsb sy":::"memory");}
#endif
static const struct mvp_io io={0,rd,wr,sync_io};
static void bytes(volatile void *to,const void *from,size_t n){
    volatile uint8_t *d=to;const uint8_t *s=from;while(n--)*d++=*s++;
}
static void zero(volatile void *to,size_t n){volatile uint8_t *d=to;while(n--)*d++=0;}
__attribute__((noreturn)) void mvp_a53_fault(uint32_t why){
    (void)mvp_off(&io);wr(0,0xfffef000,why);sync_io(0);
#ifdef MVP_HOST_TEST
    mvp_mock_fault(why);
#else
    for(;;)__asm__ volatile("wfi");
#endif
}
void mvp_a53_main(void){
    /* Provisioned by trusted cold-boot loader AFTER PS/PL/model init; no Linux. */
    const volatile struct mvp_input *in=(const volatile struct mvp_input *)0xfffee000;
    struct mvp_input cfg;
    volatile const uint8_t *src=(volatile const uint8_t *)in;uint8_t *dst=(uint8_t *)&cfg;
    for(size_t n=0;n<sizeof(cfg);n++)dst[n]=src[n];
    if(!mvp_prepare(&io))mvp_a53_fault(1);
    if(cfg.boot.magic!=MVP_MAGIC || cfg.boot.version!=1 || !cfg.boot.session ||
       cfg.boot.r5_hz!=MVP_R5_HZ || cfg.request.magic!=TY_CONFIG_MAGIC ||
       cfg.request.version!=1 || cfg.request.session!=cfg.boot.session ||
       cfg.request.command_state!=TY_CMD_READY)mvp_a53_fault(2);
    for(unsigned n=0;n<11;n++)if(cfg.boot.reserved[n])mvp_a53_fault(2);
    /* TCM power/clock/AMBA must already be supplied by trusted PS init. */
    if(!mvp_scrub_tcm(&io,0xffe00000,1000000) ||
       !mvp_scrub_tcm(&io,0xffe20000,1000000))mvp_a53_fault(3);
    for(size_t n=0;n<R5_SEGMENTS;n++){
        const struct r5_segment *s=&r5_segments[n];
        if(!mvp_segment_valid(s->address,s->filesz,s->memsz))mvp_a53_fault(4);
        uintptr_t global=UINT32_C(0xffe00000)+s->address;
        zero((volatile void *)global,s->memsz);
        bytes((volatile void *)global,s->data,s->filesz);
        const volatile uint8_t *v=(const volatile uint8_t *)global;
        for(size_t j=0;j<s->memsz;j++)if(v[j]!=(j<s->filesz?s->data[j]:0))mvp_a53_fault(5);
    }
    /* Configuration is installed AFTER ELF NOLOAD/BSS segments are zeroed. */
    volatile struct ty_shared *shared=(volatile struct ty_shared *)0xffe2f000;
    zero(shared,sizeof(*shared));
    shared->magic=TY_CONFIG_MAGIC;shared->version=1;shared->session=cfg.boot.session;
    /* Legacy service ABI field, derived from R5's independent ownership check. */
    shared->exclusive_buffers_attested=1;
    shared->sequence=cfg.request.sequence;shared->tokens=cfg.request.tokens;
    shared->first=cfg.request.first;shared->count=cfg.request.count;
    shared->reserved=cfg.request.reserved;shared->budget=cfg.request.budget;
    for(unsigned i=0;i<128;i++)shared->ids[i]=cfg.request.ids[i];
    struct ty_pmu_config pmu={TY_PMU_CONFIG_MAGIC,1,cfg.boot.session,MVP_R5_HZ,1,{0,0}};
    bytes((volatile void *)0xffe2f180,&pmu,sizeof(pmu));
    bytes((volatile void *)0xffe2f1c0,&cfg.boot,sizeof(cfg.boot));
    shared->command_state=TY_CMD_READY;sync_io(0);
    /* Release only R5_0; R5_1 reset and NCPUHALT remain asserted. */
    uint32_t v=rd(0,V_CRL_APB_RST_LPD_TOP);
    wr(0,V_CRL_APB_RST_LPD_TOP,v&~1u);sync_io(0);
    if(rd(0,V_CRL_APB_RST_LPD_TOP)!=(v&~1u))mvp_a53_fault(6);
    v=rd(0,V_RPU_RPU_0_CFG);wr(0,V_RPU_RPU_0_CFG,(v&~4u)|1u);sync_io(0);
    if((rd(0,V_RPU_RPU_0_CFG)&5)!=1)mvp_a53_fault(6);
    wr(0,0xfffef000,0x48414e44);sync_io(0); /* handoff issued, NOT ownership */
    v=rd(0,V_CRF_APB_RST_FPD_APU);wr(0,V_CRF_APB_RST_FPD_APU,v|15u);sync_io(0);
    /* If self-reset is denied, R5 never observes all four resets and fails closed. */
#ifdef MVP_HOST_TEST
    mvp_mock_fault(0x81);
#else
    for(;;)__asm__ volatile("wfi");
#endif
}
