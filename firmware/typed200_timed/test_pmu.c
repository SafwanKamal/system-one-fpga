#include "pmu.h"
#include <assert.h>
#include <string.h>
static struct ty_service c;
static void configure(void) {
    memset((void *)&ty_pmu_config,0,sizeof(ty_pmu_config));
    ty_pmu_config.magic=TY_PMU_CONFIG_MAGIC;ty_pmu_config.version=1;
    ty_pmu_config.session=7;ty_pmu_config.cpu_hz=500000000;ty_pmu_config.exclusive_pmu_attested=1;
    ty_mock_pmcr=0x41151801;ty_mock_enable=0x80000000;ty_mock_irq=0;ty_mock_overflow=0;
    ty_mock_tick=100;ty_mock_step=100;
    c.identity.session=7;
}
int main(void) {
    configure();assert(ty_pmu_bind(7));ty_trace_reset();ty_trace_event(&c,TR_INIT);
    assert(ty_trace.clock_valid && ty_trace.clock_source==TY_PMU_SOURCE);
    assert(ty_pmu_evidence.bound && !ty_pmu_evidence.fault && ty_pmu_evidence.samples==3);
    for(unsigned fault=0;fault<14;fault++) {
        configure();
        switch(fault) {
            case 0:ty_pmu_config.session=8;break;case 1:ty_pmu_config.cpu_hz=0;break;
            case 2:ty_pmu_config.exclusive_pmu_attested=0;break;
            case 3:ty_mock_pmcr|=8;break;case 4:ty_mock_pmcr&=~1u;break;
            case 5:ty_mock_pmcr|=32;break;case 6:ty_mock_enable=0;break;
            case 7:ty_mock_irq=0x80000000;break;case 8:ty_mock_overflow=0x80000000;break;
            case 9:ty_mock_step=0;break;
            case 10:ty_pmu_config.magic=0;break;case 11:ty_pmu_config.version=2;break;
            case 12:ty_pmu_config.reserved[0]=1;break;
            default:ty_mock_pmcr=0x41161801;break;
        }
        assert(!ty_pmu_bind(7));ty_trace_reset();assert(!ty_trace.clock_valid);
    }
    for(unsigned fault=0;fault<5;fault++) {
        configure();assert(ty_pmu_bind(7));ty_trace_reset();ty_trace_event(&c,TR_INIT);
        if(fault==0)ty_mock_pmcr|=8;
        if(fault==1)ty_mock_enable=0;
        if(fault==2)ty_mock_overflow=0x80000000;
        if(fault==3)ty_mock_tick=1;
        if(fault==4)ty_mock_step=0;
        ty_trace_event(&c,TR_BOOT_READY);assert(ty_pmu_evidence.fault);
        ty_mock_pmcr=0x41151801;ty_mock_enable=0x80000000;ty_mock_overflow=0;ty_mock_tick=1000;ty_mock_step=100;
        ty_trace_event(&c,TR_FINISH);assert(ty_pmu_evidence.fault); /* Sticky, never healed. */
    }
    return 0;
}
