"""Matched predecode/product/rounding/output probe against best functional control."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
from create_typed200_predecode_candidate import ROOT,OUT,verify
CONTROL=ROOT/'rtl/v2/candidates/typed200_profile_cache'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-predecode-ooc-v1');a=ap.parse_args()
    verify();assert Path('S:/').samefile(ROOT)
    proof_dir=ROOT/'build/v2/typed200-predecode-formal-v3';proof=json.loads((proof_dir/'receipt.json').read_text());assert proof['passed']
    for n,h in proof['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in proof['artifact_sha256'].items():assert sha(proof_dir/n)==h,n
    b=ROOT/'build/v2'/a.name;b.mkdir(exist_ok=False);short=f'S:/build/v2/{a.name}'
    (b/'probe.xdc').write_text('create_clock -name probe_clk -period 5.000 [get_ports clk]\n')
    header=(CONTROL/'encoder/add_skip_engine.sv').read_text().split(') (',1)[1].split('\n);',1)[0].replace('BUFFER_ADDRESS_WIDTH-1:0','13:0')
    inputs=[];ports=[]
    for line in header.splitlines():
        m=re.match(r'\s*(input|output) logic\s*(\[[^]]+\])?\s*(\w+)',line)
        if m:
            direction,width,name=m.groups();ports.append(name)
            if direction=='input' and name not in ('clk','reset'):inputs.append((width or '',name))
    layer=OUT/'encoder/encoder_layer.sv';ls=layer.read_text()
    func=ls[ls.index('    function automatic logic signed [25:0] add_round_bias'):ls.index('    logic signed [25:0] add_round_bias_reg;')]
    sources={layer.relative_to(ROOT).as_posix():sha(layer)};results={}
    for mode,source in [('control',CONTROL),('predecode',OUT)]:
        folder=b/mode;folder.mkdir()
        for fn in ('encoder_pkg.sv','add_skip_engine.sv'):
            src=source/'encoder'/fn;shutil.copyfile(src,folder/fn);sources[src.relative_to(ROOT).as_posix()]=sha(src)
        wrapper='module add_skip_probe ('+header+'\n);\n'+func
        wrapper+='logic [5:0] fetch_shift_reg;\nalways_ff @(posedge clk) fetch_shift_reg<=shift;\n'
        wrapper+='\n'.join('logic '+w+' in_'+n+';' for w,n in inputs)+'\n'
        wrapper+='always_ff @(posedge clk) begin\n'+'\n'.join('in_'+n+' <= '+('fetch_shift_reg' if n=='shift' else n)+';' for w,n in inputs)+'\nend\n'
        if mode=='predecode':wrapper+='logic signed [25:0] in_rounding_bias;\nalways_ff @(posedge clk) in_rounding_bias<=add_round_bias(fetch_shift_reg);\n'
        registered={n for w,n in inputs}
        wrapper+='add_skip_engine engine('+','.join('.'+n+'('+('in_'+n if n in registered else n)+')' for n in ports)
        if mode=='predecode':wrapper+=',.rounding_bias(in_rounding_bias)'
        wrapper+=');\nendmodule\n';(folder/'probe.sv').write_text(wrapper)
        stage_pattern='*engine/rounded_reg*' if mode=='control' else '*engine/skip_clamped_reg*'
        bias_pattern='*in_shift_reg*' if mode=='control' else '*in_rounding_bias_reg*'
        script=f'''set_param general.maxThreads 2
create_project -in_memory -part xck26-sfvc784-2LV-c
read_verilog -sv {{{short}/{mode}/encoder_pkg.sv}}
read_verilog -sv {{{short}/{mode}/add_skip_engine.sv}}
read_verilog -sv {{{short}/{mode}/probe.sv}}
read_xdc {{{short}/probe.xdc}}
synth_design -top add_skip_probe -part xck26-sfvc784-2LV-c -mode out_of_context
set out {{{short}/{mode}}}
if {{[llength [get_clocks probe_clk]]!=1}} {{error "Missing5ns clock"}}
set groups [list predecode {{{bias_pattern}}} product {{*engine/product_reg*}} rounding {{{stage_pattern}}} output {{*engine/out_data_reg*}}]
set metrics [list]
foreach {{label pattern}} $groups {{
 set regs [get_cells -quiet -hier -filter "NAME =~ $pattern && REF_NAME =~ FD*"]
 if {{[llength $regs]==0}} {{error "No registers for $label"}}
 report_timing -to $regs -delay_type max -max_paths 20 -input_pins -file [file join $out $label-paths.rpt]
 set path [get_timing_paths -to $regs -delay_type max -max_paths 1]
 if {{[llength $path]!=1}} {{error "Missing $label timing path"}}
 lappend metrics [format {{"%s":{{"flops":%d,"slack_ns":%s,"data_ns":%s,"levels":%s}}}} $label [llength $regs] [get_property SLACK $path] [get_property DATAPATH_DELAY $path] [get_property LOGIC_LEVELS $path]]
}}
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
set overall [get_timing_paths -delay_type max -max_paths 1]
set f [open [file join $out metrics.json] w]
puts $f [format {{{{"stages":{{%s}},"overall_slack_ns":%s,"carry_cells":%d}}}} [join $metrics ,] [get_property SLACK $overall] [llength [get_cells -hier -filter {{REF_NAME == CARRY8}}]]]
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
    (b/'receipt.json').write_text(json.dumps({'passed':True,'scope':'Matched registered-fetch/control/data four-stage probe against profile_cache',
        'limits':['Wrapper launch/capture registers model instruction fetch; no candidate cycles added','Not whole-design placement/routing or target/WCET/300MHz evidence'],
        'proof_sha256':sha(proof_dir/'receipt.json'),'source_sha256':sources,'results':results,
        'artifact_sha256':{p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file() and '.Xil' not in p.parts}},indent=2)+'\n')
    print(json.dumps(results));print('PASS all-stage matched mapping probe')

if __name__=='__main__':main()
