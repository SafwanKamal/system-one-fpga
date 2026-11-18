#ifndef AMP_ATF_GUARD_H
#define AMP_ATF_GUARD_H
#include <stdint.h>
#include "ownership.h"
/* Secure boot agent only; deliberately NOT exposed as a non-secure SMC API.
 * Boot activation/ack and cross-CPU quiescence still require composition. */
int AmpAtfCommit(uint64_t,uint32_t);
/* Acquires the service lock whether returning allow or deny. Caller MUST
 * release after the original handler returns, or before returning a denial. */
int AmpAtfLockAllow(uint32_t,uint64_t,uint64_t,uint64_t);
int AmpAtfIpiLockAllow(uint32_t,uint64_t,uint64_t,uint64_t,uint64_t);
void AmpAtfUnlock(void);
#endif
