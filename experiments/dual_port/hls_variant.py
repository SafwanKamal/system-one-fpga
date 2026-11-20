"""Synthesize an HLS variant of the decoder and summarize module resources (csynth estimates).
usage: python hls_variant.py NAME SRC_DIR   -> build/v2/dual-port-study/hls-NAME/{summary.json}
SRC_DIR holds qwen_decoder.cpp, matrix_q8.hpp, model_profile.hpp (same settings as v9f/v9g)."""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
name, src = sys.argv[1], Path(sys.argv[2]).resolve()
out = ROOT / 'build/v2/dual-port-study' / ('hls-' + name)
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
(out / 'summary.json').write_text(json.dumps(summary, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k != 'modules'}))
