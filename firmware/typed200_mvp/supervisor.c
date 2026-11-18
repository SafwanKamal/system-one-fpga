#include "supervisor.h"
int mvp_step(const struct mvp_io *io,struct mvp_owner *owner,struct ty_service *s,uint32_t pmu_fault){
    if(pmu_fault || !mvp_check(io,owner)){
        if(pmu_fault)owner->fault=0x200;
        (void)mvp_off(io);return -1;
    }
    ty_service_poll(s);
    if(s->shared->command_state==TY_CMD_DONE)return mvp_off(io)?1:-1;
    if(s->phase==TY_HALTED){(void)mvp_off(io);return -1;}
    return 0;
}
