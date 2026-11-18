#include "trace.h"
#include <assert.h>
#include <string.h>
static struct ty_service c;
static uint32_t ticks;
static uint32_t fake_clock(void){ticks+=17;return ticks;}
int main(void) {
    c.phase=TY_IDLE;c.identity.session=7;c.identity.request=3;c.sequence=2;
    ty_trace_clock(0,0,0);ty_trace_reset();ty_trace_event(&c,TR_INIT);
    assert(ty_trace.event_count==1 && !ty_trace.clock_valid && !ty_trace.events[0].tick);
    for(unsigned i=0;i<50;i++)ty_trace_event(&c,TR_NATIVE_OBSERVED);
    assert(ty_trace.event_count==32 && ty_trace.dropped==19);
    ty_trace_finish(&c);assert(ty_trace.committed==1 && ty_trace.dropped==20);
    struct ty_trace_record saved;memcpy(&saved,(const void *)&ty_trace,sizeof(saved));
    ty_trace_event(&c,TR_INIT);ty_trace_finish(&c);
    assert(!memcmp(&saved,(const void *)&ty_trace,sizeof(saved)));
    ticks=0xfffffff0u;ty_trace_clock(fake_clock,0xffffu,1000);ty_trace_reset();
    ty_trace_event(&c,TR_INIT);ty_trace_event(&c,TR_BOOT_READY);
    assert(ty_trace.clock_valid && ty_trace.clock_source==0xffffu && ty_trace.clock_hz==1000);
    assert(ty_trace.events[0].tick==1 && ty_trace.events[1].tick==18);
    ty_trace_clock(fake_clock,0,1000);ty_trace_reset();
    assert(!ty_trace.clock_valid && !ty_trace.clock_source && !ty_trace.clock_hz);
    static volatile struct ty_shared shared;
    c.shared=&shared;shared.command_state=TY_CMD_BUSY;shared.ids[0]=101;
    ty_trace_shared(&c,0);
    assert(shared.command_state==TY_CMD_BUSY); /* Trace does not publish or ACK. */
    assert(ty_trace.shared[24]==TY_CMD_DONE && ty_trace.shared[44]==101);
    shared.command_state=TY_CMD_READY;shared.ids[0]=999; /* Producer changes after release. */
    ty_trace_event(&c,TR_SHARED_DONE);ty_trace_finish(&c);
    assert(ty_trace.shared[24]==TY_CMD_DONE && ty_trace.shared[44]==101);
    struct ty_trace_record first;memcpy(&first,(const void *)&ty_trace,sizeof(first));
    c.sequence++;c.identity.request++;
    ty_trace_shared(&c,0);ty_trace_event(&c,TR_START_SUBMITTED);ty_trace_finish(&c);
    assert(!memcmp(&first,(const void *)&ty_trace,sizeof(first)));
    return 0;
}
