"""Gated, nondeploying synthesis/placement for the isolated counter300 candidate.

Uses the existing board-design setup only; does not invoke historical integration
or qualification flows. Never routes, exports a bitstream, packages or deploys.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

from create_counter300_candidate import ROOT, OUT, verify

BUILD = ROOT / 'build/v2'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(p):
    return re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), '
                      r'(\d+) mismatching words; clocks: encoder (\d+), request (\d+)', p.read_text())


def numerical_gate():
    candidate = verify()
    qualified_path = BUILD / 'kr260-opt-attention-context-capture-large/regression.json'
    directory = BUILD / 'counter300-regression-v2'
    if json.loads((directory / 'completion-status.json').read_text()) != {'exit_code': 0, 'complete': True}:
        raise ValueError('Complete candidate regression required before synthesis')
    qualified = json.loads(qualified_path.read_text())
    reference = BUILD / 'rtl-context-capture-parameter-check'
    counts = {'l12-h1024': 8, 'wide': 8, 'one-word': 5, 'boundary': 3,
              'h1024': 8, 'head32': 4, 'partial': 6, 'l12-h384': 8}
    hashes = {}
    for name, count in counts.items():
        path = directory / f'{name}.log'
        actual = rows(path)
        baseline = rows(reference / ('l12.log' if name.startswith('l12-') else f'{name}.log'))
        if len(actual) != count or actual != baseline:
            raise ValueError(f'Numerical/cycle mismatch: {name}')
        if any(row[2] != '0' or row[4] != '0' for row in actual):
            raise ValueError(f'Failed status/output comparison: {name}')
        if 'PASS independent deadline outcome and quarantine at wrapper' not in path.read_text():
            raise ValueError(f'Missing deadline-wrapper proof: {name}')
        expected_counters = re.findall(r'profile case (\d+) counter (\d+) = (\d+)', (reference / ('l12.log' if name.startswith('l12-') else f'{name}.log')).read_text())
        actual_counters = re.findall(r'profile case (\d+) counter (\d+) = (\d+)', path.read_text())
        if len(actual_counters) != count*10 or actual_counters != expected_counters:
            raise ValueError(f'Exact performance counter mismatch: {name}')
        hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    vectors = {'wide': BUILD / 'rtl-wide-check/vectors',
               'l12': ROOT / 'simulation/v2/vectors/kr260',
               'one-word': BUILD / 'rtl-batch3-check/one-word-vectors',
               'boundary': BUILD / 'rtl-batch-check/boundary-vectors',
               'h1024': BUILD / 'kr260-dot7-h1024-eight-vectors'}
    fixture_hashes = {}
    for group, location in vectors.items():
        for name, expected_hash in qualified['checks'][group]['vectors_sha256'].items():
            path = location / name
            if digest(path) != expected_hash:
                raise ValueError(f'Frozen numerical fixture changed: {path}')
            fixture_hashes[path.relative_to(ROOT).as_posix()] = expected_hash
    for name, expected_hash in qualified['query_group_vectors_sha256'].items():
        path = BUILD / 'attention16-head32-vectors' / name
        if digest(path) != expected_hash:
            raise ValueError(f'Frozen query-group fixture changed: {path}')
        fixture_hashes[path.relative_to(ROOT).as_posix()] = expected_hash
    if 'PASS supervisor 288 boundary scenarios' not in (directory / 'supervisor.log').read_text():
        raise ValueError('Independent supervisor boundaries must pass')
    if 'PASS telemetry exact counts' not in (directory / 'telemetry.log').read_text():
        raise ValueError('Telemetry directed boundaries must pass')
    hashes[(directory / 'telemetry.log').relative_to(ROOT).as_posix()] = digest(directory / 'telemetry.log')
    if digest(ROOT / 'rtl/contracts/performance_telemetry.sv') != candidate['candidate_sha256']['common/performance_telemetry.sv']:
        raise ValueError('Directed telemetry module differs from sealed candidate')
    # Verify bytes compiled in the staged snapshot, rather than just current files.
    stage = Path((directory / 'stage.txt').read_text().strip())
    expected = candidate['candidate_sha256']
    inventory = (directory / 'source-sha256.txt').read_text().splitlines()
    staged = {name: value for value, name in (line.split(maxsplit=1) for line in inventory)}
    for name, value in expected.items():
        if staged.get('rtl/v2/' + name) != value:
            raise ValueError(f'Compiled candidate bytes differ: {name} ({stage})')
    test_name = 'simulation/v2/performance_telemetry_tb.sv'
    if staged.get(test_name) != digest(ROOT / test_name):
        raise ValueError('Directed telemetry test source changed since compilation')
    return {'cases': sum(counts.values()), 'exact_outputs_and_cycles': True,
            'exact_performance_counters': True, 'counter_values_compared': sum(counts.values())*10,
            'candidate_manifest_sha256': digest(OUT / 'candidate.json'),
            'qualified_regression_sha256': digest(qualified_path),
            'fixture_sha256': fixture_hashes, 'evidence_sha256': hashes}


def project_tcl(profile, destination):
    # Snapshot a reviewed existing PS/PL setup, replacing all candidate locations.
    source = ROOT / 'scripts/v2/kr260/create_project_kr260.tcl'
    text = source.read_text().split('if {$preflight} {', 1)[0]
    short = Path('S:/')
    if not short.exists() or not short.samefile(ROOT):
        raise ValueError('Existing S: repository alias unavailable; do not recreate/change it')
    prefix = 'set argv {preflight optimized 300 bram wide memory context-capture large}\n'
    text = re.sub(r'^set repo_dir .*$', 'set repo_dir [file normalize {S:/}]', text, count=1, flags=re.M)
    hidden = 384 if profile == 'encoder384' else 1024
    insertion = (f'set project_dir [file join $repo_dir build v2 counter300-{profile}]\n'
                 'if {[file exists [file join $project_dir sysone_v2_kr260.xpr]]} {error "Preserve existing project"}\n')
    anchor = 'set board_store '
    pos = text.index(anchor)
    text = text[:pos] + insertion + text[pos:]
    text = text.replace('set rtl [file join $repo_dir rtl v2]',
                        'set rtl [file join $repo_dir rtl v2 candidates counter300]')
    text = text.replace('if {$optimized} {\n    # Freeze',
                        'lappend source_files [file join $rtl common deadline_supervisor.sv]\n'
                        'lappend source_files [file join $rtl common performance_telemetry.sv]\n'
                        'if {$optimized} {\n    # Freeze')
    text = text.replace('if {$large} { set_property CONFIG.MAX_HIDDEN 1024 $enc }',
                        f'set_property CONFIG.MAX_HIDDEN {hidden} $enc')
    return prefix + text + '''
set_param general.maxThreads 4
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Candidate synthesis failed"}
open_run synth_1
report_utilization -file [file join $project_dir synthesis-utilization.rpt]
report_timing_summary -file [file join $project_dir synthesis-timing.rpt]
report_timing -delay_type max -max_paths 30 -input_pins -file [file join $project_dir synthesis-critical.rpt]
report_high_fanout_nets -timing -load_types -max_nets 40 -file [file join $project_dir synthesis-fanout.rpt]
set replicas [get_cells -hier -filter {IS_SEQUENTIAL == 1 && NAME =~ *gen_query_read*data_reg*}]
set selects [get_cells -hier -filter {IS_SEQUENTIAL == 1 && NAME =~ *gen_local_mac_select*select_reg*}]
set telemetry [get_cells -hier -filter {IS_SEQUENTIAL == 1 && NAME =~ *telemetry_inst*delta_reg*}]
if {[llength $telemetry] < 27} {error "Telemetry input cut disappeared"}
set supervisor [get_cells -hier -filter {IS_SEQUENTIAL == 1 && NAME =~ *contract_inst*}]
set report [open [file join $project_dir locality-inference.json] w]
puts $report [format {{"query_data_registers":%d,"local_select_registers":%d,"supervisor_registers":%d,"telemetry_delta_registers":%d,"routed":false}} [llength $replicas] [llength $selects] [llength $supervisor] [llength $telemetry]]
close $report
if {[llength $replicas] < 512 || [llength $selects] < 128 || [llength $supervisor] < 64} {
    error "Locality or supervisor register cut disappeared; inspect reports"
}
write_checkpoint [file join $project_dir synthesized.dcp]
close_project
''', digest(source)


def placement_tcl(profile):
    return f'''set_param general.maxThreads 4
set build {{S:/build/v2/counter300-{profile}}}
set output [file join $build placement]
open_project [file join $build sysone_v2_kr260.xpr]
open_run synth_1
if {{[llength [get_pblocks -quiet]]}} {{error "Unexpected physical constraints"}}
opt_design
write_checkpoint [file join $output optimized.dcp]
place_design
write_checkpoint [file join $output placed.dcp]
report_utilization -file [file join $output utilization.rpt]
report_design_analysis -congestion -file [file join $output congestion.rpt]
set report [open [file join $output frequency-diagnostics.json] w]
puts $report "\\["
set separator ""
foreach mhz {{200 250 300}} {{
    foreach name {{clk_pl_0 clk_pl_1}} {{
        set c [get_clocks -quiet $name]
        if {{[llength $c] != 1}} {{error "Expected two known PS clocks"}}
        create_clock -name $name -period [expr {{1000.0/$mhz}}] [get_pins [get_property SOURCE_PINS $c]]
    }}
    report_timing_summary -file [file join $output timing-${{mhz}}.rpt]
    report_timing -delay_type max -max_paths 30 -input_pins -file [file join $output critical-${{mhz}}.rpt]
    set setup [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
    set hold [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
    puts $report "$separator{{\\"mhz\\":$mhz,\\"setup_ns\\":$setup,\\"hold_ns\\":$hold,\\"routed\\":false}}"
    set separator ","
}}
puts $report "\\]"
close $report
close_project
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=['encoder384', 'capacity1024'], required=True)
    p.add_argument('--stage', choices=['synth', 'place'], default='synth')
    p.add_argument('--prepare-only', action='store_true')
    args = p.parse_args()
    proof = numerical_gate()
    build = BUILD / f'counter300-{args.profile}'
    if args.stage == 'synth':
        if build.exists():
            raise FileExistsError('Preserve existing synthesis evidence')
        build.mkdir()
        text, setup_sha = project_tcl(args.profile, build)
        proof['board_setup_source_sha256'] = setup_sha
        destination = build
    else:
        # Synthesis has to complete and inference cuts be reviewed first.
        status = json.loads((build / 'synth-status.json').read_text())
        review = json.loads((build / 'synthesis-review.json').read_text())
        if status.get('exit_code') != 0 or review.get('placement_approved') is not True:
            raise ValueError('Successful synthesis and explicit evidence review required')
        for name, expected in review['evidence_sha256'].items():
            if digest(build / name) != expected:
                raise ValueError(f'Reviewed synthesis evidence changed: {name}')
        destination = build / 'placement'
        if destination.exists():
            raise FileExistsError('Preserve existing placement evidence')
        destination.mkdir()
        text = placement_tcl(args.profile)
    script = destination / f'{args.stage}.tcl'
    script.write_text(text)
    (destination / 'input-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    if args.prepare_only:
        print(script)
        return
    exe = Path('C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat')
    short_destination = Path('S:/') / destination.relative_to(ROOT)
    with (destination / 'console.log').open('w') as console:
        result = subprocess.run([str(exe), '-mode', 'batch', '-nojournal', '-log',
                                 str(short_destination / 'vivado.log'), '-source',
                                 str(short_destination / script.name)],
                                stdout=console, stderr=subprocess.STDOUT, cwd=short_destination)
    (build / f'{args.stage}-status.json').write_text(json.dumps({
        'stage': args.stage, 'exit_code': result.returncode, 'target_mhz': 300,
        'routed': False, 'hardware_qualified': False})+'\n')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
