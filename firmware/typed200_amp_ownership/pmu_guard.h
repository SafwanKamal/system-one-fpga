#ifndef AMP_PMU_GUARD_H
#define AMP_PMU_GUARD_H
#include "xpfw_default.h"
#include "xpfw_module.h"
#include "ownership.h"
int AmpPmuIpi(u32,u32,const u32 *,u32);
int AmpPmuEvent(const XPfw_Module_t *,u32);
int AmpPmuClosed(void);
/* Trusted main-loop-only commit, with interrupts masked and earlier callbacks
 * returned. No IPI can activate/release this lease. Passing a session/gate mask
 * is not proof of the boot/ownership premises; caller integration is pending. */
int AmpPmuCommit(u64,u32);
int AmpPmuMatches(u64);
#endif
