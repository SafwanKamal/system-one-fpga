#include "service.h"
#include "sha256.h"
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
    region(2,0x60000000,0x33,0x110c);   /* 64 MiB shared DDR, privileged RW, XN, NC */
    region(3,0xa0000000,0x19,0x1105);   /* 8 KiB MMIO, privileged RW, XN, Device */
    region(4,0xf000,0x17,0x1108);       /* ATCM exception stacks, RW, XN, NC */
    uint32_t ctl;
    __asm__ volatile("dsb sy\n mrc p15,0,%0,c1,c0,0":"=r"(ctl)::"memory");
    ctl|=1; /* enable MPU; caches/background privileged region stay disabled */
    ctl&=~(1u<<17);
    __asm__ volatile("mcr p15,0,%0,c1,c0,0\n dsb sy\n isb"::"r"(ctl):"memory");
}
__attribute__((noreturn)) void ty_exception(uint32_t why) {
    ty_shared.exception_reason=why;ty_shared.boot_status=0x80000000u|why;
    for(;;)__asm__ volatile("wfi");
}
void ty_r5_main(void) {
    static const uint8_t expected[32]={0x41,0x29,0xba,0xde,0xd3,0x44,0x72,0x9c,0xcc,0x7e,0xf6,0xa3,0xf0,0xa2,0xb3,0x47,
        0x99,0x28,0x0a,0x91,0xd8,0x81,0x73,0xae,0x1c,0x0b,0x19,0x7c,0xde,0xf8,0xc3,0xbb};
    if(ty_shared.magic!=TY_CONFIG_MAGIC || ty_shared.version!=1 || !ty_shared.session || ty_shared.exclusive_buffers_attested!=1)
        ty_exception(10);
    volatile uint32_t *b=(volatile uint32_t *)0xa0000000;
    volatile uint32_t *permit=(volatile uint32_t *)0xa0001000;
    if(b[0xc0/4]!=TI200_ABI || (b[1]&30))ty_exception(12);
    permit[0]=0;__asm__ volatile("dmb sy":::"memory");
    uint8_t hash[32];ty_sha256((const volatile uint8_t *)0x60000000,33916928,hash);
    uint32_t d=0;for(unsigned i=0;i<32;i++)d|=(uint32_t)(hash[i]^expected[i]);
    if(d)ty_exception(11);
    if(!ty_service_init(&service,b,permit,(volatile uint16_t *)1645215744,
                       (const volatile int8_t *)1645219840,&ty_shared,&input,1))ty_exception(12);
    for(;;){ty_service_poll(&service);if(service.phase==TY_HALTED)ty_exception(13);}
}
