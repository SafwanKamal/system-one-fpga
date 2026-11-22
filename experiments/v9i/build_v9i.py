"""HLS export + Vivado implementation of v9i with the exact flow and constraints that built v9h.
usage: python build_v9i.py [hls|vivado|all]   (run with the source checkout mapped as S:)
Takes build/v2/dual-port-study/s1/{hls-release.tcl,create_kr260.tcl} (the v9h build), retargets
paths from s1 to build/v2/v9i/impl, and adds a hierarchical utilization report. The reports are
written before the timing gate, so a design that fails timing still yields its numbers.
Outputs: build/v2/v9i/impl/{hls,ip.zip,vivado/routed-*.rpt,hls-console.log,vivado-console.log}.
One Vivado job at a time on this machine (14 GB).
"""
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path('S:/')
S1, OUT = ROOT / 'build/v2/dual-port-study/s1', ROOT / 'build/v2/v9i/impl'
SRC = ROOT / 'build/v2/v9i/src'
VITIS = 'C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat'
VIVADO = 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat'
step = sys.argv[1] if len(sys.argv) > 1 else 'all'


def retarget(text):
    return text.replace('S:/build/v2/dual-port-study/s1', 'S:/build/v2/v9i/impl')


def tcl_hls():
    t = retarget((S1 / 'hls-release.tcl').read_text())
    assert 'S:/build/v2/v9i/impl/src/qwen_decoder.cpp' in t
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
    for d in ('hls', 'src'):
        shutil.rmtree(OUT / d, ignore_errors=True)
    shutil.copytree(SRC, OUT / 'src')
    tcl_hls()
    if run([VITIS, '--mode', 'hls', '--tcl', 'S:/build/v2/v9i/impl/hls-release.tcl'], 'hls-console.log'):
        sys.exit(1)
if step in ('vivado', 'all'):
    shutil.rmtree(OUT / 'vivado', ignore_errors=True)
    tcl_vivado()
    sys.exit(run([VIVADO, '-mode', 'batch', '-source', 'S:/build/v2/v9i/impl/create_kr260.tcl'], 'vivado-console.log'))
