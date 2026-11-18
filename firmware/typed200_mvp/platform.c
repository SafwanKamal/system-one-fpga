#include "../typed200_r5/service.h"
#include "../typed200_r5/sha256.h"
#include "../typed200_timed/pmu.h"
#include "ownership.h"
#include "supervisor.h"
__attribute__((section(".boot_config"),used)) volatile struct mvp_boot mvp_boot;
__attribute__((section(".owner_evidence"),used)) struct mvp_owner mvp_owner;
static uint32_t rd(void *c,uint32_t a){(void)c;return *(volatile uint32_t *)(uintptr_t)a;}
static void wr(void *c,uint32_t a,uint32_t v){(void)c;*(volatile uint32_t *)(uintptr_t)a=v;}
static void sync_io(void *c){(void)c;__asm__ volatile("dsb sy":::"memory");}
static const struct mvp_io io={0,rd,wr,sync_io};
__attribute__((section(".shared"),used)) volatile struct ty_shared ty_shared;
static struct ti_input input;
static struct ty_service service;
static void region(uint32_t i,uint32_t base,uint32_t size,uint32_t attrs) {
    __asm__ volatile("mcr p15,0,%0,c6,c2,0"::"r"(i):"memory");
    __asm__ volatile("mcr p15,0,%0,c6,c1,0"::"r"(base):"memory");
    __asm__ volatile("mcr p15,0,%0,c6,c1,2"::"r"(size):"memory");
    __asm__ volatile("mcr p15,0,%0,c6,c1,4"::"r"(attrs):"memory");
}
void ty_mpu_init(void) {
    for(uint32_t i=0;i<16;i++)region(i,0,0,0);
    region(0,0,0x1f,0x508);             /* 64 KiB ATCM, privileged RO, executable, NC */
    region(1,0x20000,0x1f,0x1108);      /* 64 KiB BTCM, privileged RW, XN, NC */
    region(2,0x60000000,0x33,0x150c);   /* 64 MiB shared DDR, privileged RW, XN, NC */
    region(3,0xa0000000,0x19,0x1105);   /* 8 KiB MMIO, privileged RW, XN, Device */
    region(4,0xf000,0x17,0x1108);       /* ATCM exception stacks, RW, XN, NC */
    region(5,0x62100000,0x17,0x110c); /* IDs only, 4 KiB RW; hidden stays RO */
    region(6,0xff5e0000,0x1f,0x1505); /* PS reset/clock Device RO */
    region(7,0xfd1a0000,0x1f,0x1505);
    region(8,0xff9a0000,0x1f,0x1505);
    region(9,0xff0a0000,0x1f,0x1505);
    region(10,0x2f180,0x09,0x1508); /* immutable PMU config 32 B */
    region(11,0x2f1c0,0x0b,0x1508); /* immutable boot config 64 B */
    uint32_t ctl;
    __asm__ volatile("dsb sy\n mrc p15,0,%0,c1,c0,0":"=r"(ctl)::"memory");
    ctl|=1; /* enable MPU; caches/background privileged region stay disabled */
    ctl&=~(1u<<17);
    __asm__ volatile("mcr p15,0,%0,c1,c0,0\n dsb sy\n isb"::"r"(ctl):"memory");
}
__attribute__((noreturn)) void ty_exception(uint32_t why) {
    (void)mvp_off(&io);
    ty_shared.exception_reason=why;ty_shared.boot_status=0x80000000u|why;
    for(;;)__asm__ volatile("wfi");
}
void ty_r5_main(void) {
    static const uint8_t expected[32]={0x41,0x29,0xba,0xde,0xd3,0x44,0x72,0x9c,0xcc,0x7e,0xf6,0xa3,0xf0,0xa2,0xb3,0x47,
        0x99,0x28,0x0a,0x91,0xd8,0x81,0x73,0xae,0x1c,0x0b,0x19,0x7c,0xde,0xf8,0xc3,0xbb};
    if(ty_shared.magic!=TY_CONFIG_MAGIC || ty_shared.version!=1 || !ty_shared.session)
        ty_exception(10);
    if(mvp_boot.magic!=MVP_MAGIC || mvp_boot.version!=1 || mvp_boot.session!=ty_shared.session ||
       mvp_boot.r5_hz!=MVP_R5_HZ || ty_pmu_config.cpu_hz!=MVP_R5_HZ ||
       ty_pmu_config.session!=mvp_boot.session)ty_exception(15);
    for(unsigned n=0;n<11;n++)if(mvp_boot.reserved[n])ty_exception(15);
    if(!mvp_off(&io))ty_exception(16);
    /* Bounded startup wait. A53_0 must reset itself BEFORE any admission. */
    unsigned wait=1000000;
    while((rd(0,0xfd1a0104)&15)!=15 && --wait){}
    if(!wait || !mvp_check(&io,&mvp_owner))ty_exception(17);
    volatile uint32_t *b=(volatile uint32_t *)0xa0000000;
    volatile uint32_t *permit=(volatile uint32_t *)0xa0001000;
    if(b[0xc0/4]!=TI200_ABI || (b[1]&30))ty_exception(12);
    permit[0]=0;__asm__ volatile("dmb sy":::"memory");
    uint8_t hash[32];ty_sha256((const volatile uint8_t *)0x60000000,33916928,hash);
    uint32_t d=0;for(unsigned i=0;i<32;i++)d|=(uint32_t)(hash[i]^expected[i]);
    if(d)ty_exception(11);
    /* Own PMU once; no control writes after bind/admission. Full-rate CC only. */
    uint32_t all=0xffffffffu,cc=0x80000000u,zero=0,control=7;
    __asm__ volatile("mcr p15,0,%0,c9,c12,2\n mcr p15,0,%0,c9,c14,2\n mcr p15,0,%0,c9,c12,3"::"r"(all):"memory");
    __asm__ volatile("mcr p15,0,%0,c9,c14,0\n mcr p15,0,%0,c9,c13,0"::"r"(zero):"memory");
    __asm__ volatile("mcr p15,0,%0,c9,c12,0\n isb"::"r"(control):"memory");
    __asm__ volatile("mcr p15,0,%0,c9,c12,1\n isb"::"r"(cc):"memory");
    if(!ty_pmu_bind(ty_shared.session))ty_exception(14);
    if(!ty_service_init(&service,b,permit,(volatile uint16_t *)1645215744,
                       (const volatile int8_t *)1645219840,&ty_shared,&input,1))ty_exception(12);
    for(;;){
        int step=mvp_step(&io,&mvp_owner,&service,ty_pmu_evidence.fault);
        if(step<0 || ty_pmu_evidence.fault)ty_exception(18);
        if(step>0){
            ty_shared.boot_status=2;
            for(;;)__asm__ volatile("wfi"); /* one-shot evidence; no concurrent client */
        }
    }
}
