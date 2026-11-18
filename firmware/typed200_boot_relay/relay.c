#include "relay.h"
#include "../typed200_mvp/ownership.h"
#include "../typed200_r5/service.h"
/* Generated ONLY from the frozen v5 A53 ELF; no OCM application partition. */
#include "a53_payload.h"
struct relay_input {struct mvp_boot boot;struct ty_shared request;};
_Static_assert(sizeof(struct relay_input)==448,"relay provisioning ABI");
#ifdef RELAY_HOST_TEST
extern uint32_t relay_mock_read(uint32_t);
extern void relay_mock_write(uint32_t,uint32_t);
extern void relay_mock_fault(uint32_t) __attribute__((noreturn));
extern void relay_mock_jump(uint64_t) __attribute__((noreturn));
extern void relay_mock_after_copy(void);
#define read32 relay_mock_read
#define write32 relay_mock_write
#else
static uint32_t read32(uint32_t a){return *(volatile uint32_t *)(uintptr_t)a;}
static void write32(uint32_t a,uint32_t v){*(volatile uint32_t *)(uintptr_t)a=v;}
#endif
static void barrier(void){
#ifndef RELAY_HOST_TEST
    __asm__ volatile("dsb sy":::"memory");
#endif
}
__attribute__((noreturn)) void relay_fault(uint32_t why){
    write32(MVP_PERMIT,0);barrier();write32(RELAY_STATUS,0x80000000u|why);barrier();
#ifdef RELAY_HOST_TEST
    relay_mock_fault(why);
#else
    for(;;)__asm__ volatile("wfi");
#endif
}
int relay_destination_valid(uint64_t a,uint64_t f,uint64_t m){
    if(!m || f>m)return 0;
    /* Two deliberately narrow allowlisted v5 destination windows. */
    if(a>=UINT64_C(0xfffc0000) && a<UINT64_C(0xfffe0000))
        return m<=UINT64_C(0xfffe0000)-a;
    if(a>=UINT64_C(0xfffe0000) && a<UINT64_C(0xfffe4000))
        return m<=UINT64_C(0xfffe4000)-a;
    return 0;
}
void relay_main(void){
    write32(MVP_PERMIT,0);barrier();if(read32(MVP_PERMIT)!=0)relay_fault(1);
    write32(RELAY_STATUS,1);barrier();
    /* Entry is FINAL same-core FSBL handoff, not early/peer/core restart.
       FSBL has cleaned caches; this relay must never return or resume FSBL. */
    uint32_t cause=read32(0xff5e0220);
    if(!(cause&3) || (cause&0x807c))relay_fault(2);
    if((read32(0xfd1a0104)&14)!=14 || (read32(0xff5e023c)&3)!=3)relay_fault(3);
    if(read32(0xa00000c0)!=MVP_ABI || (read32(0xa0000004)&30) ||
       !(read32(0xa00000cc)&2))relay_fault(4);
    if((read32(0xffc80008)&0x1fff) || (read32(0xffc80808)&0x1fff) ||
       !(read32(0xffca300c)&1) || !(read32(0xffca3010)&8))relay_fault(5);
    const volatile uint8_t *src=(const volatile uint8_t *)(uintptr_t)RELAY_INPUT;
    struct relay_input input;uint8_t *raw=(uint8_t *)&input;
    for(size_t i=0;i<sizeof(input);i++)raw[i]=src[i];
    if(input.boot.magic!=MVP_MAGIC || input.boot.version!=1 || !input.boot.session ||
       input.boot.r5_hz!=MVP_R5_HZ || input.request.magic!=TY_CONFIG_MAGIC ||
       input.request.version!=1 || input.request.session!=input.boot.session ||
       input.request.command_state!=TY_CMD_READY)relay_fault(6);
    for(unsigned i=0;i<11;i++)if(input.boot.reserved[i])relay_fault(6);
    /* Validate EVERY destination/overlap before writing any OCM payload. */
    for(size_t i=0;i<A53_SEGMENTS;i++){
        const struct a53_segment *s=&a53_segments[i];
        if(!relay_destination_valid(s->address,s->filesz,s->memsz))relay_fault(7);
        for(size_t j=0;j<i;j++){
            const struct a53_segment *p=&a53_segments[j];
            if(s->address<p->address+p->memsz && p->address<s->address+s->memsz)relay_fault(7);
        }
    }
    for(size_t i=0;i<A53_SEGMENTS;i++){
        const struct a53_segment *s=&a53_segments[i];
        volatile uint8_t *d=(volatile uint8_t *)(uintptr_t)s->address;
        for(size_t j=0;j<s->memsz;j++)d[j]=j<s->filesz?s->data[j]:0;
    }
    volatile uint8_t *cfg=(volatile uint8_t *)(uintptr_t)RELAY_DEST_INPUT;
    for(size_t i=0;i<sizeof(input);i++)cfg[i]=raw[i];
    barrier();
#ifdef RELAY_HOST_TEST
    relay_mock_after_copy();
#endif
    for(size_t i=0;i<A53_SEGMENTS;i++){
        const struct a53_segment *s=&a53_segments[i];
        const volatile uint8_t *d=(const volatile uint8_t *)(uintptr_t)s->address;
        for(size_t j=0;j<s->memsz;j++)if(d[j]!=(j<s->filesz?s->data[j]:0))relay_fault(8);
    }
    for(size_t i=0;i<sizeof(input);i++)if(cfg[i]!=raw[i])relay_fault(8);
    write32(RELAY_STATUS,2);barrier();
#ifdef RELAY_HOST_TEST
    relay_mock_jump(UINT64_C(0xfffc0000));
#else
    /* No dirty cache lines are generated here: entry requires cache/MMU off.
       Complete OCM stores and discard old FSBL instruction state before branch. */
    __asm__ volatile("dsb sy\n ic iallu\n dsb sy\n isb":::"memory");
    ((void (*)(void))(uintptr_t)0xfffc0000)();
    relay_fault(9);
#endif
}
