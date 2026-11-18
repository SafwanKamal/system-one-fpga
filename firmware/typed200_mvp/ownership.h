#ifndef MVP_OWNERSHIP_H
#define MVP_OWNERSHIP_H
#include <stdint.h>
#include <stddef.h>
/* Cold boot only. PMU/CSU/authenticated loader/debug are trusted, quiescent TCB.
 * No Linux or concurrent A53 client. This is not an adversarial PS firewall. */
#define MVP_PERMIT UINT32_C(0xa0001000)
#define MVP_ABI UINT32_C(0x54590201)
#define MVP_MAGIC UINT32_C(0x4d565031)
#define MVP_R5_HZ UINT32_C(533328000) /* declared 33.333 MHz ref; not calibrated */
struct mvp_io {
    void *ctx;
    uint32_t (*read)(void *,uint32_t);
    void (*write)(void *,uint32_t,uint32_t);
    void (*barrier)(void *);
};
struct mvp_rule {uint32_t address,mask,expected;};
extern const struct mvp_rule mvp_rules[];
extern const size_t mvp_rule_count;
struct mvp_owner {uint32_t fault,checks,established;};
struct mvp_boot {uint32_t magic,version;uint64_t session;uint32_t r5_hz,reserved[11];};
_Static_assert(sizeof(struct mvp_boot)==64,"boot ABI");
int mvp_off(const struct mvp_io *io);
int mvp_check(const struct mvp_io *io,struct mvp_owner *owner);
/* A53 EL3, cold boot, caches/MMU off, model/request already loaded.
 * This function prepares exclusivity but does NOT assert A53_0 reset itself.
 * Only R5 observing ALL A53 resets completes ownership. */
int mvp_prepare(const struct mvp_io *io);
int mvp_scrub_tcm(const struct mvp_io *io,uint32_t address,uint32_t polls);
int mvp_segment_valid(uint32_t address,size_t filesz,size_t memsz);
#endif
