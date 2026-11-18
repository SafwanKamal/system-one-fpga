"""Matched registered endpoint probe; actual stored shape-bank paths and overall STA."""
from pathlib import Path
import argparse,json,re,shutil,subprocess
from create_typed200_row_range_csa_candidate import ROOT,OUT,PARENT,verify,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-row-range-csa-ooc-v1');a=ap.parse_args()
    verify();assert Path('S:/').samefile(ROOT)
    proofs={}
    for name in ('typed200-row-range-csa-arithmetic-v1','typed200-row-range-csa-endpoint-formal-v1'):
        folder=ROOT/'build/v2'/name;p=folder/'receipt.json';r=json.loads(p.read_text());assert r['passed']
        for n,h in r['source_sha256'].items():assert sha(ROOT/n)==h,n
        for n,h in r['artifact_sha256'].items():assert sha(folder/n)==h,n
        proofs[p.relative_to(ROOT).as_posix()]=sha(p)
    b=ROOT/'build/v2'/a.name;b.mkdir(exist_ok=False);short=f'S:/build/v2/{a.name}'
    header=(PARENT/'contracts/typed_intent_axil.sv').read_text().split('(',1)[1].split('\n);',1)[0]
    ports=[];direction=width=None
    for chunk in header.split(','):
        chunk=chunk.strip();m=re.fullmatch(r'(input|output)\s+(?:logic|wire)\s*(\[[^]]+\])?\s*(\w+)',chunk)
        if m:direction,width,n=m.groups();width=width or ''
        else:n=chunk;assert re.fullmatch(r'\w+',n),chunk
        ports.append((direction,width,n))
    assert len({n for d,w,n in ports})==len(ports)
    code='module endpoint_probe ('+header+'\n);\n'
    for d,w,n in ports:
        if n!='clk':code+=f'logic {w} sampled_{n};\n'
    code+='always_ff @(posedge clk) begin\n'
    for d,w,n in ports:
        if n=='clk':continue
        code+=f' sampled_{n}<={n};\n' if d=='input' else f' {n}<=sampled_{n};\n'
    code+='end\n'
    code+='typed_intent_axil endpoint('+','.join(f'.{n}({n if n=="clk" else "sampled_"+n})' for d,w,n in ports)+');\nendmodule\n'
    code=re.sub(r'\boutput wire\b','output logic',code)
    (b/'probe.sv').write_text(code);(b/'probe.xdc').write_text('create_clock -name probe_clk -period 5.000 [get_ports clk]\n')
    sources={};results={}
    for mode,source in [('control',PARENT),('row_range_csa',OUT)]:
        out=b/mode;out.mkdir()
        for name in ('typed_publication_gate.sv','typed_intent_guard.sv','typed_intent_axil.sv'):
            p=source/'contracts'/name;shutil.copyfile(p,out/name);sources[p.relative_to(ROOT).as_posix()]=sha(p)
        script=fr'''set_param general.maxThreads 2
create_project -in_memory -part xck26-sfvc784-2LV-c
read_verilog -sv [glob {{{short}/{mode}/*.sv}}]
read_verilog -sv {{{short}/probe.sv}}
read_xdc {{{short}/probe.xdc}}
synth_design -top endpoint_probe -part xck26-sfvc784-2LV-c -mode out_of_context
set out {{{short}/{mode}}}
set shape [get_cells -quiet -hier -regexp {{.*endpoint/bank_reg\[(5|28)\].*}}]
set shape [filter $shape {{REF_NAME =~ FD*}}]
if {{[llength $shape]==0}} {{error "Missing actual stored shape source flops"}}
set paths [get_timing_paths -from $shape -delay_type max -max_paths 1]
if {{[llength $paths]!=1}} {{error "Missing stored shape timing path"}}
report_timing -from $shape -delay_type max -max_paths 30 -input_pins -file [file join $out shape-paths.rpt]
set overall [get_timing_paths -delay_type max -max_paths 1]
report_timing -delay_type max -max_paths 30 -input_pins -file [file join $out overall-paths.rpt]
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
set f [open [file join $out metrics.json] w]
puts $f [format {{{{"overall_slack_ns":%s,"shape_slack_ns":%s,"shape_data_ns":%s,"shape_levels":%s,"shape_source_flops":%d,"carry_cells":%d}}}} [get_property SLACK $overall] [get_property SLACK $paths] [get_property DATAPATH_DELAY $paths] [get_property LOGIC_LEVELS $paths] [llength $shape] [llength [get_cells -hier -filter {{REF_NAME == CARRY8}}]]]
close $f
write_checkpoint [file join $out mapped.dcp]
close_project
'''
        (out/'synth.tcl').write_text(script)
        with (out/'console.log').open('w') as log:
            r=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
                '-log',f'{short}/{mode}/vivado.log','-source',f'{short}/{mode}/synth.tcl'],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        (out/'status.json').write_text(json.dumps({'exit_code':r.returncode})+'\n');assert r.returncode==0,mode
        results[mode]=json.loads((out/'metrics.json').read_text())
    gain=results['row_range_csa']['shape_slack_ns']-results['control']['shape_slack_ns']
    overall_gain=results['row_range_csa']['overall_slack_ns']-results['control']['overall_slack_ns']
    (b/'receipt.json').write_text(json.dumps({'passed':True,'results':results,'shape_gain_ns':gain,'overall_gain_ns':overall_gain,
        'scope':'Actual full endpoint with identical registered inputs/output captures; actual bank5/28 paths and overall paths',
        'limits':['Probe shell models launch/capture boundaries, no candidate cycle added','Does not model full encoder fanout or physical placement; no WCET or frequency qualification'],
        'proof_sha256':proofs,'source_sha256':sources,
        'artifact_sha256':{p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file() and '.Xil' not in p.parts}},indent=2)+'\n')
    print(json.dumps(results));print('PASS matched endpoint probe')
if __name__=='__main__':main()
