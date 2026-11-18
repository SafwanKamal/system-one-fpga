#ifndef SYSONE_TYPED_MAILBOX_H
#define SYSONE_TYPED_MAILBOX_H
#include "typed_intent.h"
struct ti_record {
    struct ti_identity identity;
    uint32_t elapsed;
    uint16_t label, reserved_score;
    uint8_t outcome;
};
/* base is a privileged Device-memory mapping. Exclusive owner, no concurrent ACK.
 * Finite instruction/transaction counts do NOT bound AXI completion latency.
 * These calls do not poll, retry, reset, allocate, or change boot configuration.
 */
void ti_mmio_provision(volatile uint32_t *base, uint64_t fresh_session);
void ti_mmio_start(volatile uint32_t *base, const struct ti_identity *, uint32_t budget);
void ti_mmio_propose(volatile uint32_t *base, const struct ti_proposal *);
/* One observation; 0 means not yet terminal. Never ACKs or releases ownership. */
int ti_mmio_observe(volatile uint32_t *base, struct ti_record *);
void ti_mmio_ack(volatile uint32_t *base);
#endif
