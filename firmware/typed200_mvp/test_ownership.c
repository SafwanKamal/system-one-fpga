#include "ownership.h"
#include "vendor_regs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct reg {uint32_t a,v;};
static struct reg regs[128];static unsigned nr,writes,deny_write,reads;
static int dma_mode;
static uint32_t *reg(uint32_t a){
    for(unsigned i=0;i<nr;i++)if(regs[i].a==a)return &regs[i].v;
    assert(nr<128);regs[nr].a=a;return &regs[nr++].v;
}
static uint32_t rd(void *c,uint32_t a){(void)c;reads++;return *reg(a);}
static void wr(void *c,uint32_t a,uint32_t v){
    (void)c;writes++;if(writes==deny_write)return;
    if(a==V_ADMA_CH0_ZDMA_CH_ISR){*reg(a)&=~v;return;}
    *reg(a)=v;
    if(a==V_ADMA_CH0_ZDMA_CH_CTRL2 && (v&1)){
        if(dma_mode==0)*reg(V_ADMA_CH0_ZDMA_CH_ISR)=0x400;
        if(dma_mode==2)*reg(V_ADMA_CH0_ZDMA_CH_STATUS)=3;
    }
}
static void barrier(void *c){(void)c;}
static const struct mvp_io io={0,rd,wr,barrier};
static void init(void){
    memset(regs,0,sizeof(regs));nr=reads=writes=deny_write=0;dma_mode=0;
    for(size_t i=0;i<mvp_rule_count;i++)*reg(mvp_rules[i].address)=mvp_rules[i].expected;
    *reg(V_CRL_APB_RESET_REASON)=1;*reg(0xa00000c0)=MVP_ABI;*reg(0xa00000cc)=2;
}
int main(void){
    unsigned mutations=0;
    init();struct mvp_owner o={0};assert(mvp_check(&io,&o)&&o.established&&o.checks==1);
    /* Every compared bit, both reset and clock/GPIO expectations. */
    for(size_t i=0;i<mvp_rule_count;i++)for(unsigned b=0;b<32;b++)if(mvp_rules[i].mask&(UINT32_C(1)<<b)){
        init();o=(struct mvp_owner){0};*reg(MVP_PERMIT)=1;
        *reg(mvp_rules[i].address)^=UINT32_C(1)<<b;
        assert(!mvp_check(&io,&o)&&o.fault==i+1&&!*reg(MVP_PERMIT));
        *reg(mvp_rules[i].address)^=UINT32_C(1)<<b;
        assert(!mvp_check(&io,&o));mutations++;
    }
    init();o=(struct mvp_owner){0,UINT32_MAX,1};assert(!mvp_check(&io,&o));
    init();assert(mvp_prepare(&io));unsigned prepare_writes=writes;
    assert((*reg(V_CRL_APB_RST_LPD_TOP)&7)==3);
    assert((*reg(V_CRF_APB_RST_FPD_TOP)&0x80)==0); /* active encoder AFI preserved */
    for(unsigned i=1;i<=prepare_writes;i++){
        init();/* make every requested mutation necessary */
        *reg(MVP_PERMIT)=1;*reg(V_RPU_RPU_0_CFG)=5;*reg(V_RPU_RPU_1_CFG)=1;
        *reg(V_RPU_RPU_GLBL_CNTL)=0x50;*reg(V_CRL_APB_RST_LPD_TOP)=4;
        *reg(V_CRF_APB_RST_FPD_APU)=0;*reg(V_CRF_APB_RST_FPD_TOP)=0;
        *reg(V_CRL_APB_RST_LPD_IOU0)=0;*reg(V_CRL_APB_RST_LPD_IOU2)=0;
        *reg(V_CRF_APB_DPDMA_REF_CTRL)=0x01000000;
        deny_write=i;assert(!mvp_prepare(&io));
    }
    for(unsigned b=2;b<7;b++){init();*reg(V_CRL_APB_RESET_REASON)|=1u<<b;assert(!mvp_prepare(&io));}
    init();*reg(V_CRL_APB_RESET_REASON)=0;assert(!mvp_prepare(&io));
    init();*reg(0xa00000c0)=0;assert(!mvp_prepare(&io));
    init();*reg(0xa0000004)=2;assert(!mvp_prepare(&io));
    init();*reg(0xa00000cc)=0;assert(!mvp_prepare(&io));
    for(int mode=0;mode<3;mode++){
        init();dma_mode=mode;assert(mvp_scrub_tcm(&io,0xffe00000,4)==(mode==0));
        assert(*reg(V_CRL_APB_RST_LPD_IOU2)&0x20000);
    }
    init();assert(!mvp_scrub_tcm(&io,0xffe10000,10)&&writes==0);
    assert(!mvp_scrub_tcm(&io,0xffe20000,0)&&writes==0);
    for(uint32_t a=0;a<0x40000;a++){
        int expected=(a<0x10000)||(a>=0x20000&&a<0x30000);
        assert(mvp_segment_valid(a,1,1)==expected);
        assert(!mvp_segment_valid(a,2,1));
        assert(!mvp_segment_valid(a,0,65537));
    }
    assert(mvp_segment_valid(0,65536,65536));assert(mvp_segment_valid(0x20000,0,65536));
    assert(!mvp_segment_valid(UINT32_MAX,0,SIZE_MAX));
    printf("PASS ownership: %u single-bit faults sticky/permit-low, reset/clock/profile failures, DMA done/error/timeout, 786432 segment checks\n",mutations);
    return 0;
}
