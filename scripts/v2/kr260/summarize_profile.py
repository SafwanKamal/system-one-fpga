"""Summarize counter-enabled evaluation reports; counters overlap, not a partition."""
import argparse
import json
import math
from pathlib import Path

def summarize(report):
    rows=[r for r in report['cases'] if r.get('performance_counters') is not None]
    if not rows:
        raise ValueError('No FPGA counters: evaluate a qualified PERF_COUNTERS=1 candidate first')
    if len(rows)!=len(report['cases']):
        raise ValueError('Partial counter report: every case must contain FPGA counters')
    hz=report['clock_hz']
    if type(hz) not in (int,float) or not math.isfinite(hz) or hz<=0 or int(hz)!=hz:
        raise ValueError('Verified live clock required')
    keys=set(rows[0]['performance_counters'])
    required={'linear_mac_issues','attention_mac_issues','axi_read_beats'}
    if not required<=keys:
        raise ValueError('Missing required FPGA counters')
    host_times=[]
    for row in rows:
        counters=row['performance_counters']
        if set(counters)!=keys:
            raise ValueError('Inconsistent counter schema across cases')
        if any(type(v) is not int or not 0<=v<1<<32 for v in counters.values()):
            raise ValueError('Invalid unsigned 32-bit FPGA counter')
        cycles=row.get('request_clocks')
        if type(cycles) is not int or not 0<cycles<1<<32:
            raise ValueError('Invalid request cycle measurement')
        host=row.get('host_round_trip_ms')
        if host is not None:
            if type(host) not in (int,float) or not math.isfinite(host) or host<0:
                raise ValueError('Invalid host request measurement')
            if host>=(1<<32)*1000/hz:
                raise ValueError('Counter wrap cannot be excluded for this request')
            host_times.append(host)
    cycles=sum(r['request_clocks'] for r in rows)
    if cycles<=0: raise ValueError('Missing request cycle measurements')
    counts={name:sum(r['performance_counters'][name] for r in rows) for name in rows[0]['performance_counters']}
    seconds=cycles/hz
    issues=counts['linear_mac_issues']+counts['attention_mac_issues']
    return {'cases':len(rows),'image_sha256':report.get('image_sha256'),'clock_hz':hz,
            'mean_request_ms':seconds*1000/len(rows),
            'axi_read_bytes':16*counts['axi_read_beats'],
            'read_bytes_per_request_second':16*counts['axi_read_beats']/seconds,
            'mac_issue_cycles_per_request_cycle':issues/cycles,
            'event_counts':counts,
            'event_cycles_per_request_cycle':{k:v/cycles for k,v in counts.items() if k not in
                {'axi_read_beats','axi_write_beats','axi_read_bursts'}},
            'hard_timing_guarantee':False,
            'counter_wrap_excluded_by_host_duration':len(host_times)==len(rows),
            'note':'Counters overlap and may wrap at 2^32. Rates include compute gaps; not standalone DDR bandwidth. No causal attribution from ratios alone.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);ap.add_argument('--output',type=Path)
    args=ap.parse_args();result=summarize(json.loads(args.report.read_text()))
    text=json.dumps(result,indent=2)+'\n'
    if args.output: args.output.write_text(text)
    print(text,end='')

if __name__=='__main__': main()
