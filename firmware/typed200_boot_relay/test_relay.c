#define _GNU_SOURCE
#include "relay.h"
#include "../typed200_mvp/ownership.h"
#include "../typed200_r5/service.h"
#include "a53_payload.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
struct relay_input {struct mvp_boot boot;struct ty_shared request;};
struct reg {uint32_t a,v;};static struct reg regs[32];static unsigned nr,stop,jumped,corrupt,deny_permit;
static jmp_buf done;
static uint32_t *reg(uint32_t a){
    for(unsigned i=0;i<nr;i++)if(regs[i].a==a)return &regs[i].v;
    assert(nr<32);regs[nr].a=a;return &regs[nr++].v;
}
uint32_t relay_mock_read(uint32_t a){return *reg(a);}
void relay_mock_write(uint32_t a,uint32_t v){if(a!=MVP_PERMIT || !deny_permit)*reg(a)=v;}
void relay_mock_fault(uint32_t why){stop=why;longjmp(done,1);}
void relay_mock_jump(uint64_t a){assert(a==0xfffc0000);jumped++;longjmp(done,1);}
void relay_mock_after_copy(void){
    if(corrupt==1)*(volatile uint8_t *)(uintptr_t)0xfffc0000^=1;
    if(corrupt==2)*(volatile uint8_t *)(uintptr_t)RELAY_DEST_INPUT^=1;
}
static void init(void){
    memset(regs,0,sizeof(regs));nr=stop=jumped=corrupt=deny_permit=0;
    memset((void *)(uintptr_t)0xfffc0000,0xa5,0x40000);
    *reg(0xff5e0220)=1;*reg(0xfd1a0104)=14;*reg(0xff5e023c)=3;
    *reg(0xa00000c0)=MVP_ABI;*reg(0xa00000cc)=2;*reg(0xffca300c)=1;*reg(0xffca3010)=8;
    struct relay_input *in=(struct relay_input *)(uintptr_t)RELAY_INPUT;memset(in,0,sizeof(*in));
    in->boot.magic=MVP_MAGIC;in->boot.version=1;in->boot.session=0x12345678;in->boot.r5_hz=MVP_R5_HZ;
    in->request.magic=TY_CONFIG_MAGIC;in->request.version=1;in->request.session=in->boot.session;
    in->request.command_state=TY_CMD_READY;in->request.sequence=1;in->request.tokens=2;
    in->request.count=2;in->request.budget=10000000;in->request.ids[0]=101;in->request.ids[1]=102;
}
static void boot(void){if(!setjmp(done))relay_main();}
static void untouched(void){const uint8_t *p=(const uint8_t *)(uintptr_t)0xfffc0000;for(unsigned i=0;i<0x40000;i++)assert(p[i]==0xa5);}
int main(void){
    assert(mmap((void *)(uintptr_t)0x10000000,0x100000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==(void *)(uintptr_t)0x10000000);
    assert(mmap((void *)(uintptr_t)0xfffc0000,0x40000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==(void *)(uintptr_t)0xfffc0000);
    init();boot();assert(jumped==1&&stop==0&&!*reg(MVP_PERMIT)&&*reg(RELAY_STATUS)==2);
    for(size_t i=0;i<A53_SEGMENTS;i++){
        const struct a53_segment *s=&a53_segments[i];const uint8_t *p=(const uint8_t *)(uintptr_t)s->address;
        assert(!memcmp(p,s->data,s->filesz));for(size_t j=s->filesz;j<s->memsz;j++)assert(!p[j]);
    }
    assert(!memcmp((const void *)(uintptr_t)RELAY_INPUT,(const void *)(uintptr_t)RELAY_DEST_INPUT,448));
    const struct {uint32_t address,mask,why;} faults[]={
        {0xfd1a0104,14,3},{0xff5e023c,3,3},{0xa00000c0,0xffffffff,4},
        {0xa0000004,30,4},{0xa00000cc,2,4},{0xffc80008,0x1fff,5},
        {0xffc80808,0x1fff,5},{0xffca300c,1,5},{0xffca3010,8,5}};
    unsigned cases=0;
    for(size_t i=0;i<sizeof(faults)/sizeof(faults[0]);i++)for(unsigned b=0;b<32;b++)if(faults[i].mask&(UINT32_C(1)<<b)){
        init();*reg(faults[i].address)^=UINT32_C(1)<<b;boot();
        assert(!jumped&&stop==faults[i].why&&!*reg(MVP_PERMIT));untouched();cases++;
    }
    init();*reg(0xff5e0220)=0x11;boot();assert(stop==2&&!jumped);untouched();
    init();deny_permit=1;*reg(MVP_PERMIT)=1;boot();assert(stop==1&&!jumped);untouched();
    for(unsigned i=0;i<11;i++){init();((struct relay_input *)(uintptr_t)RELAY_INPUT)->boot.reserved[i]=1;boot();assert(stop==6&&!jumped);untouched();}
    init();((struct relay_input *)(uintptr_t)RELAY_INPUT)->request.session++;boot();assert(stop==6&&!jumped);untouched();
    init();((struct relay_input *)(uintptr_t)RELAY_INPUT)->boot.session=0;boot();assert(stop==6&&!jumped);untouched();
    init();corrupt=1;boot();assert(stop==8&&!jumped);
    init();corrupt=2;boot();assert(stop==8&&!jumped);
    for(uint64_t a=UINT64_C(0xfffb0000);a<UINT64_C(0xffff0000);a++){
        int expected=a>=UINT64_C(0xfffc0000)&&a<UINT64_C(0xfffe4000);
        assert(relay_destination_valid(a,1,1)==expected);
        assert(!relay_destination_valid(a,2,1));assert(!relay_destination_valid(a,0,0));
    }
    assert(!relay_destination_valid(UINT64_MAX,0,UINT64_MAX));
    assert(!relay_destination_valid(0xfffdffff,0,2)); /* must not cross code/stack window */
    printf("PASS actual relay C: exact frozen A53 bytes/NOLOAD/input; %u single-bit precondition faults; malformed/warm/permit/corrupt failures; 786432 range checks\n",cases);
    return 0;
}
