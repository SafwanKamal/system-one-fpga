"""Synthesize an attention-reclaim variant of the decoder and summarize resources (csynth estimates).
usage: python hls_attn.py NAME SRC_DIR [TCL...]  -> build/v2/attn-reclaim/claude/hls-NAME/summary.json
Run with the source checkout mapped as S: (subst S: <checkout>); ROOT may be passed as SYS_ROOT.
SRC_DIR holds qwen_decoder.cpp, matrix_q8.hpp, model_profile.hpp (same settings as v9f/v9g)."""
import json, re, shutil, subprocess, sys
from pathlib import Path

import os
ROOT = Path(os.environ.get('SYS_ROOT', 'S:/'))
name, src = sys.argv[1], Path(sys.argv[2]).resolve()
EXTRA = '\n'.join(sys.argv[3:])  # optional extra Tcl lines inserted before csynth_design (e.g. config_op ...)
out = ROOT / 'build/v2/attn-reclaim/claude' / ('hls-' + name)
if out.exists():
    shutil.rmtree(out)
(out / 'src').mkdir(parents=True)
for f in ('qwen_decoder.cpp', 'matrix_q8.hpp', 'model_profile.hpp'):
    shutil.copyfile(src / f, out / 'src' / f)
s = lambda p: 'S:/' + p.relative_to(ROOT).as_posix()
(out / 'synth.tcl').write_text(f"""open_project {s(out)}/hls
set_top qwen_decoder
add_files {s(out)}/src/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {{xck26-sfvc784-2LV-c}}
create_clock -period 8 -name default
set_clock_uncertainty 1.0
config_compile -pipeline_loops 0
{EXTRA}
csynth_design
exit
""")
with open(out / 'synth-console.log', 'w') as log:
    rc = subprocess.run(['C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat', '--mode', 'hls', '--tcl', s(out) + '/synth.tcl'],
                        cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
rpt = out / 'hls/solution/syn/report/csynth.rpt'
txt = rpt.read_text() if rpt.exists() else ''
summary = dict(name=name, returncode=rc)
num = lambda f: int(f.split('(')[0]) if f.strip() not in ('-', '') else 0
mods = {}
for line in txt.splitlines():
    if not re.match(r'\|\s*\+ ', line):
        continue
    parts = [x.strip() for x in line.strip().strip('|').split('|')]
    if len(parts) < 14:
        continue
    key = parts[0].lstrip('+ ').strip()
    vals = dict(zip(('BRAM', 'DSP', 'FF', 'LUT', 'URAM'), map(num, parts[-5:])))
    mods.setdefault(key, vals)
summary['total'] = mods.get('qwen_decoder')
summary['modules'] = mods
warn = re.findall(r'WARNING: \[HLS 200-885\].*|WARNING: \[HLS 200-880\].*', (out / 'synth-console.log').read_text(errors='replace'))
summary['ii_warnings'] = len(warn)
# Attention breakdown by category and latency of its loops (from attention_csynth.rpt).
arpt = out / 'hls/solution/syn/report/attention_csynth.rpt'
if arpt.exists():
    at = arpt.read_text()
    cats = {}
    for cat in ('Expression', 'Instance', 'Memory', 'Multiplexer', 'Register', 'Total'):
        m = re.search(r'\|%s\s*\|(.*)' % cat, at)
        if m:
            cols = [c.strip() for c in m.group(1).split('|')]
            cats[cat] = dict(zip(('BRAM', 'DSP', 'FF', 'LUT', 'URAM'), map(num, cols[:5])))
    ops = {}
    for line in at.splitlines():
        m = re.match(r'\s*\|\s*\S+\s*\|\s*(f\w+?)_32ns\S*\s*\|', line)
        if m:
            ops[m.group(1)] = ops.get(m.group(1), 0) + 1
    # Per-loop achieved II, iteration latency and trip count from attention's pipelined loops.
    # Source line numbers match qwen_decoder.cpp of the variant (loop names VITIS_LOOP_<line>_<n>).
    loops = {}
    for sub_rpt in sorted(arpt.parent.glob('attention_Pipeline_*_csynth.rpt')):
        for line in sub_rpt.read_text().splitlines():
            m = re.match(r'\s*\|-\s*(\S+)\s*\|\s*(\S+)\|\s*(\S+)\|\s*(\S+)\|\s*(\S+)\|\s*(\S+)\|\s*([^|]+)\|', line)
            if m:
                loops[m.group(1)] = dict(lat_max=m.group(3), iter_lat=m.group(4), ii=m.group(5),
                                         ii_target=m.group(6), trip=m.group(7).strip())
    summary['attention'] = dict(categories=cats, fp_operators=ops, loops=loops)
(out / 'summary.json').write_text(json.dumps(summary, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k != 'modules'}))
