#ifndef TYPED_BOOT_SEAL_POLICY_H
#define TYPED_BOOT_SEAL_POLICY_H
#include <stdint.h>
#define TB_MODULE 0x53u
#define TB_REQUEST 0x00530001u
#define TB_MAGIC 0x53594f4eu
#define TB_VERSION 1u
/* One cold-boot lifetime. No clear/unseal entry point. Not a hostile-master firewall. */
struct tb_seal { uint32_t pending, closed, lo, hi; };
enum { TB_OK=0, TB_INVALID=1, TB_BUSY=2, TB_NOT_READY=3 };
static inline uint32_t tb_request(volatile struct tb_seal *s, uint32_t ipi,
                                 uint32_t source, const uint32_t *p,
                                 uint32_t words, uint32_t complete) {
    if(words<6 || ipi!=0 || source!=1 || p[0]!=TB_REQUEST ||
       p[1]!=TB_MAGIC || !(p[2]|p[3]) || p[4]!=TB_VERSION || p[5])return TB_INVALID;
    for(uint32_t i=6;i<words;i++)if(p[i])return TB_INVALID;
    if(s->closed || s->pending)return TB_BUSY;
    if((complete&15u)!=11u)return TB_NOT_READY; /* FSBL done + A53 + PMU common done */
    s->lo=p[2];s->hi=p[3];s->pending=1;return TB_OK;
}
/* Called only at the core-loop boundary after every scheduled callback returns. */
static inline int tb_commit(volatile struct tb_seal *s, uint32_t complete) {
    if(!s->pending || s->closed || (complete&15u)!=11u)return 0;
    s->closed=1;s->pending=0;return 1;
}
static inline int tb_event_allowed(const volatile struct tb_seal *s, int em,
                                   uint32_t event) {
    return !s->closed || (em && (event==4u || event==5u));
}
#endif
