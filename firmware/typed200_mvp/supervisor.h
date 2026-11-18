#ifndef MVP_SUPERVISOR_H
#define MVP_SUPERVISOR_H
#include "ownership.h"
#include "../typed200_r5/service.h"
/* 0 continue; 1 terminal frozen/park; -1 ownership/PMU/service fault, park. */
int mvp_step(const struct mvp_io *,struct mvp_owner *,struct ty_service *,uint32_t pmu_fault);
#endif
