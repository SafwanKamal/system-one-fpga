"""Conditional phase observations from PMU-backed diagnostic traces, never WCET."""
import struct
from .typed200_trace import assess_trace


def assess_timed_trace(trace, evidence, expected):
    def require(ok, message):
        if not ok:raise ValueError(message)
    report=assess_trace(trace,expected)
    require(type(evidence) is bytes and len(evidence)==72,'Expected 72 PMU evidence bytes')
    magic,version,bound,fault,session,*v=struct.unpack('<4IQ12I',evidence)
    hz,samples,ip,ie,ii,io,lp,le,li,lo,first,last=v
    require((magic,version,bound,fault)==(0x504d4531,1,1,0),'Unbound/faulted PMU evidence')
    require(session==expected.session and hz>0,'PMU session/frequency mismatch')
    require(report['timestamps_supplied'] and report['clock_source']==0x52355031 and
            report['declared_clock_hz']==hz,'Trace not bound to this full-rate PMU provider')
    for p,e,i,o in ((ip,ie,ii,io),(lp,le,li,lo)):
        require(p>>16==0x4115 and p&0x29==1 and e&0x80000000 and
                i&0x80000000==0 and o&0x80000000==0,'Invalid PMU controls/overflow')
    events=report['trace_events'];ticks=[e['tick'] for e in events]
    require(samples==len(events)+2,'PMU sample count mismatch')
    require(first<ticks[0] and ticks[-1]==last and all(a<b for a,b in zip(ticks,ticks[1:])),
            'Counter reset, stalled counter or wrap; no modulo correction permitted')
    by_name={e['kind']:e['tick'] for e in events}
    pairs=[('hidden_copy','copy_begin','copy_end'),
           ('bridge_head','bridge_head_begin','bridge_head_end'),
           ('proposal_call','proposal_begin','proposal_end'),
           ('raw_capture','capture_begin','capture_end'),
           ('observed_request','start_submitted','finish')]
    intervals={}
    for label,start,end in pairs:
        if start in by_name and end in by_name:
            delta=by_name[end]-by_name[start]
            require(delta>0,'Invalid phase duration')
            intervals[label]={'observed_counter_ticks':delta,
                'nominal_ns_at_declared_hz_ceil':(delta*1000000000+hz-1)//hz}
    return {**report,'phase_observations':intervals,
            'counter_wrap_policy':'Reject overflow/backward/equal samples; no wrap recovery',
            'frequency_verified':False,'pmu_ownership_verified':False,
            'scope':'Conditional instrumented processor-cycle observations; declared frequency, exclusive PMU, no halt/reset/tampering required; not wall time or WCET'}
