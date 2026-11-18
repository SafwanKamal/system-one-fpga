#include "typed_intent.h"
#include <float.h>
#include "generated/profile.inc"
_Static_assert(DBL_MANT_DIG==53 && DBL_MAX_EXP==1024, "binary64 required");
_Static_assert(sizeof(double)==8 && sizeof(int32_t)==4, "unsupported ABI");

const uint8_t *ti_contract(void) { return ti_contract_bytes; }
static int identity_equal(const struct ti_identity *a, const struct ti_identity *b) {
    uint32_t d=0;
    for (unsigned i=0;i<32;i++) d |= (uint32_t)(a->contract[i]^b->contract[i]);
    return a->session==b->session && a->request==b->request && d==0;
}
static int profile_equal(const uint8_t *p) {
    uint32_t d=0;
    for(unsigned i=0;i<32;i++) d |= (uint32_t)(p[i]^ti_contract_bytes[i]);
    return d==0;
}
/* C signed division truncates toward zero. Explicitly implement floor. */
static int64_t floor_q16(int64_t x) {
    return x>=0 ? x/65536 : -((-x+65535)/65536);
}
uint16_t ti_choose(const int32_t logits[TI_LABELS]) {
    uint16_t best=0;
    double maximum=(double)logits[0]*ti_scale[0];
    for(uint16_t c=1;c<TI_LABELS;c++) {
        double score=(double)logits[c]*ti_scale[c];
        if(score>maximum) { maximum=score; best=c; }
    }
    return best;
}
int ti_head(const struct ti_input *input, struct ti_head_result *out) {
    /* Always canonicalize output, including every rejected input. */
    for(unsigned c=0;c<TI_LABELS;c++) out->logits[c]=0;
    out->label=0;
    if(input->tokens==0 || input->tokens>TI_MAX_TOKENS || input->count==0 ||
       input->count>input->tokens) return 0;
    for(unsigned r=0;r<input->count;r++)
        if(input->rows[r]>=input->tokens || (r && input->rows[r]<=input->rows[r-1])) return 0;
    int32_t pooled[TI_HIDDEN];
    for(unsigned d=0;d<TI_HIDDEN;d++) {
        int64_t sum=0;
        for(unsigned r=0;r<input->count;r++)
            sum+=input->hidden[(unsigned)input->rows[r]*TI_HIDDEN+d];
        pooled[d]=(int32_t)floor_q16(sum*ti_recip[input->count]+32768);
    }
    for(unsigned c=0;c<TI_LABELS;c++) {
        int64_t acc=ti_bias[c];
        for(unsigned d=0;d<TI_HIDDEN;d++) acc+=(int64_t)pooled[d]*ti_weights[d*TI_LABELS+c];
        /* Generated profile verifies conservative absolute bound < INT32_MAX. */
        out->logits[c]=(int32_t)acc;
    }
    out->label=ti_choose(out->logits);
    return 1;
}
int ti_bridge_init(struct ti_bridge *b, uint64_t session) {
    b->identity.session=session; b->identity.request=0; b->last_request=0;
    b->proposed_label=0; b->proposed_outcome=0;
    for(unsigned i=0;i<32;i++) b->identity.contract[i]=ti_contract_bytes[i];
    b->state=session ? TI_IDLE : TI_QUARANTINE;
    return session!=0;
}
int ti_bridge_admitted(struct ti_bridge *b, const struct ti_identity *id) {
    if(b->state!=TI_IDLE || id->session!=b->identity.session ||
       id->request<=b->last_request || !profile_equal(id->contract)) return 0;
    b->identity=*id; b->last_request=id->request; b->state=TI_WAIT_CORE;
    b->proposed_label=0; b->proposed_outcome=0;
    return 1;
}
int ti_bridge_core(struct ti_bridge *b, int complete, int success, int live_quiet,
                   const struct ti_input *in, struct ti_proposal *p) {
    if(b->state!=TI_WAIT_CORE || !complete) return 0;
    p->identity=b->identity; p->label=0; p->reserved_score=0; p->outcome=TI_FAULT;
    if(success && live_quiet) {
        struct ti_head_result head;
        if(ti_head(in,&head)) { p->label=head.label; p->outcome=TI_ACCEPTED; }
        /* Bad head input after admission is a trusted-pipeline fault. */
    }
    b->proposed_label=p->label; b->proposed_outcome=p->outcome;
    b->state=TI_WAIT_TERMINAL;
    return 1;
}
int ti_bridge_terminal(struct ti_bridge *b, const struct ti_identity *id,
                       uint8_t outcome, uint16_t label, uint16_t reserved_score,
                       int live_quiet) {
    if((b->state!=TI_WAIT_CORE && b->state!=TI_WAIT_TERMINAL) ||
       !identity_equal(&b->identity,id)) return 0;
    if(outcome<TI_ACCEPTED || outcome>TI_INVALID || outcome==TI_FAULT ||
       outcome==TI_DEADLINE || !live_quiet ||
       reserved_score!=0 || (outcome!=TI_ACCEPTED && label!=0) ||
       (outcome==TI_ACCEPTED && (b->state!=TI_WAIT_TERMINAL ||
         b->proposed_outcome!=TI_ACCEPTED || label!=b->proposed_label))) b->state=TI_QUARANTINE;
    else b->state=TI_IDLE;
    return 1;
}
