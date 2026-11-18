"""Matched OOC synthesis control/clock experiment; frozen RTL, no board actions."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='typed200-synthesis-clock-v3')
    ap.add_argument('--control-from', help='Reuse hash-identical completed unconstrained control')
    args = ap.parse_args()
    assert re.fullmatch(r'[a-z0-9-]+', args.name)
    assert Path('S:/').samefile(ROOT)
    # Rehash all immutable source/document/evidence maps before consuming inputs.
    checked = 0
    for seal in (ROOT/'docs/research').glob('2026-10-15-*-validation.json'):
        data = json.loads(seal.read_text(encoding='utf-8'))
        for key in ('source_sha256', 'documentation_sha256', 'evidence_sha256'):
            for name, digest in data.get(key, {}).items():
                assert sha(ROOT/name) == digest, name
                checked += 1
    preserved = json.loads((ROOT/'docs/research/2026-10-14-system-one-preservation.json').read_text(encoding='utf-8'))
    for row in preserved['file_checks']:
        assert sha(ROOT/row['path']) == row['before_sha256'], row['path']
    old = ROOT/'build/v2/typed200-flush-physical-v1'
    generated = (old/'sysone_v2_kr260.runs/system_encoder_0_synth_1/system_encoder_0.tcl').read_text()
    blocks = re.findall(r'read_verilog -library xil_defaultlib(?: -sv)? (\{[^}]+\}|[^\n]+)', generated)
    assert len(blocks) == 2
    names = []
    for block in blocks:
        names += block.strip('{} \n').splitlines()
    paths = [ROOT/Path(p.strip()).relative_to(Path('S:/')) for p in names]
    assert len(paths) == 28
    paths.append(old/'sysone_v2_kr260.gen/sources_1/bd/system/ip/system_encoder_0/synth/system_encoder_0.v')
    build = ROOT/'build/v2'/args.name
    build.mkdir(exist_ok=False)
    inputs = build/'inputs'
    inputs.mkdir()
    inventory = {}
    for i, path in enumerate(paths):
        dest = inputs/f'{i:02d}-{path.name}'
        shutil.copyfile(path, dest)
        inventory[dest.relative_to(build).as_posix()] = {
            'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(dest)}
        assert sha(path) == sha(dest)
    (build/'input-proof.json').write_text(json.dumps({
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'seal_entries_checked': checked, 'protected_files_checked': len(preserved['file_checks']),
        'inputs': inventory, 'rtl_changed': False, 'hardware_qualified': False,
        'scope': 'Same generated wrapper, parameters, part, RTL order and synthesis options; only XDC differs',
    }, indent=2)+'\n')
    short = f'S:/build/v2/{args.name}'
    # read_xdc is registered BEFORE synth_design. XDC accepts a restricted command
    # subset; validation/logging belongs in the surrounding Tcl, never in XDC.
    xdc = 'create_clock -name encoder_ooc_200 -period 5.000 [get_ports clk]\n'
    (build/'encoder-ooc.xdc').write_text(xdc)
    for mode in ('control', 'clocked'):
        out = build/mode
        if mode == 'control' and args.control_from:
            assert re.fullmatch(r'[a-z0-9-]+', args.control_from)
            control = ROOT/'build/v2'/args.control_from
            prior = json.loads((control/'input-proof.json').read_text())
            assert prior['inputs'] == inventory, 'Control input/order mismatch'
            assert json.loads((control/'control/status.json').read_text())['exit_code'] == 0
            assert (control/'control/clock-count.txt').read_text().strip() == 'Stored OOC clocks: 0'
            shutil.copytree(control/'control', out)
            (build/'control-reuse.json').write_text(json.dumps({
                'source': args.control_from, 'checkpoint_sha256': sha(out/'encoder.dcp'),
                'matched_inputs': True}, indent=2)+'\n')
            continue
        out.mkdir()
        reads = '\n'.join(f'read_verilog -library xil_defaultlib {"-sv " if n.endswith(".sv") else ""}{{{short}/{n}}}' for n in inventory)
        tcl = f'''set_param general.maxThreads 4
create_project -in_memory -part xck26-sfvc784-2LV-c
set_property XPM_LIBRARIES {{XPM_CDC XPM_FIFO XPM_MEMORY}} [current_project]
set_property default_lib xil_defaultlib [current_project]
set_property target_language Verilog [current_project]
{reads}
{f'read_xdc {{{short}/encoder-ooc.xdc}}' if mode == 'clocked' else '# Matched control: no OOC clock, as in frozen parent'}
synth_design -top system_encoder_0 -part xck26-sfvc784-2LV-c -incremental_mode off -mode out_of_context
if {{[get_msg_config -count -severity {{CRITICAL WARNING}}] != 0}} {{error "Critical synthesis warnings require review"}}
set out {{{short}/{mode}}}
set c [get_clocks -quiet *]
set f [open [file join $out clock-count.txt] w]
puts $f "Stored OOC clocks: [llength $c]"
foreach clk $c {{puts $f "$clk period [get_property PERIOD $clk]"}}
close $f
if {{[llength $c] != {1 if mode == 'clocked' else 0}}} {{error "Unexpected OOC clock count"}}
{ 'if {[get_property PERIOD $c] != 5.000} {error "Wrong synthesis clock period"}' if mode == 'clocked' else '' }
report_utilization -file [file join $out utilization.rpt]
if {{[llength $c]}} {{
  report_clocks -file [file join $out clocks.rpt]
  report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
  report_timing -delay_type max -max_paths 30 -input_pins -file [file join $out critical.rpt]
  check_timing -verbose -file [file join $out check-timing.rpt]
}}
rename_ref -prefix_all system_encoder_0_
write_checkpoint [file join $out encoder.dcp]
close_project
'''
        script = out/'synth.tcl'
        script.write_text(tcl)
        with (out/'console.log').open('w') as log:
            result = subprocess.run([
                'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat', '-mode', 'batch', '-nojournal',
                '-log', f'{short}/{mode}/vivado.log', '-source', f'{short}/{mode}/synth.tcl'],
                cwd=out, stdout=log, stderr=subprocess.STDOUT)
        receipt = {'exit_code': result.returncode, 'mode': mode, 'hardware_qualified': False}
        if result.returncode == 0 and mode == 'clocked':
            log = (out/'console.log').read_text()
            marker = f'Parsing XDC File [{short}/encoder-ooc.xdc]'
            assert marker in log
            assert log.index(marker) < log.index('Start Cross Boundary and Area Optimization')
            receipt['clock_applied_during_synthesis'] = True
        (out/'status.json').write_text(json.dumps(receipt, indent=2)+'\n')
        assert result.returncode == 0, receipt
    for n, record in inventory.items():
        assert sha(build/n) == record['sha256']
        assert sha(ROOT/record['source']) == record['sha256']
    print('PASS matched OOC clock experiment; inspect reports before integration')


if __name__ == '__main__':
    main()
