#include "typed200.h"
static void barrier(void) {
#if defined(__arm__)
    __asm__ volatile("dmb sy" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}
/* SHA bytes use conventional display order; register index 0 is the numeric
 * digest's LEAST significant word. Each word is assembled in digest byte order.
 */
static uint32_t digest_word(const uint8_t *digest,unsigned index) {
    const uint8_t *p=digest+28-4*index;
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | (uint32_t)p[3];
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
    b[0x10/4]=(uint32_t)id->request;b[0x14/4]=(uint32_t)(id->request>>32);b[0x18/4]=budget;
    for(unsigned i=0;i<8;i++)b[0x20/4+i]=digest_word(id->contract,i);
    barrier();b[0]=2;barrier();
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
    for(unsigned i=0;i<8;i++)mismatch|=b[0x90/4+i]^digest_word(id->contract,i);
    if(session!=id->session || request!=id->request || mismatch ||
       b[0xc4/4]!=((uint32_t)first<<16 | tokens) || b[0xc8/4]!=count)return -1;
    return 1;
}
void ti200_propose(volatile uint32_t *b,const struct ti_proposal *p) {
    b[0x40/4]=(uint32_t)p->identity.session;b[0x44/4]=(uint32_t)(p->identity.session>>32);
    b[0x48/4]=(uint32_t)p->identity.request;b[0x4c/4]=(uint32_t)(p->identity.request>>32);
    for(unsigned i=0;i<8;i++)b[0x50/4+i]=digest_word(p->identity.contract,i);
    b[0x70/4]=(uint32_t)p->label<<16 | p->outcome;b[0x74/4]=p->reserved_score;
    barrier();b[0]=4;barrier();
}
int ti200_terminal_observe(volatile uint32_t *b,struct ti_record *r) {
    if(b[0xc0/4]!=TI200_ABI || (b[1]&4)==0)return 0;
    barrier();
    r->identity.session=(uint64_t)b[0x80/4] | (uint64_t)b[0x84/4]<<32;
    r->identity.request=(uint64_t)b[0x88/4] | (uint64_t)b[0x8c/4]<<32;
    for(unsigned i=0;i<8;i++) {
        uint32_t x=b[0x90/4+i];unsigned offset=28-4*i;
        r->identity.contract[offset]=(uint8_t)(x>>24);
        r->identity.contract[offset+1]=(uint8_t)(x>>16);
        r->identity.contract[offset+2]=(uint8_t)(x>>8);
        r->identity.contract[offset+3]=(uint8_t)x;
    }
    uint32_t payload=b[0xb0/4];r->outcome=(uint8_t)payload;r->label=(uint16_t)(payload>>16);
    r->reserved_score=(uint16_t)b[0xb4/4];r->elapsed=b[0xb8/4];
    barrier();return 1;
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
