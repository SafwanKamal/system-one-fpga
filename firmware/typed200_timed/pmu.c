#include "pmu.h"
__attribute__((section(".clock_config"),used)) volatile struct ty_pmu_config ty_pmu_config;
volatile struct ty_pmu_evidence ty_pmu_evidence;
#ifdef TY_PMU_HOST_TEST
uint32_t ty_mock_pmcr,ty_mock_enable,ty_mock_irq,ty_mock_overflow,ty_mock_tick,ty_mock_step;
static uint32_t pmcr(void){return ty_mock_pmcr;}
static uint32_t enable(void){return ty_mock_enable;}
static uint32_t irq(void){return ty_mock_irq;}
static uint32_t overflow(void){return ty_mock_overflow;}
static uint32_t tick(void){ty_mock_tick+=ty_mock_step;return ty_mock_tick;}
#else
static uint32_t pmcr(void){uint32_t v;__asm__ volatile("mrc p15,0,%0,c9,c12,0":"=r"(v)::"memory");return v;}
static uint32_t enable(void){uint32_t v;__asm__ volatile("mrc p15,0,%0,c9,c12,1":"=r"(v)::"memory");return v;}
static uint32_t irq(void){uint32_t v;__asm__ volatile("mrc p15,0,%0,c9,c14,1":"=r"(v)::"memory");return v;}
static uint32_t overflow(void){uint32_t v;__asm__ volatile("mrc p15,0,%0,c9,c12,3":"=r"(v)::"memory");return v;}
static uint32_t tick(void){uint32_t v;__asm__ volatile("isb\n mrc p15,0,%0,c9,c13,0\n isb":"=r"(v)::"memory");return v;}
#endif
static int controls_ok(uint32_t p,uint32_t e,uint32_t i,uint32_t o) {
    return p>>16==0x4115u && (p&0x29u)==1 && (e&0x80000000u) &&
           !(i&0x80000000u) && !(o&0x80000000u);
}
static uint32_t sample(void) {
    uint32_t p=pmcr(),e=enable(),i=irq(),o=overflow(),t=tick();o|=overflow();
    ty_pmu_evidence.last_pmcr=p;ty_pmu_evidence.last_enable=e;
    ty_pmu_evidence.last_irq=i;ty_pmu_evidence.last_overflow=o;
    if(!controls_ok(p,e,i,o))ty_pmu_evidence.fault|=1;
    if(ty_pmu_evidence.samples && t<=ty_pmu_evidence.last_tick)ty_pmu_evidence.fault|=2;
    if(!ty_pmu_evidence.samples)ty_pmu_evidence.first_tick=t;
    ty_pmu_evidence.last_tick=t;
    if(ty_pmu_evidence.samples!=UINT32_MAX)ty_pmu_evidence.samples++;
    else ty_pmu_evidence.fault|=4;
    return t;
}
int ty_pmu_bind(uint64_t session) {
    ty_trace_clock(0,0,0);
    volatile unsigned char *raw=(volatile unsigned char *)&ty_pmu_evidence;
    for(unsigned n=0;n<sizeof(ty_pmu_evidence);n++)raw[n]=0;
    ty_pmu_evidence.magic=0x504d4531u;ty_pmu_evidence.version=1;
    ty_pmu_evidence.session=session;
    if(ty_pmu_config.magic!=TY_PMU_CONFIG_MAGIC || ty_pmu_config.version!=1 || !session ||
       ty_pmu_config.session!=session || !ty_pmu_config.cpu_hz ||
       ty_pmu_config.exclusive_pmu_attested!=1 || ty_pmu_config.reserved[0] || ty_pmu_config.reserved[1]) {
        ty_pmu_evidence.fault=8;return 0;
    }
    ty_pmu_evidence.cpu_hz=ty_pmu_config.cpu_hz;
    ty_pmu_evidence.initial_pmcr=pmcr();ty_pmu_evidence.initial_enable=enable();
    ty_pmu_evidence.initial_irq=irq();ty_pmu_evidence.initial_overflow=overflow();
    if(!controls_ok(ty_pmu_evidence.initial_pmcr,ty_pmu_evidence.initial_enable,
                    ty_pmu_evidence.initial_irq,ty_pmu_evidence.initial_overflow)) {
        ty_pmu_evidence.fault=1;return 0;
    }
    (void)sample();(void)sample();
    if(ty_pmu_evidence.fault)return 0;
    ty_pmu_evidence.bound=1;
    ty_trace_clock(sample,TY_PMU_SOURCE,ty_pmu_evidence.cpu_hz);
    return 1;
}
