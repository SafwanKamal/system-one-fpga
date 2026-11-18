"""Both-stage matched probe, including registered instruction/data input paths."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
from create_typed200_stage_clamp_candidate import ROOT,OUT,PARENT,verify
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-stage-clamp-ooc-v1');a=ap.parse_args()
    verify();assert Path('S:/').samefile(ROOT)
    proof_dir=ROOT/'build/v2/typed200-stage-clamp-formal-v1';proof=json.loads((proof_dir/'receipt.json').read_text());assert proof['passed']
    for n,h in proof['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in proof['artifact_sha256'].items():assert sha(proof_dir/n)==h,n
    b=ROOT/'build/v2'/a.name;b.mkdir(exist_ok=False);short=f'S:/build/v2/{a.name}'
    (b/'probe.xdc').write_text('create_clock -name probe_clk -period 5.000 [get_ports clk]\n')
    header=(PARENT/'encoder/add_skip_engine.sv').read_text().split(') (',1)[1].split('\n);',1)[0].replace('BUFFER_ADDRESS_WIDTH-1:0','13:0')
    inputs=[];ports=[]
    for line in header.splitlines():
        m=re.match(r'\s*(input|output) logic\s*(\[[^]]+\])?\s*(\w+)',line)
        if m:
            direction,width,name=m.groups();ports.append(name)
            if direction=='input' and name not in ('clk','reset'):inputs.append((width or '',name))
    wrapper='module add_skip_probe ('+header+'\n);\n'
    wrapper+='\n'.join('logic '+w+' in_'+n+';' for w,n in inputs)+'\n'
    wrapper+='always_ff @(posedge clk) begin\n'+'\n'.join('in_'+n+' <= '+n+';' for w,n in inputs)+'\nend\n'
    registered={n for w,n in inputs}
    wrapper+='add_skip_engine engine('+','.join('.'+n+'('+('in_'+n if n in registered else n)+')' for n in ports)+');\nendmodule\n'
    (b/'probe.sv').write_text(wrapper)
    sources={};results={}
    for mode,source in [('control',PARENT),('stage',OUT)]:
        folder=b/mode;folder.mkdir()
        for fn in ('encoder_pkg.sv','add_skip_engine.sv'):
            src=source/'encoder'/fn;shutil.copyfile(src,folder/fn);sources[src.relative_to(ROOT).as_posix()]=sha(src)
        stage_pattern='*rounded_reg*' if mode=='control' else '*skip_clamped_reg*'
        script=f'''set_param general.maxThreads 2
create_project -in_memory -part xck26-sfvc784-2LV-c
read_verilog -sv {{{short}/{mode}/encoder_pkg.sv}}
read_verilog -sv {{{short}/{mode}/add_skip_engine.sv}}
read_verilog -sv {{{short}/probe.sv}}
read_xdc {{{short}/probe.xdc}}
synth_design -top add_skip_probe -part xck26-sfvc784-2LV-c -mode out_of_context
set out {{{short}/{mode}}}
if {{[llength [get_clocks probe_clk]] != 1}} {{error "Missing5ns clock"}}
set regs [get_cells -hier -filter {{NAME =~ {stage_pattern} && REF_NAME =~ FD*}}]
if {{[llength $regs] == 0}} {{error "Missing stage registers"}}
set pins [get_pins -of_objects $regs -filter {{REF_PIN_NAME == Q}}]
report_timing -to $regs -delay_type max -max_paths 20 -input_pins -file [file join $out rounding-stage-paths.rpt]
report_timing -from $pins -delay_type max -max_paths 20 -input_pins -file [file join $out output-stage-paths.rpt]
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
set rounding [get_timing_paths -to $regs -delay_type max -max_paths 1]
set output [get_timing_paths -from $pins -delay_type max -max_paths 1]
set overall [get_timing_paths -delay_type max -max_paths 1]
foreach path [list $rounding $output $overall] {{if {{[llength $path]!=1}} {{error "Missing stage timing path"}}}}
set f [open [file join $out metrics.json] w]
puts $f [format {{{{"stage_flops":%d,"carry_cells":%d,"rounding_slack_ns":%s,"rounding_data_ns":%s,"rounding_levels":%s,"output_slack_ns":%s,"output_data_ns":%s,"output_levels":%s,"overall_slack_ns":%s}}}} [llength $regs] [llength [get_cells -hier -filter {{REF_NAME == CARRY8}}]] [get_property SLACK $rounding] [get_property DATAPATH_DELAY $rounding] [get_property LOGIC_LEVELS $rounding] [get_property SLACK $output] [get_property DATAPATH_DELAY $output] [get_property LOGIC_LEVELS $output] [get_property SLACK $overall]]
close $f
write_checkpoint [file join $out mapped.dcp]
close_project
'''
        (folder/'synth.tcl').write_text(script)
        with (folder/'console.log').open('w') as log:
            r=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
                '-log',f'{short}/{mode}/vivado.log','-source',f'{short}/{mode}/synth.tcl'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
        (folder/'status.json').write_text(json.dumps({'exit_code':r.returncode})+'\n');assert r.returncode==0,mode
        results[mode]=json.loads((folder/'metrics.json').read_text())
    (b/'receipt.json').write_text(json.dumps({'passed':True,'scope':'Matched both-stage ADD_SKIP probe with identical registered input shell and5ns clock',
        'limits':['Shell registers model upstream launch points; not candidate pipeline stages','Not full-design placement/routing or target/WCET/300MHz evidence'],
        'proof_sha256':sha(proof_dir/'receipt.json'),'source_sha256':sources,'results':results,
        'artifact_sha256':{p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file() and '.Xil' not in p.parts}},indent=2)+'\n')
    print(json.dumps(results));print('PASS both-stage registered-input mapped probe')

if __name__=='__main__':main()
