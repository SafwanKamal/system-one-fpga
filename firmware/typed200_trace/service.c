#include "trace.h"
static void fence(void){
#if defined(__arm__)
    __asm__ volatile("dmb sy":::"memory");
#else
    __asm__ volatile("":::"memory");
#endif
}
static int identity_ok(const struct ti_identity *a,const struct ti_identity *b) {
    uint32_t d=0;for(unsigned i=0;i<32;i++)d|=(uint32_t)(a->contract[i]^b->contract[i]);
    return !d && a->session==b->session && a->request==b->request;
}
static void output(struct ty_service *c,const struct ti_record *r,uint32_t origin) {
    /* Serialize members explicitly: structure assignment may copy stack padding. */
    volatile struct ti_record *dst=&c->shared->result;
    volatile unsigned char *bytes=(volatile unsigned char *)dst;
    for(unsigned i=0;i<sizeof(*dst);i++)bytes[i]=0;
    dst->identity.session=r->identity.session;dst->identity.request=r->identity.request;
    for(unsigned i=0;i<32;i++)dst->identity.contract[i]=r->identity.contract[i];
    dst->elapsed=r->elapsed;dst->label=r->label;dst->reserved_score=r->reserved_score;
    dst->outcome=r->outcome;
    c->shared->result_origin=origin;c->shared->result_sequence=c->sequence;
    ty_trace_shared(c,origin);
    fence();c->shared->command_state=TY_CMD_DONE;
    ty_trace_event(c,TR_SHARED_DONE);
}
static void reject(struct ty_service *c) {
    struct ti_record r={0};r.identity=c->identity;r.outcome=TI_INVALID;
    output(c,&r,0);ty_trace_finish(c);
}
static void invalid_terminal(struct ty_service *c) {
    struct ti_record r={0};r.identity=c->identity;r.outcome=TI_FAULT;
    c->phase=TY_HALTED;output(c,&r,0);ty_trace_finish(c);
}
int ty_service_init(struct ty_service *c,volatile uint32_t *b,volatile uint32_t *permit,
                    volatile uint16_t *ids,const volatile int8_t *hidden,volatile struct ty_shared *shared,
                    struct ti_input *input,int verified) {
    c->mmio=b;c->permit=permit;c->ids=ids;c->hidden=hidden;c->shared=shared;c->input=input;
    c->phase=TY_HALTED;c->next_request=1;c->last_sequence=0;c->sequence=0;
    permit[0]=0;fence();
    if(!verified || shared->magic!=TY_CONFIG_MAGIC || shared->version!=TY_SHARED_VERSION ||
       !shared->session || shared->exclusive_buffers_attested!=1 || b[0xc0/4]!=TI200_ABI || (b[1]&30))return 0;
    c->identity.session=shared->session;c->identity.request=0;
    for(unsigned i=0;i<32;i++)c->identity.contract[i]=ti_contract()[i];
    if(!ti_bridge_init(&c->bridge,c->identity.session))return 0;
    ty_trace_reset();ty_trace_event(c,TR_INIT);
    b[8/4]=(uint32_t)c->identity.session;b[12/4]=(uint32_t)(c->identity.session>>32);
    fence();b[0]=1;fence();c->phase=TY_BOOT_WAIT;return 1;
}
static int terminal(struct ty_service *c) {
    struct ti_record r;
    if(!ti200_terminal_observe(c->mmio,&r))return 0;
    ty_trace_event(c,TR_TERMINAL_OBSERVED);ty_trace_pl(c);
    uint32_t native=c->mmio[0xcc/4];
    if(!identity_ok(&r.identity,&c->identity) || r.outcome<1 || r.outcome>6 || r.reserved_score ||
       (r.outcome!=TI_ACCEPTED && r.label)) {invalid_terminal(c);return 1;}
    if(c->phase==TY_ADMISSION) {
        // A very short deadline can expire before ARM observes ACTIVE.
        if(r.outcome<TI_FAULT || r.label){invalid_terminal(c);return 1;}
        else c->phase=r.outcome==TI_INVALID && (native&2) ? TY_IDLE:TY_HALTED;
    } else {
        if(!ti_bridge_terminal(&c->bridge,&r.identity,r.outcome,r.label,r.reserved_score,(native&2)!=0)) {
            invalid_terminal(c);return 1;
        }
        c->phase=c->bridge.state==TI_IDLE ? TY_IDLE:TY_HALTED;
        if(r.outcome==TI_ACCEPTED && c->phase!=TY_IDLE){invalid_terminal(c);return 1;}
    }
    output(c,&r,1);
    if(c->phase==TY_IDLE){fence();c->mmio[0]=8;fence();ty_trace_event(c,TR_ACK_WRITTEN);}
    ty_trace_finish(c);
    return 1;
}
void ty_service_poll(struct ty_service *c) {
    if(c->phase==TY_HALTED)return;
    if(c->phase==TY_BOOT_WAIT) {
        uint64_t s=(uint64_t)c->mmio[0x80/4]|(uint64_t)c->mmio[0x84/4]<<32;
        if((c->mmio[1]&16) && s==c->identity.session){c->permit[0]=1;fence();c->phase=TY_IDLE;c->shared->boot_status=1;ty_trace_event(c,TR_BOOT_READY);}
        return;
    }
    if(c->phase!=TY_IDLE && terminal(c))return;
    if(c->phase==TY_IDLE) {
        if(c->shared->command_state!=TY_CMD_READY)return;
        fence();c->sequence=c->shared->sequence;
        c->tokens=c->shared->tokens;c->first=c->shared->first;c->count=c->shared->count;
        uint32_t budget=c->shared->budget;uint16_t ids[128];
        int valid=c->sequence && c->sequence>c->last_sequence && !c->shared->reserved &&
            c->tokens>0 && c->tokens<=128 && c->count>0 && c->count<=c->tokens &&
            c->first<c->tokens && c->count<=c->tokens-c->first && budget;
        if(valid)for(unsigned i=0;i<c->tokens;i++){ids[i]=c->shared->ids[i];if(ids[i]>=30522)valid=0;}
        fence();if(c->sequence!=c->shared->sequence || c->shared->command_state!=TY_CMD_READY)valid=0;
        if(c->sequence>c->last_sequence)c->last_sequence=c->sequence;
        if(!valid){reject(c);return;}
        if(!c->next_request){c->phase=TY_HALTED;return;}
        c->identity.request=c->next_request++;
        c->shared->command_state=TY_CMD_BUSY;
        for(unsigned i=0;i<c->tokens;i++)c->ids[i]=ids[i];
        fence();
        if(!ti200_start(c->mmio,&c->identity,budget,c->tokens,c->first,c->count)){c->phase=TY_HALTED;return;}
        c->phase=TY_ADMISSION;ty_trace_event(c,TR_START_SUBMITTED);return;
    }
    if(c->phase==TY_ADMISSION) {
        int seen=ti200_admission_observe(c->mmio,&c->identity,c->tokens,c->first,c->count);
        if(seen<0){c->phase=TY_HALTED;return;}
        if(seen){if(ti_bridge_admitted(&c->bridge,&c->identity)){c->phase=TY_CORE;ty_trace_event(c,TR_ADMISSION_OBSERVED);}else c->phase=TY_HALTED;}
        return;
    }
    if(c->phase==TY_CORE) {
        uint32_t native=c->mmio[0xcc/4];if((native&8)==0)return;
        ty_trace_event(c,TR_NATIVE_OBSERVED);
        int success=(native&31)==30;
        if(success){ty_trace_event(c,TR_COPY_BEGIN);
            if(!ti200_copy_hidden(c->mmio,c->hidden,c->input))success=0;
            ty_trace_event(c,TR_COPY_END);}
        ty_trace_event(c,TR_HEAD_BEGIN);
        int proposal_ready=ti_bridge_core(&c->bridge,1,success,(native&2)!=0,c->input,&c->proposal);
        ty_trace_event(c,TR_HEAD_END);
        if(proposal_ready) {
            ty_trace_event(c,TR_PROPOSAL_BEGIN);
            ti200_propose(c->mmio,&c->proposal);c->phase=TY_TERMINAL;
            ty_trace_event(c,TR_PROPOSAL_END);
        }
    }
}
