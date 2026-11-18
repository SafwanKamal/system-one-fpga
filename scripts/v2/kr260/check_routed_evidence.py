"""Require complete legal routing and positive final setup/hold at the selected clock."""
import argparse
import json
import math
from pathlib import Path
import re

def validate(timing, routes, mhz):
    if not re.search(r'Design State\s*:\s*(?:Fully )?Routed\s*\|',timing):
        raise ValueError('Routed design state required')
    counts={}
    for name in ('routable nets','fully routed nets','nets with routing errors'):
        match=re.search(r'# of '+re.escape(name)+r'\.*\s*:\s*(\d+)',routes)
        if match is None:raise ValueError('Missing route-status count: '+name)
        counts[name]=int(match[1])
    if counts['routable nets']<=0 or counts['fully routed nets']!=counts['routable nets'] or counts['nets with routing errors']!=0:
        raise ValueError('All routable nets must be routed without errors')
    lines=timing.splitlines()
    header=next((i for i,line in enumerate(lines) if 'WNS(ns)' in line and 'WHS(ns)' in line),None)
    if header is None:raise ValueError('Missing final timing summary')
    values=None
    for line in lines[header+1:header+8]:
        fields=line.split()
        if len(fields)!=12:continue
        try:values=[float(x) for x in fields]
        except ValueError:continue
        break
    if values is None or not all(math.isfinite(x) for x in values):raise ValueError('Invalid timing summary')
    if values[0]<=0 or values[4]<=0 or values[8]<0 or any(values[i]!=0 for i in (1,2,5,6,9,10)):
        raise ValueError('Positive setup/hold and no failing timing endpoints required')
    if 'All user specified timing constraints are met.' not in timing:raise ValueError('Passing timing constraints required')
    if type(mhz) is not int or mhz<=0:raise ValueError('Positive integer clock required')
    for name in ('clk_pl_0','clk_pl_1'):
        match=re.search(r'^'+name+r'\s+\{[^}]+\}\s+([0-9.]+)\s+',timing,re.M)
        if match is None or abs(float(match[1])-1000/mhz)>0.001:raise ValueError('Fabric clock does not match qualification')
    return {'clock_mhz':mhz,'setup_slack_ns':values[0],'hold_slack_ns':values[4],
            'pulse_width_slack_ns':values[8],'route_counts':counts,'timing_qualified':True,'hardware_qualified':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--timing',type=Path,required=True)
    ap.add_argument('--routes',type=Path,required=True);ap.add_argument('--mhz',type=int,required=True)
    args=ap.parse_args();print(json.dumps(validate(args.timing.read_text(),args.routes.read_text(),args.mhz),indent=2))

if __name__=='__main__':main()
