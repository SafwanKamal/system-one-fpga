#ifndef SYSONE_TYPED_INTENT_H
#define SYSONE_TYPED_INTENT_H
#include <stdint.h>

enum { TI_HIDDEN=384, TI_MAX_TOKENS=128, TI_LABELS=18 };
enum ti_outcome { TI_ACCEPTED=1, TI_CLARIFY=2, TI_ABSTAIN=3,
    TI_FAULT=4, TI_DEADLINE=5, TI_INVALID=6 };
struct ti_input {
    int8_t hidden[TI_MAX_TOKENS * TI_HIDDEN];
    uint16_t rows[TI_MAX_TOKENS];
    uint16_t tokens, count;
};
struct ti_head_result { int32_t logits[TI_LABELS]; uint16_t label; };
/* Trusted immutable buffers, exclusively owned for the entire call. */
int ti_head(const struct ti_input *, struct ti_head_result *);
uint16_t ti_choose(const int32_t logits[TI_LABELS]);
const uint8_t *ti_contract(void);

struct ti_identity { uint64_t session, request; uint8_t contract[32]; };
struct ti_proposal {
    struct ti_identity identity;
    uint16_t label, reserved_score;
    uint8_t outcome;
};
enum ti_bridge_state { TI_IDLE, TI_WAIT_CORE, TI_WAIT_TERMINAL, TI_QUARANTINE };
struct ti_bridge {
    struct ti_identity identity;
    uint64_t last_request;
    enum ti_bridge_state state;
    uint16_t proposed_label;
    uint8_t proposed_outcome;
};
/* Initialization is outside admission; session MUST be fresh across resets. */
int ti_bridge_init(struct ti_bridge *, uint64_t session);
/* Called only AFTER matching validated PL admission and verified model deployment. */
int ti_bridge_admitted(struct ti_bridge *, const struct ti_identity *);
/* One bounded call, no polling. Returns 1 exactly when it emits a proposal. */
int ti_bridge_core(struct ti_bridge *, int complete, int success, int live_quiet,
                   const struct ti_input *, struct ti_proposal *);
/* Observe a stable authoritative PL record before releasing buffer ownership. */
int ti_bridge_terminal(struct ti_bridge *, const struct ti_identity *,
                       uint8_t outcome, uint16_t label, uint16_t reserved_score,
                       int live_quiet);
#endif
