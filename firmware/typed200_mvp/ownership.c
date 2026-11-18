#include "ownership.h"
#include "vendor_regs.h"
#define FPD_MASK UINT32_C(0x000f007a) /* PCIe, DP, GDMA, GPU, SATA; preserve AFI */
#define IO2_MASK UINT32_C(0x00030061) /* ADMA, NAND, SDIO0/1, QSPI */
#define USB_MASK UINT32_C(0x00000fc0)
const struct mvp_rule mvp_rules[]={
 {V_CRF_APB_RST_FPD_APU,0xf,0xf},
 {V_CRF_APB_RST_FPD_TOP,FPD_MASK|0x80,FPD_MASK},
 {V_CRL_APB_RST_LPD_IOU0,0xf,0xf},
 {V_CRL_APB_RST_LPD_IOU2,IO2_MASK|0x40000,IO2_MASK},
 {V_CRL_APB_RST_LPD_TOP,USB_MASK|7,USB_MASK|2},
 {V_CRF_APB_DPDMA_REF_CTRL,0x01000000,0},
 {V_RPU_RPU_GLBL_CNTL,0x1fb,8}, /* split, TCM clock on/no wait, ARM/little endian */
 {V_RPU_RPU_0_CFG,5,1}, {V_RPU_RPU_1_CFG,1,0},
 {V_CRL_APB_PLL_STATUS,0x1b,0x1b},
 {V_CRL_APB_IOPLL_CTRL,0x07737f09,0x00013c00},
 {V_CRL_APB_RPLL_CTRL,0x07737f09,0x00014000},
 {V_CRL_APB_IOPLL_FRAC_CFG,0x80000000,0},
 {V_CRL_APB_RPLL_FRAC_CFG,0x80000000,0},
 {V_CRL_APB_CPU_R5_CTRL,0x03003f07,0x03000200},
 {V_CRL_APB_PL0_REF_CTRL,0x013f3f07,0x01010500},
 {V_CRL_APB_PL1_REF_CTRL,0x013f3f07,0x01010a00},
 {0xff0a0344,0x80000000,0x80000000}, /* EMIO reset direction */
 {0xff0a0348,0x80000000,0x80000000}, /* output enable */
 {0xff0a0054,0x80000000,0x80000000}  /* PL reset deasserted */
};
const size_t mvp_rule_count=sizeof(mvp_rules)/sizeof(mvp_rules[0]);
static int masked(const struct mvp_io *io,uint32_t a,uint32_t mask,uint32_t v){
    uint32_t old=io->read(io->ctx,a);
    io->write(io->ctx,a,(old&~mask)|v);io->barrier(io->ctx);
    return (io->read(io->ctx,a)&mask)==v;
}
static int exact(const struct mvp_io *io,uint32_t a,uint32_t v){
    io->write(io->ctx,a,v);io->barrier(io->ctx);return io->read(io->ctx,a)==v;
}
int mvp_off(const struct mvp_io *io){
    io->write(io->ctx,MVP_PERMIT,0);io->barrier(io->ctx);
    return io->read(io->ctx,MVP_PERMIT)==0;
}
int mvp_check(const struct mvp_io *io,struct mvp_owner *o){
    if(o->fault){(void)mvp_off(io);return 0;}
    for(size_t i=0;i<mvp_rule_count;i++){
        if((io->read(io->ctx,mvp_rules[i].address)&mvp_rules[i].mask)!=mvp_rules[i].expected){
            o->fault=(uint32_t)i+1;(void)mvp_off(io);return 0;
        }
    }
    if(o->checks==UINT32_MAX){o->fault=0x100;(void)mvp_off(io);return 0;}
    o->checks++;o->established=1;return 1;
}
int mvp_prepare(const struct mvp_io *io){
    if(!mvp_off(io))return 0;
    /* Explicit cold-POR prerequisite, no reset-history acknowledgement/clear. */
    uint32_t cause=io->read(io->ctx,V_CRL_APB_RESET_REASON);
    if(!(cause&3) || (cause&0x807c))return 0;
    if(io->read(io->ctx,0xa00000c0)!=MVP_ABI ||
       (io->read(io->ctx,0xa0000004)&30) ||
       !(io->read(io->ctx,0xa00000cc)&2))return 0;
    /* Check existing clock/reset profile BEFORE touching core state. */
    for(size_t i=9;i<mvp_rule_count;i++)
        if((io->read(io->ctx,mvp_rules[i].address)&mvp_rules[i].mask)!=mvp_rules[i].expected)return 0;
    if(!masked(io,V_RPU_RPU_0_CFG,1,0) || !masked(io,V_RPU_RPU_1_CFG,1,0))return 0;
    if(!masked(io,V_CRL_APB_RST_LPD_TOP,7,3))return 0;
    if(!masked(io,V_RPU_RPU_GLBL_CNTL,0x1fb,8))return 0;
    if(!masked(io,V_RPU_RPU_0_CFG,4,0))return 0;
    /* A53_0 still executes in OCM. Hold peers; self-reset is final handoff. */
    if(!masked(io,V_CRF_APB_RST_FPD_APU,0xe,0xe))return 0;
    if(!masked(io,V_CRF_APB_RST_FPD_TOP,FPD_MASK,FPD_MASK))return 0;
    if(!masked(io,V_CRL_APB_RST_LPD_IOU0,0xf,0xf))return 0;
    if(!masked(io,V_CRL_APB_RST_LPD_IOU2,IO2_MASK,IO2_MASK))return 0;
    if(!masked(io,V_CRL_APB_RST_LPD_TOP,USB_MASK,USB_MASK))return 0;
    if(!masked(io,V_CRF_APB_DPDMA_REF_CTRL,0x01000000,0))return 0;
    return 1;
}
int mvp_scrub_tcm(const struct mvp_io *io,uint32_t address,uint32_t polls){
    if((address!=0xffe00000 && address!=0xffe20000) || !polls)return 0;
    /* R5 halted/reset, TCM clock and RPU AMBA running. ADMA is sole temporary
       DMA owner. Reassert ADMA reset on EVERY exit, including timeout. */
    if(!masked(io,V_CRL_APB_RST_LPD_IOU2,0x20000,0)){
        (void)masked(io,V_CRL_APB_RST_LPD_IOU2,0x20000,0x20000);return 0;
    }
    uint32_t s=io->read(io->ctx,V_ADMA_CH0_ZDMA_CH_STATUS)&3;
    int ok=0;
    if(s!=0)goto done;
    io->write(io->ctx,V_ADMA_CH0_ZDMA_CH_ISR,0x400);
    io->barrier(io->ctx);
    if(io->read(io->ctx,V_ADMA_CH0_ZDMA_CH_ISR)&0x400)goto done;
    if(!exact(io,V_ADMA_CH0_ZDMA_CH_CTRL0,0x90))goto done;
    for(uint32_t a=V_ADMA_CH0_ZDMA_CH_WR_ONLY_WORD0;a<=V_ADMA_CH0_ZDMA_CH_WR_ONLY_WORD3;a+=4)
        if(!exact(io,a,0))goto done;
    if(!exact(io,V_ADMA_CH0_ZDMA_CH_DST_DSCR_WORD0,address) ||
       !exact(io,V_ADMA_CH0_ZDMA_CH_DST_DSCR_WORD1,0) ||
       !exact(io,V_ADMA_CH0_ZDMA_CH_DST_DSCR_WORD2,65536) ||
       !exact(io,V_ADMA_CH0_ZDMA_CH_SRC_DSCR_WORD2,65536))goto done;
    io->barrier(io->ctx);io->write(io->ctx,V_ADMA_CH0_ZDMA_CH_CTRL2,1);
    while(polls--){
        s=io->read(io->ctx,V_ADMA_CH0_ZDMA_CH_STATUS)&3;
        if(s==3)break;
        if(io->read(io->ctx,V_ADMA_CH0_ZDMA_CH_ISR)&0x400){
            ok=(io->read(io->ctx,V_ADMA_CH0_ZDMA_CH_STATUS)&3)!=3;break;
        }
    }
done:
    if(!masked(io,V_CRL_APB_RST_LPD_IOU2,0x20000,0x20000))ok=0;
    return ok;
}
int mvp_segment_valid(uint32_t a,size_t f,size_t m){
    if(f>m || m>65536)return 0;
    if(a<65536)return m<=65536-a;
    if(a>=0x20000 && a<0x30000)return m<=0x30000-a;
    return 0;
}
