#include "typed_mailbox.h"
static void barrier(void) {
#if defined(__arm__)
    __asm__ volatile("dmb sy" ::: "memory");
#else
    /* Host transport tests only. Target needs the ARM barrier above. */
    __asm__ volatile("" ::: "memory");
#endif
}
static uint32_t word(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void put64(volatile uint32_t *b,unsigned offset,uint64_t x) {
    b[offset/4]=(uint32_t)x;b[offset/4+1]=(uint32_t)(x>>32);
}
static uint64_t get64(volatile uint32_t *b,unsigned offset) {
    uint32_t lo=b[offset/4],hi=b[offset/4+1];
    return (uint64_t)lo | (uint64_t)hi<<32;
}
void ti_mmio_provision(volatile uint32_t *b,uint64_t session) {
    put64(b,8,session);barrier();b[0]=1;barrier();
}
void ti_mmio_start(volatile uint32_t *b,const struct ti_identity *id,uint32_t budget) {
    put64(b,0x10,id->request);b[0x18/4]=budget;
    for(unsigned i=0;i<8;i++)b[0x20/4+i]=word(id->contract+4*i);
    barrier();b[0]=2;barrier();
}
void ti_mmio_propose(volatile uint32_t *b,const struct ti_proposal *p) {
    put64(b,0x40,p->identity.session);put64(b,0x48,p->identity.request);
    for(unsigned i=0;i<8;i++)b[0x50/4+i]=word(p->identity.contract+4*i);
    b[0x70/4]=(uint32_t)p->label<<16 | p->outcome;b[0x74/4]=p->reserved_score;
    barrier();b[0]=4;barrier();
}
int ti_mmio_observe(volatile uint32_t *b,struct ti_record *r) {
    if((b[1]&4)==0)return 0;
    barrier();
    r->identity.session=get64(b,0x80);r->identity.request=get64(b,0x88);
    for(unsigned i=0;i<8;i++) {
        uint32_t x=b[0x90/4+i];
        for(unsigned j=0;j<4;j++)r->identity.contract[4*i+j]=(uint8_t)(x>>(8*j));
    }
    uint32_t payload=b[0xb0/4];
    r->outcome=(uint8_t)payload;r->label=(uint16_t)(payload>>16);
    r->reserved_score=(uint16_t)b[0xb4/4];r->elapsed=b[0xb8/4];
    barrier();return 1;
}
void ti_mmio_ack(volatile uint32_t *b) { barrier();b[0]=8;barrier(); }
