#define _GNU_SOURCE
#include "ownership.h"
#include "vendor_regs.h"
#include "../typed200_r5/service.h"
#include "../typed200_timed/pmu.h"
#include "r5_payload.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <sys/mman.h>
extern void mvp_a53_main(void);
struct mvp_input {struct mvp_boot boot;struct ty_shared request;};
struct reg {uint32_t a,v;};static struct reg regs[128];static unsigned nr,stop,release_r5;
static int dma_stuck,deny_self;static jmp_buf finish;
static uint32_t *reg(uint32_t a){
    for(unsigned i=0;i<nr;i++)if(regs[i].a==a)return &regs[i].v;
    assert(nr<128);regs[nr].a=a;return &regs[nr++].v;
}
uint32_t mvp_mock_read(void *c,uint32_t a){(void)c;return *reg(a);}
void mvp_mock_barrier(void *c){(void)c;}
void mvp_mock_fault(uint32_t why){stop=why;longjmp(finish,1);}
void mvp_mock_write(void *c,uint32_t a,uint32_t v){
    (void)c;
    if(a==V_ADMA_CH0_ZDMA_CH_ISR){*reg(a)&=~v;return;}
    if(a==V_CRF_APB_RST_FPD_APU && (v&1)){
        if(deny_self)return;
        *reg(a)=v;stop=0x48414e44;longjmp(finish,1);
    }
    *reg(a)=v;
    if(a==V_ADMA_CH0_ZDMA_CH_CTRL2 && (v&1) && !dma_stuck){
        assert((*reg(V_CRL_APB_RST_LPD_TOP)&7)==3);
        assert((*reg(V_RPU_RPU_0_CFG)&1)==0);
        uint32_t dst=*reg(V_ADMA_CH0_ZDMA_CH_DST_DSCR_WORD0);
        assert(dst==0xffe00000||dst==0xffe20000);
        memset((void *)(uintptr_t)dst,0,65536);*reg(V_ADMA_CH0_ZDMA_CH_ISR)=0x400;
    }
    if(a==V_RPU_RPU_0_CFG&&(v&1)){
        assert((*reg(V_CRL_APB_RST_LPD_TOP)&7)==2);
        assert(*reg(V_CRL_APB_RST_LPD_IOU2)&0x20000);
        assert(*reg(MVP_PERMIT)==0);release_r5++;
    }
}
static void init(void){
    memset(regs,0,sizeof(regs));nr=stop=release_r5=0;dma_stuck=deny_self=0;
    memset((void *)(uintptr_t)0xffe00000,0xa5,65536);
    memset((void *)(uintptr_t)0xffe20000,0xa5,65536);
    for(size_t i=0;i<mvp_rule_count;i++)*reg(mvp_rules[i].address)=mvp_rules[i].expected;
    *reg(V_CRF_APB_RST_FPD_APU)=0;
    *reg(V_RPU_RPU_0_CFG)=0;*reg(V_CRL_APB_RESET_REASON)=1;
    *reg(0xa00000c0)=MVP_ABI;*reg(0xa00000cc)=2;
    struct mvp_input *cfg=(struct mvp_input *)(uintptr_t)0xfffee000;
    memset(cfg,0,sizeof(*cfg));cfg->boot.magic=MVP_MAGIC;cfg->boot.version=1;
    cfg->boot.session=0x12345678;cfg->boot.r5_hz=MVP_R5_HZ;
    cfg->request.magic=TY_CONFIG_MAGIC;cfg->request.version=1;cfg->request.session=cfg->boot.session;
    cfg->request.command_state=TY_CMD_READY;cfg->request.tokens=2;cfg->request.count=2;
    cfg->request.budget=100;cfg->request.sequence=1;cfg->request.ids[0]=101;cfg->request.ids[1]=102;
}
static void boot(void){if(!setjmp(finish))mvp_a53_main();}
int main(void){
    void *m=mmap((void *)(uintptr_t)0xffe00000,0x30000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    assert(m==(void *)(uintptr_t)0xffe00000);
    m=mmap((void *)(uintptr_t)0xfffc0000,0x40000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    assert(m==(void *)(uintptr_t)0xfffc0000);
    init();boot();assert(stop==0x48414e44&&release_r5==1);
    for(size_t i=0;i<R5_SEGMENTS;i++){
        const struct r5_segment *s=&r5_segments[i];const uint8_t *v=(const uint8_t *)(uintptr_t)(0xffe00000u+s->address);
        assert(!memcmp(v,s->data,s->filesz));
        /* Shared segment deliberately provisioned after NOLOAD zero. */
        if(s->address!=0x2f000)for(size_t j=s->filesz;j<s->memsz;j++)assert(v[j]==0);
    }
    const volatile struct mvp_boot *cfg=(const volatile struct mvp_boot *)(uintptr_t)0xffe2f1c0;
    const volatile struct ty_shared *shared=(const volatile struct ty_shared *)(uintptr_t)0xffe2f000;
    const volatile struct ty_pmu_config *pmu=(const volatile struct ty_pmu_config *)(uintptr_t)0xffe2f180;
    assert(cfg->magic==MVP_MAGIC&&shared->session==cfg->session&&pmu->session==cfg->session&&shared->ids[1]==102);
    struct mvp_owner o={0};const struct mvp_io io={0,mvp_mock_read,mvp_mock_write,mvp_mock_barrier};
    assert(mvp_check(&io,&o));
    init();deny_self=1;boot();assert(stop==0x81&&release_r5==1);o=(struct mvp_owner){0};
    assert(!mvp_check(&io,&o)&&!*reg(MVP_PERMIT));
    init();dma_stuck=1;boot();assert(stop==3&&release_r5==0&&!*reg(MVP_PERMIT));
    init();((struct mvp_input *)(uintptr_t)0xfffee000)->boot.session=0;boot();assert(stop==2&&release_r5==0);
    init();((struct mvp_input *)(uintptr_t)0xfffee000)->boot.reserved[10]=1;boot();assert(stop==2&&release_r5==0);
    init();((struct mvp_input *)(uintptr_t)0xfffee000)->request.session++;boot();assert(stop==2&&release_r5==0);
    init();*reg(V_CRL_APB_RESET_REASON)=0x10;boot();assert(stop==1&&release_r5==0);
    puts("PASS actual A53 C: TCM ECC mock/ELF load+readback/NOLOAD/config order, R5 release-before-self-reset, denied self reset, DMA timeout, stale/malformed config, warm reset");
    return 0;
}
