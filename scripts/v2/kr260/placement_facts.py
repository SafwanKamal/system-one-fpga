"""Extract completed placement evidence; never approve or launch routing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


def extract(build):
    folder = build / 'placement'
    if json.loads((folder / 'completion-status.json').read_text())['state'] != 'placement_ready':
        raise ValueError('Completed placement required')
    regression = json.loads((build / 'regression.json').read_text())
    sweep = json.loads((folder / 'frequency-diagnostics.json').read_text())
    if {row['mhz'] for row in sweep} != {125, 150, 200, 250, 300} or len(sweep) != 5:
        raise ValueError('Complete five-frequency sweep required')
    if any(row['routed'] is not False or not math.isfinite(row['estimated_setup_slack_ns']) for row in sweep):
        raise ValueError('Invalid placement sweep')
    timing = (folder / 'timing-200mhz.rpt').read_text()
    lines = timing.splitlines()
    header = next(i for i, line in enumerate(lines) if 'WNS(ns)' in line and 'WHS(ns)' in line)
    summary = None
    for line in lines[header + 1:header + 8]:
        fields = line.split()
        if len(fields) == 12:
            try:
                summary = [float(value) for value in fields]
            except ValueError:
                continue
            break
    if summary is None or not all(math.isfinite(value) for value in summary):
        raise ValueError('Complete timing summary required')
    setup = next(row['estimated_setup_slack_ns'] for row in sweep if row['mhz'] == 200)
    if abs(setup - summary[0]) > .002:
        raise ValueError('Timing report and sweep disagree')
    utilization = (folder / 'utilization.rpt').read_text()
    packing = re.search(r'\|\s*CLB\s*\|\s*(\d+)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|\s*([\d.]+)', utilization)
    if not packing:
        raise ValueError('CLB packing evidence required')
    congestion = (folder / 'congestion.rpt').read_text()
    levels = [int(level) for level in re.findall(r'\|\s*(?:North|South|East|West)\s*\|\s*\w+\s*\|\s*(\d+)', congestion)]
    if 'Placer Final Level Congestion Reporting' not in congestion:
        raise ValueError('Congestion report required')
    critical = (folder / 'critical-200mhz.rpt').read_text()
    paths = []
    for block in re.split(r'(?=Slack \()', critical)[1:]:
        def field(pattern):
            match = re.search(pattern, block)
            if not match:
                raise ValueError('Incomplete critical path')
            return match.group(1)
        paths.append({'slack_ns': float(field(r'Slack \([^)]*\)\s*:\s*([-\d.]+)ns')),
                      'source': field(r'Source:\s*(\S+)'),
                      'destination': field(r'Destination:\s*(\S+)'),
                      'data_ns': float(field(r'Data Path Delay:\s*([\d.]+)ns'))})
    if not paths:
        raise ValueError('Critical paths required')
    names = ['system_wrapper_placed.dcp', 'frequency-diagnostics.json', 'congestion.rpt',
             'utilization.rpt', 'timing-200mhz.rpt', 'critical-200mhz.rpt', 'placement-result.json']
    return {'candidate': regression['candidate'], 'stage': 'placed, not routed',
            'sweep': sweep, 'setup_ns': setup, 'hold_ns': summary[4],
            'hold_failing_endpoints': int(summary[6]), 'clb_used': int(packing[1]),
            'clb_available': int(packing[2]), 'clb_percent': float(packing[3]),
            'congestion_level': max(levels, default=0), 'critical_paths': paths,
            'native_times': json.loads((folder / 'placement-result.json').read_text()),
            'minimum_setup_margin_met': setup >= .5,
            'route_approved': False, 'review_required': True,
            'evidence_sha256': {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in names}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.build), indent=2))
