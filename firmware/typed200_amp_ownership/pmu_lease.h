#ifndef AMP_PMU_LEASE_H
#define AMP_PMU_LEASE_H
#include "pmu_guard.h"
enum {AMP_LEASE_CLOSE=0x007f0001u,AMP_LEASE_STATUS=0x007f0002u,
      AMP_LEASE_ABI=0x41504d31u,AMP_LEASE_PENDING=0x53590001u,
      AMP_LEASE_ACK=0x53590002u};
/* Trusted R5 only; source is controller-observed. This transport does not
 * establish ATF closure, image identity, physical source tags, or boot gates.
 * R5 must discharge them before sending CLOSE. ACK means PMU dispatch closed
 * at a main-loop boundary for this session, never permission to admit alone.
 * Eight words: opcode/sessionLo/sessionHi/ABI/gates/0/0/0.
 * Response: status/sessionLo/sessionHi/ABI/0/0/0/0. No Linux activation API.
 */
int AmpPmuLeaseIpi(u32,u32,const u32 *,u32);
/* Main loop only, after any existing callback/interrupt handler has returned.
 * Never a scheduler callback or IPI handler. Does not raise FPGA permit. */
void AmpPmuLeasePoll(void);
#endif
