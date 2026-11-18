#include "trace.h"
volatile struct ty_trace_record ty_trace;
static uint32_t (*clock_read)(void);
static uint32_t clock_source,clock_hz;
static void barrier(void) {
#if defined(__arm__)
    __asm__ volatile("dmb sy":::"memory");
#else
    __asm__ volatile("":::"memory");
#endif
}
void ty_trace_clock(uint32_t (*fn)(void),uint32_t source,uint32_t hz) {
    clock_read=fn && source && hz ? fn:0;
    clock_source=clock_read ? source:0;clock_hz=clock_read ? hz:0;
}
void ty_trace_reset(void) {
    volatile unsigned char *p=(volatile unsigned char *)&ty_trace;
    for(unsigned i=0;i<sizeof(ty_trace);i++)p[i]=0;
    ty_trace.magic=TY_TRACE_MAGIC;ty_trace.version=1;
    ty_trace.clock_source=clock_source;ty_trace.clock_hz=clock_hz;
    ty_trace.clock_valid=clock_read!=0;
}
void ty_trace_event(struct ty_service *c,uint32_t kind) {
    if(ty_trace.committed)return;
    uint32_t n=ty_trace.event_count;
    if(n>=TY_TRACE_EVENTS){if(ty_trace.dropped!=UINT32_MAX)ty_trace.dropped++;return;}
    volatile struct ty_trace_event *e=&ty_trace.events[n];
    e->kind=kind;e->tick=clock_read ? clock_read():0;
    e->sequence=c->sequence;e->phase=(uint32_t)c->phase;e->request=c->identity.request;
    barrier();ty_trace.event_count=n+1;
}
void ty_trace_pl(struct ty_service *c) {
    if(ty_trace.committed || ty_trace.pl_present)return;
    /* Only defined read-only CSR offsets. Reading all64 words would SLVERR on
       write-only/unmapped addresses. No reconstructed decoded payload here. */
    static const unsigned char offsets[]={0x04,0x80,0x84,0x88,0x8c,
        0x90,0x94,0x98,0x9c,0xa0,0xa4,0xa8,0xac,0xb0,0xb4,0xb8,
        0xc0,0xc4,0xc8,0xcc,0xd0,0xd4};
    ty_trace_event(c,TR_CAPTURE_BEGIN);barrier();
    for(unsigned i=0;i<sizeof(offsets);i++)
        ty_trace.pl_words[offsets[i]/4]=c->mmio[offsets[i]/4];
    barrier();ty_trace.pl_status_after=c->mmio[1];
    ty_trace.pl_present=1;ty_trace_event(c,TR_CAPTURE_END);
}
void ty_trace_shared(struct ty_service *c,uint32_t origin) {
    if(ty_trace.committed || ty_trace.shared_present)return;
    const volatile unsigned char *p=(const volatile unsigned char *)c->shared;
    for(unsigned i=0;i<sizeof(ty_trace.shared);i++)ty_trace.shared[i]=p[i];
    /* Snapshot fields before releasing producer ownership. Reflect the known
       final command_state store, not a racy read after publishing DONE. */
    ty_trace.shared[24]=TY_CMD_DONE;ty_trace.shared[25]=0;
    ty_trace.shared[26]=0;ty_trace.shared[27]=0;
    ty_trace.session=c->identity.session;ty_trace.request=c->identity.request;
    ty_trace.sequence=c->sequence;ty_trace.origin=origin;
    barrier();ty_trace.shared_present=1;
}
void ty_trace_finish(struct ty_service *c) {
    if(ty_trace.committed)return;
    ty_trace_event(c,TR_FINISH);barrier();ty_trace.committed=1;
}
