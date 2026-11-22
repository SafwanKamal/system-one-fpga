"""HLS export + Vivado implementation of v9j with the exact flow and constraints that built v9h.
usage: python build_v9j.py [hls|vivado|all]   (run with the source checkout mapped as S:)
Same flow as experiments/v9i/build_v9i.py, retargeted: takes the v9h build scripts from
build/v2/dual-port-study/s1/{hls-release.tcl,create_kr260.tcl}, points them at build/v2/v9j/impl,
and adds a hierarchical utilization report before the timing gate (so a design that fails timing
still yields its numbers). Source: build/v2/v9j/src from experiments/v9j/make_v9j.py (D3 dual port,
P=4 attention, Gemini's mul_xb in FTZ mode; xmul_hls.hpp sits beside qwen_decoder.cpp).
Outputs: build/v2/v9j/impl/{hls,vivado/routed-*.rpt,hls-console.log,vivado-console.log}.
One Vivado job at a time on this machine (14 GB).
"""
import shutil, subprocess, sys
from pathlib import Path

NAME = 'v9j'
ROOT = Path('S:/')
S1, OUT = ROOT / 'build/v2/dual-port-study/s1', ROOT / f'build/v2/{NAME}/impl'
SRC = ROOT / f'build/v2/{NAME}/src'
OUT_TCL = f'S:/build/v2/{NAME}/impl'
VITIS = 'C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat'
VIVADO = 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat'
step = sys.argv[1] if len(sys.argv) > 1 else 'all'


def retarget(text):
    return text.replace('S:/build/v2/dual-port-study/s1', OUT_TCL)


def tcl_hls():
    t = retarget((S1 / 'hls-release.tcl').read_text())
    assert f'{OUT_TCL}/src/qwen_decoder.cpp' in t
    (OUT / 'hls-release.tcl').write_text(t)


def tcl_vivado():
    t = retarget((S1 / 'create_kr260.tcl').read_text())
    gate = 'set setup [get_timing_paths -delay_type max -max_paths 1]'
    assert t.count(gate) == 1
    t = t.replace(gate, 'report_utilization -hierarchical -hierarchical_depth 4 -file '
                        '[file join $project_dir routed-hier-utilization.rpt]\n' + gate)
    (OUT / 'create_kr260.tcl').write_text(t)


def run(cmd, log):
    with open(OUT / log, 'w') as f:
        rc = subprocess.run(cmd, cwd=OUT, stdout=f, stderr=subprocess.STDOUT).returncode
    print(log, 'rc', rc)
    return rc


OUT.mkdir(parents=True, exist_ok=True)
if step in ('hls', 'all'):
    assert (SRC / 'xmul_hls.hpp').is_file(), 'run experiments/v9j/make_v9j.py first'
    for d in ('hls', 'src'):
        shutil.rmtree(OUT / d, ignore_errors=True)
    shutil.copytree(SRC, OUT / 'src')
    tcl_hls()
    if run([VITIS, '--mode', 'hls', '--tcl', f'{OUT_TCL}/hls-release.tcl'], 'hls-console.log'):
        sys.exit(1)
if step in ('vivado', 'all'):
    shutil.rmtree(OUT / 'vivado', ignore_errors=True)
    tcl_vivado()
    sys.exit(run([VIVADO, '-mode', 'batch', '-source', f'{OUT_TCL}/create_kr260.tcl'], 'vivado-console.log'))
