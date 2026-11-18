#ifndef TY_TIMED_PMU_H
#define TY_TIMED_PMU_H
#include "../typed200_trace/trace.h"
#define TY_PMU_SOURCE 0x52355031u
#define TY_PMU_CONFIG_MAGIC 0x504d5531u
struct ty_pmu_config {
    uint32_t magic,version;uint64_t session;
    uint32_t cpu_hz,exclusive_pmu_attested,reserved[2];
};
struct ty_pmu_evidence {
    uint32_t magic,version,bound,fault;
    uint64_t session;
    uint32_t cpu_hz,samples,initial_pmcr,initial_enable,initial_irq,initial_overflow;
    uint32_t last_pmcr,last_enable,last_irq,last_overflow,first_tick,last_tick;
};
_Static_assert(sizeof(struct ty_pmu_config)==32,"PMU config ABI");
_Static_assert(sizeof(struct ty_pmu_evidence)==72,"PMU evidence ABI");
extern volatile struct ty_pmu_config ty_pmu_config;
extern volatile struct ty_pmu_evidence ty_pmu_evidence;
int ty_pmu_bind(uint64_t session);
#ifdef TY_PMU_HOST_TEST
extern uint32_t ty_mock_pmcr,ty_mock_enable,ty_mock_irq,ty_mock_overflow,ty_mock_tick,ty_mock_step;
#endif
#endif
