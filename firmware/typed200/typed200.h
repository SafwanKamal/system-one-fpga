#ifndef SYSONE_TYPED200_H
#define SYSONE_TYPED200_H
#include "../typed_intent/typed_mailbox.h"
#define TI200_ABI 0x54590201u
/* Privileged deployment maps MMIO as Device and result DDR without cached aliases.
 * Calls are finite, non-polling. Actual memory/bus access time still needs a bound.
 */
int ti200_start(volatile uint32_t *,const struct ti_identity *,uint32_t budget,
                uint16_t tokens,uint16_t first,uint16_t count);
/* 0: not active, 1: matching active epoch, -1: identity/schema mismatch. */
int ti200_admission_observe(volatile uint32_t *,const struct ti_identity *,
                           uint16_t tokens,uint16_t first,uint16_t count);
/* Copies only after native complete/success/drain/environment checks.
 * dst and DDR result mapping are trusted, exclusively owned, properly sized.
 * Returns 1 on copy, 0 on not-ready/error. Never ACKs or proposes a result.
 */
int ti200_copy_hidden(volatile uint32_t *,const volatile int8_t *result,struct ti_input *dst);
#endif
