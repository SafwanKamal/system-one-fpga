#ifndef AMP_ONE_SHOT_MAILBOX_H
#define AMP_ONE_SHOT_MAILBOX_H
#include "../typed200_r5/service.h"
enum {AMP_REQUEST_WORDS=160, AMP_RESULT_WORDS=32,
      AMP_REQUEST_MAGIC=0x41525131u, AMP_RESULT_MAGIC=0x41525331u,
      AMP_MB_BOOT=0, AMP_MB_READY=1, AMP_MB_BUSY=2, AMP_MB_SEALED=3};
/* Wire ABI: all words uint32_t, little endian. Request: magic/version/ready/
 * sequence/sessionLo/sessionHi/tokens/first/count/budget, six zero words,
 * 128 token IDs, sixteen zero words. Result: magic/version/published/sequence/
 * origin/outcome/label/score/elapsed/sessionLo/sessionHi/requestLo/requestHi,
 * 8 contract words in display-byte order, then 11 zero words.
 * origin=1 ONLY for an observed authoritative PL record. CPU rejection/fault=0.
 */
struct amp_mailbox {
 struct ty_service service;
 struct ty_shared private_shared;
 const volatile uint32_t *ingress;
 volatile uint32_t *result;
 uint64_t session;
 uint32_t phase;
};
/* Trusted boot only, fresh nonzero session, after real ownership ACKs. verified
 * is a caller precondition, NOT a new proof/activation mechanism. All private
 * state/input/code must be protected; ingress R5-RO/APU-RW, result R5-RW/APU-RO.
 * Calls are finite but AXI/DDR completion time is not bounded by this code.
 */
int amp_mailbox_init(struct amp_mailbox *,uint64_t,int,
 const volatile uint32_t *,volatile uint32_t *,volatile uint32_t *,
 volatile uint32_t *,volatile uint16_t *,const volatile int8_t *,struct ti_input *);
/* One request per cold-start session, including invalid requests. No retry,
 * ACK-driven buffer reuse, reset, cancellation or Linux-owned service state.
 * The finite captured word vector defines the request. Concurrent Linux writes
 * can produce a mixed vector; sequence recheck does NOT prove atomic capture.
 * No Linux reads occur after submission. Local PL deadline starts at admission,
 * not at Linux ready/store or R5 snapshot start. */
void amp_mailbox_poll(struct amp_mailbox *);
#endif
