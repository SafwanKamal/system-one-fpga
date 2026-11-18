#ifndef TY_R5_SERVICE_H
#define TY_R5_SERVICE_H
#include "../typed200_v2/typed200.h"
#include <stddef.h>
enum {TY_CONFIG_MAGIC=0x54594331u,TY_SHARED_VERSION=1,TY_CMD_IDLE=0,TY_CMD_READY=1,TY_CMD_BUSY=2,TY_CMD_DONE=3};
struct ty_shared {
    uint32_t magic,version;
    uint64_t session;
    uint32_t exclusive_buffers_attested,boot_status;
    uint32_t command_state,sequence;
    uint16_t tokens,first,count,reserved;
    uint32_t budget;
    uint16_t ids[128];
    uint32_t result_sequence,result_origin; /* 1: PL terminal; 0: CPU rejection/fault */
    struct ti_record result;
    uint32_t exception_reason;
};
_Static_assert(sizeof(struct ty_shared)==384,"shared ABI size");
_Static_assert(offsetof(struct ty_shared,result)==312,"shared ABI result offset");
enum ty_phase {TY_BOOT_WAIT,TY_IDLE,TY_ADMISSION,TY_CORE,TY_TERMINAL,TY_HALTED};
struct ty_service {
    volatile uint32_t *mmio,*permit;
    volatile uint16_t *ids;
    const volatile int8_t *hidden;
    volatile struct ty_shared *shared;
    struct ti_input *input;
    struct ti_bridge bridge;
    struct ti_identity identity;
    struct ti_proposal proposal;
    uint64_t next_request;
    uint32_t sequence,last_sequence;
    uint16_t tokens,first,count;
    enum ty_phase phase;
};
int ty_service_init(struct ty_service *,volatile uint32_t *,volatile uint32_t *,volatile uint16_t *,
                    const volatile int8_t *,volatile struct ty_shared *,struct ti_input *,int verified);
void ty_service_poll(struct ty_service *);
#endif
