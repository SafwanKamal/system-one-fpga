"""Matched mapped probe for the placed contract-comparison path, no hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from create_typed200_validation_tree_candidate import ROOT, OUT, PARENT, verify


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-validation-tree-ooc-v1');a=ap.parse_args()
    verify();assert Path('S:/').samefile(ROOT)
    proof=json.loads((ROOT/'build/v2/typed200-validation-tree-formal-v1/receipt.json').read_text())
    assert proof['passed']
    for n,h in proof['source_sha256'].items():assert sha(ROOT/n)==h,n
    b=ROOT/'build/v2'/a.name;b.mkdir(exist_ok=False);short=f'S:/build/v2/{a.name}'
    old=(PARENT/'contracts/typed_intent_guard.sv').read_text()
    header=old.split(') (',1)[1].split('\n);',1)[0]
    ports=[]
    for line in re.findall(r'^\s*(?:input|output)\s+(?:logic|wire)\s+(?:\[[^]]+\]\s*)?([^\n]+)',header,re.M):
        for n in line.rstrip().rstrip(',').split(','):
            n=n.strip();assert re.fullmatch(r'[a-z_]+',n),n;ports.append(n)
    assert len(ports)==len(set(ports)) and 'request_contract' in ports and 'elapsed' in ports
    connects=','.join(f'.{n}({"contract_reg" if n=="request_contract" else n})' for n in ports)
    probe='module contract_probe ('+header+'\n);\n'+'''logic [255:0] contract_reg;
always_ff @(posedge clk) begin
  if(reset) contract_reg<=0;
  else contract_reg<=request_contract;
end
'''+f'typed_intent_guard guard_inst({connects});\nendmodule\n'
    (b/'probe.sv').write_text(probe)
    (b/'probe.xdc').write_text('create_clock -name probe_clk -period 5.000 [get_ports clk]\n')
    source_map={}
    for mode,parent in [('control',PARENT),('tree',OUT)]:
        out=b/mode
        if mode=='control':
            prior=ROOT/'build/v2/typed200-profile-tree-ooc-v1'
            assert json.loads((prior/'control/status.json').read_text())['exit_code']==0
            for n in ['probe.sv','probe.xdc']:assert sha(b/n)==sha(prior/n)
            shutil.copytree(prior/'control',out)
            for name in ['typed_intent_guard.sv','typed_publication_gate.sv']:
                src=PARENT/'contracts'/name;assert sha(out/name)==sha(src)
                source_map[(out/name).relative_to(b).as_posix()]={'source':src.relative_to(ROOT).as_posix(),'sha256':sha(src)}
            continue
        out.mkdir()
        for name in ['typed_intent_guard.sv','typed_publication_gate.sv']:
            src=parent/'contracts'/name;dest=out/name;shutil.copyfile(src,dest)
            source_map[dest.relative_to(b).as_posix()]={'source':src.relative_to(ROOT).as_posix(),'sha256':sha(src)}
        script=f'''set_param general.maxThreads 2
create_project -in_memory -part xck26-sfvc784-2LV-c
read_verilog -sv {{{short}/{mode}/typed_publication_gate.sv}}
read_verilog -sv {{{short}/{mode}/typed_intent_guard.sv}}
read_verilog -sv {{{short}/probe.sv}}
read_xdc {{{short}/probe.xdc}}
synth_design -top contract_probe -part xck26-sfvc784-2LV-c -mode out_of_context
set out {{{short}/{mode}}}
if {{[llength [get_clocks probe_clk]] != 1}} {{error "Missing probe clock"}}
set regs [get_cells -hier -filter {{NAME =~ contract_reg* && REF_NAME =~ FD*}}]
if {{[llength $regs] != 256}} {{error "Expected256 real source flops, got [llength $regs]"}}
set pins [get_pins -of_objects $regs -filter {{DIRECTION == OUT}}]
report_timing -from $pins -delay_type max -max_paths 20 -input_pins -file [file join $out contract-paths.rpt]
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_utilization -file [file join $out utilization.rpt]
set f [open [file join $out structure.txt] w]
puts $f "Source contract flops: [llength $regs]"
puts $f "Carry cells: [llength [get_cells -hier -filter {{REF_NAME == CARRY8}}]]"
puts $f "Byte boundary nets: [llength [get_nets -hier -filter {{NAME =~ *request_contract_byte_equal*}}]]"
puts $f "Group boundary nets: [llength [get_nets -hier -filter {{NAME =~ *request_contract_group_equal*}}]]"
close $f
write_checkpoint [file join $out mapped.dcp]
close_project
'''
        (out/'synth.tcl').write_text(script)
        with (out/'console.log').open('w') as log:
            result=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
                '-log',f'{short}/{mode}/vivado.log','-source',f'{short}/{mode}/synth.tcl'],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        (out/'status.json').write_text(json.dumps({'exit_code':result.returncode,'hardware_qualified':False})+'\n')
        assert result.returncode==0,mode
    (b/'receipt.json').write_text(json.dumps({'passed':True,'control_reused_from':'typed200-profile-tree-ooc-v1','registered_contract_source_bits':256,
        'scope':'Matched register-to-guard mapping probe; source flops model existing bank, not a new candidate pipeline stage',
        'limits':['Probe is not composed encoder placement/routing','No interface skew/delay or hardware/WCET claim'],
        'source_sha256':source_map,'artifact_sha256':{p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file() and '.Xil' not in p.parts}},indent=2)+'\n')
    print('PASS mapped contract probe; inspect actual carry depth and boundary retention')


if __name__=='__main__':main()
