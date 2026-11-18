#ifndef TY_TRACE_H
#define TY_TRACE_H
#include "../typed200_r5/service.h"
enum {TY_TRACE_EVENTS=32,TY_TRACE_MAGIC=0x54524331u};
enum ty_trace_kind {TR_INIT=1,TR_BOOT_READY,TR_START_SUBMITTED,TR_ADMISSION_OBSERVED,
    TR_NATIVE_OBSERVED,TR_COPY_BEGIN,TR_COPY_END,TR_HEAD_BEGIN,TR_HEAD_END,
    TR_PROPOSAL_BEGIN,TR_PROPOSAL_END,TR_TERMINAL_OBSERVED,TR_CAPTURE_BEGIN,
    TR_CAPTURE_END,TR_SHARED_DONE,TR_ACK_WRITTEN,TR_FINISH};
struct ty_trace_event {uint32_t kind,tick,sequence,phase;uint64_t request;};
struct ty_trace_record {
    uint32_t magic,version,committed,event_count,dropped,clock_source,clock_hz,clock_valid;
    uint64_t session,request;
    uint32_t sequence,origin,pl_present,shared_present;
    uint32_t pl_status_after,reserved[3];
    uint32_t pl_words[64];
    unsigned char shared[384];
    struct ty_trace_event events[TY_TRACE_EVENTS];
};
_Static_assert(sizeof(struct ty_trace_record)==1488,"trace ABI");
_Static_assert(offsetof(struct ty_trace_record,pl_words)==80,"trace PL offset");
_Static_assert(offsetof(struct ty_trace_record,shared)==336,"trace shared offset");
_Static_assert(offsetof(struct ty_trace_record,events)==720,"trace event offset");
extern volatile struct ty_trace_record ty_trace;
/* Configure only before initialization, outside admission, under exclusive owner.
 * NULL means order-only trace. An injected clock is not self-attesting evidence.
 */
void ty_trace_clock(uint32_t (*read_tick)(void),uint32_t source,uint32_t hz);
void ty_trace_reset(void);
void ty_trace_event(struct ty_service *,uint32_t kind);
void ty_trace_pl(struct ty_service *);
void ty_trace_shared(struct ty_service *,uint32_t origin);
void ty_trace_finish(struct ty_service *);
#endif
