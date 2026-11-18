"""Matched whole ADD_SKIP mapped probe, with clocks applied before synthesis."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess
from create_typed200_clamp_candidate import ROOT, OUT, PARENT, verify

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-clamp-ooc-v1');a=ap.parse_args()
    verify();assert Path('S:/').samefile(ROOT)
    proof_dir=ROOT/'build/v2/typed200-clamp-formal-v5'
    proof=json.loads((proof_dir/'receipt.json').read_text());assert proof['passed']
    for n,h in proof['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in proof['artifact_sha256'].items():assert sha(proof_dir/n)==h,n
    b=ROOT/'build/v2'/a.name;b.mkdir(exist_ok=False);short=f'S:/build/v2/{a.name}'
    (b/'probe.xdc').write_text('create_clock -name probe_clk -period 5.000 [get_ports clk]\n')
    sources={};results={}
    for mode,source in [('control',PARENT),('clamp',OUT)]:
        folder=b/mode;folder.mkdir()
        for fn in ('encoder_pkg.sv','add_skip_engine.sv'):
            src=source/'encoder'/fn;shutil.copyfile(src,folder/fn)
            sources[src.relative_to(ROOT).as_posix()]=sha(src)
        script=f'''set_param general.maxThreads 2
create_project -in_memory -part xck26-sfvc784-2LV-c
read_verilog -sv {{{short}/{mode}/encoder_pkg.sv}}
read_verilog -sv {{{short}/{mode}/add_skip_engine.sv}}
read_xdc {{{short}/probe.xdc}}
synth_design -top add_skip_engine -part xck26-sfvc784-2LV-c -mode out_of_context
set out {{{short}/{mode}}}
if {{[llength [get_clocks probe_clk]] != 1}} {{error "Missing5ns clock"}}
set regs [get_cells -hier -filter {{NAME =~ *rounded_reg* && REF_NAME =~ FD*}}]
if {{[llength $regs] == 0}} {{error "Missing rounded source registers"}}
set pins [get_pins -of_objects $regs -filter {{REF_PIN_NAME == Q}}]
report_timing -from $pins -delay_type max -max_paths 20 -input_pins -file [file join $out rounded-paths.rpt]
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
set path [get_timing_paths -from $pins -delay_type max -max_paths 1]
if {{[llength $path] != 1}} {{error "No rounded timing path"}}
set allpath [get_timing_paths -delay_type max -max_paths 1]
set f [open [file join $out metrics.json] w]
puts $f [format {{{{"rounded_source_flops":%d,"carry_cells":%d,"rounded_slack_ns":%s,"rounded_data_ns":%s,"rounded_levels":%s,"overall_slack_ns":%s}}}} [llength $regs] [llength [get_cells -hier -filter {{REF_NAME == CARRY8}}]] [get_property SLACK $path] [get_property DATAPATH_DELAY $path] [get_property LOGIC_LEVELS $path] [get_property SLACK $allpath]]
close $f
write_checkpoint [file join $out mapped.dcp]
close_project
'''
        (folder/'synth.tcl').write_text(script)
        with (folder/'console.log').open('w') as log:
            r=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
                '-log',f'{short}/{mode}/vivado.log','-source',f'{short}/{mode}/synth.tcl'],
                cwd=folder,stdout=log,stderr=subprocess.STDOUT)
        (folder/'status.json').write_text(json.dumps({'exit_code':r.returncode})+'\n')
        assert r.returncode==0,mode
        results[mode]=json.loads((folder/'metrics.json').read_text())
    (b/'receipt.json').write_text(json.dumps({'passed':True,'scope':'Matched full ADD_SKIP mapped probe at5ns',
        'limits':['Not full design placement/routing','No target/WCET/300MHz claim'],
        'proof_sha256':sha(proof_dir/'receipt.json'),'source_sha256':sources,'results':results,
        'artifact_sha256':{p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file() and '.Xil' not in p.parts}},indent=2)+'\n')
    print(json.dumps(results));print('PASS matched mapped probe; compare actual improvement before full physical spend')

if __name__=='__main__':main()
