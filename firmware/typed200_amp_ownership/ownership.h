#ifndef TYPED200_AMP_OWNERSHIP_H
#define TYPED200_AMP_OWNERSHIP_H
#include <stdint.h>
#include <stddef.h>
/* Candidate boot-time engine. Caller executes in trusted, protected memory,
 * with every affected bus master quiescent. Never call on a running Linux SoC. */
struct amp_write { uint32_t address,mask,value; };
struct amp_io {
 void *ctx;
 uint32_t (*read)(void *,uint32_t);
 void (*write)(void *,uint32_t,uint32_t);
 void (*barrier)(void *);
};
enum {AMP_BOOT=0,AMP_OWNED=1,AMP_QUARANTINED=2};
enum {AMP_GATES=0x7fu};
#define AMP_PERMIT UINT32_C(0xa0001000)
struct amp_owner {uint32_t phase,failed_step;uint64_t session;};
/* All seven proofs must be discharged by a trusted loader: inventory/recovery,
 * quiescence, memory map/reservation, source tags, secure/PM policy, physical
 * timing/integration, and startup/service composition. A caller-set flag is
 * NOT a replacement for those proofs. No API here raises the FPGA permit. */
int amp_install(const struct amp_io *,struct amp_owner *,uint64_t,uint32_t,
                const struct amp_write *,size_t);
/* Active one-shot PM lease: read-only queries only. No Linux-origin clock,
 * reset, power, MMIO, IOCTL, pinmux, FPGA or configuration mutation is allowed.
 * ipi source is the controller-observed mask, never a payload claim. */
int amp_pm_allow(const struct amp_owner *,uint32_t ipi,uint32_t source,
                 const uint32_t *,size_t);
int amp_pm_event_allow(const struct amp_owner *,int is_safety);
#endif
