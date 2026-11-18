#include "typed200.h"
static void barrier(void) {
#if defined(__arm__)
    __asm__ volatile("dmb sy" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}
static uint32_t word(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static int shape_valid(unsigned tokens,unsigned first,unsigned count) {
    return tokens>0 && tokens<=128 && count>0 && count<=tokens && first<tokens && count<=tokens-first;
}
int ti200_start(volatile uint32_t *b,const struct ti_identity *id,uint32_t budget,
                uint16_t tokens,uint16_t first,uint16_t count) {
    if(b[0xc0/4]!=TI200_ABI || (b[1]&1)==0 || !budget || !id->session || !id->request ||
       !shape_valid(tokens,first,count)) return 0;
    const uint8_t *profile=ti_contract();
    uint32_t mismatch=0;
    for(unsigned i=0;i<32;i++)mismatch|=(uint32_t)(id->contract[i]^profile[i]);
    uint64_t session=(uint64_t)b[0x80/4] | (uint64_t)b[0x84/4]<<32;
    if(mismatch || session!=id->session)return 0;
    b[0x1c/4]=(uint32_t)first<<16 | tokens;b[0x78/4]=count;
    ti_mmio_start(b,id,budget);
    return 1; /* command staged, NOT proof that work was admitted */
}
int ti200_admission_observe(volatile uint32_t *b,const struct ti_identity *id,
                           uint16_t tokens,uint16_t first,uint16_t count) {
    if(b[0xc0/4]!=TI200_ABI)return -1;
    if((b[1]&2)==0)return 0;
    barrier();
    uint64_t session=(uint64_t)b[0x80/4] | (uint64_t)b[0x84/4]<<32;
    uint64_t request=(uint64_t)b[0x88/4] | (uint64_t)b[0x8c/4]<<32;
    uint32_t mismatch=0;
    for(unsigned i=0;i<8;i++)mismatch|=b[0x90/4+i]^word(id->contract+4*i);
    if(session!=id->session || request!=id->request || mismatch ||
       b[0xc4/4]!=((uint32_t)first<<16 | tokens) || b[0xc8/4]!=count)return -1;
    return 1;
}
int ti200_copy_hidden(volatile uint32_t *b,const volatile int8_t *result,struct ti_input *dst) {
    if(b[0xc0/4]!=TI200_ABI || (b[0xcc/4]&31)!=30)return 0;
    barrier();
    uint32_t shape=b[0xc4/4],count=b[0xc8/4];
    unsigned tokens=shape&65535,first=shape>>16;
    if(!shape_valid(tokens,first,count))return 0;
    dst->tokens=(uint16_t)tokens;dst->count=(uint16_t)count;
    for(unsigned i=0;i<count;i++)dst->rows[i]=(uint16_t)(first+i);
    for(unsigned i=0;i<tokens*TI_HIDDEN;i++)dst->hidden[i]=result[i];
    barrier();
    return 1;
}
