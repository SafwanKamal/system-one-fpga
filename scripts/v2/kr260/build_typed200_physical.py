"""Isolated 200 MHz PS/PL integration; no package, bitstream or board actions."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
from create_typed200_candidate import ROOT,OUT,verify
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='typed200-physical-v1')
    ap.add_argument('--stage',choices=['synth','place','route'],default='synth');a=ap.parse_args()
    verify();short=Path('S:/');assert short.exists() and short.samefile(ROOT)
    for fn in ['2026-10-15-typed200-validation.json','2026-10-15-typed200-transport-validation.json']:
        r=json.loads((ROOT/'docs/research'/fn).read_text())
        for key in ['source_sha256','documentation_sha256','evidence_sha256']:
            for p,h in r[key].items():assert sha(ROOT/p)==h,p
    build=ROOT/'build/v2'/a.name;bd=f'S:/build/v2/{a.name}'
    if a.stage=='synth':
        build.mkdir(exist_ok=False);rtl=build/'rtl-input';shutil.copytree(OUT,rtl)
        wrapper=ROOT/'rtl/platform/typed200/typed200_encoder_wrapper.v'
        shutil.copyfile(wrapper,rtl/'platform/kr260/typed200_encoder_wrapper.v')
        source=ROOT/'scripts/v2/kr260/create_project_kr260.tcl'
        s=source.read_text().split('if {$preflight} {',1)[0]
        s='set argv {preflight optimized 200 bram wide memory context-capture large}\n'+s
        s=re.sub(r'^set repo_dir .*$', 'set repo_dir [file normalize {S:/}]',s,count=1,flags=re.M)
        i=s.index('set board_store ');s=s[:i]+f'set project_dir {{{bd}}}\n'+s[i:]
        s=s.replace('set rtl [file join $repo_dir rtl v2]',f'set rtl {{{bd}/rtl-input}}')
        s=s.replace('platform kr260 kr260_encoder.sv','platform kr260 typed200_encoder.sv').replace('platform kr260 kr260_encoder_wrapper.v','platform kr260 typed200_encoder_wrapper.v')
        i=s.index('if {$optimized} {\n    # Freeze');s=s[:i]+'lappend source_files {*}[glob -directory [file join $rtl contracts] *.sv]\n'+s[i:]
        s=s.replace('-reference kr260_encoder_wrapper','-reference typed200_encoder_wrapper')
        s=s.replace('set rst [create_bd_cell', '''set permit [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio deployment_permit]
set_property -dict [list CONFIG.C_GPIO_WIDTH {1} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000}] $permit
set rst [create_bd_cell''')
        s=s.replace('CONFIG.NUM_MI {1}] $sc_ctl','CONFIG.NUM_MI {2}] $sc_ctl')
        s=s.replace('[get_bd_pins encoder/clk] [get_bd_pins reset_pl0/slowest_sync_clk]',
                    '[get_bd_pins encoder/clk] [get_bd_pins deployment_permit/s_axi_aclk] [get_bd_pins reset_pl0/slowest_sync_clk]')
        s=s.replace('[get_bd_pins encoder/reset_n] \\', '[get_bd_pins encoder/reset_n] [get_bd_pins deployment_permit/s_axi_aresetn] \\')
        s=s.replace('connect_bd_net [get_bd_pins encoder/irq]', '''connect_bd_intf_net [get_bd_intf_pins control_interconnect/M01_AXI] [get_bd_intf_pins deployment_permit/S_AXI]
connect_bd_net [get_bd_pins deployment_permit/gpio_io_o] [get_bd_pins encoder/deployment_ready]
connect_bd_net [get_bd_pins encoder/irq]''')
        s=s.replace('assign_bd_address [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]',
            'assign_bd_address -offset 0xA0001000 -range 4K [get_bd_addr_segs deployment_permit/S_AXI/Reg]\nassign_bd_address [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]')
        s+='''
set_param general.maxThreads 4
write_bd_tcl -force [file join $project_dir composed-bd.tcl]
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Typed synthesis failed"}
open_run synth_1
report_utilization -file [file join $project_dir synthesis-utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $project_dir synthesis-timing.rpt]
report_timing -delay_type max -max_paths 20 -input_pins -file [file join $project_dir synthesis-critical.rpt]
write_checkpoint [file join $project_dir synthesized.dcp]
close_project
'''
        inputs={p.relative_to(rtl).as_posix():sha(p) for p in rtl.rglob('*') if p.suffix in ('.sv','.v')}
        (build/'input-proof.json').write_text(json.dumps({'candidate_sha256':sha(OUT/'candidate.json'),
            'wrapper_sha256':sha(wrapper),'board_setup_sha256':sha(source),'rtl_sha256':inputs,
            'clock_mhz':200,'control_base':'0xa0000000','permit_base':'0xa0001000',
            'permit_reset_value':0,'hardware_qualified':False},indent=2)+'\n')
        output=build
    else:
        assert json.loads((build/'synth-status.json').read_text())['exit_code']==0
        output=build/a.stage;output.mkdir(exist_ok=False)
        if a.stage=='place':
            action='open_run synth_1\nopt_design\nplace_design'
        else:
            review=json.loads((build/'placement-review.json').read_text());assert review['route_approved']
            for p,h in review['evidence_sha256'].items():assert sha(build/p)==h,p
            action=f'open_checkpoint {{{bd}/place/placed.dcp}}\nphys_opt_design\nroute_design'
        s=f'''set_param general.maxThreads 4
set project_dir {{{bd}}}
open_project [file join $project_dir sysone_v2_kr260.xpr]
{action}
set output [file join $project_dir {a.stage}]
write_checkpoint [file join $output {'placed' if a.stage=='place' else 'routed'}.dcp]
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $output timing.rpt]
report_timing -delay_type max -max_paths 30 -input_pins -file [file join $output critical.rpt]
report_cdc -details -file [file join $output cdc.rpt]
report_clock_interaction -file [file join $output clock-interaction.rpt]
report_drc -file [file join $output drc.rpt]
check_timing -verbose -file [file join $output check-timing.rpt]
set f [open [file join $output timing.json] w]
puts $f [format {{{{"setup_ns":%s,"hold_ns":%s,"routed":{str(a.stage=='route').lower()}}}}} [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]]
close $f
close_project
'''
    script=output/f'{a.stage}.tcl';script.write_text(s)
    with (output/'console.log').open('w') as f:
        r=subprocess.run(['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-nojournal',
            '-log',f'{bd}/{"" if a.stage=="synth" else a.stage+"/"}vivado.log','-source',
            f'{bd}/{"" if a.stage=="synth" else a.stage+"/"}{a.stage}.tcl'],cwd=Path('S:/build/v2')/a.name,stdout=f,stderr=subprocess.STDOUT)
    (build/f'{a.stage}-status.json').write_text(json.dumps({'exit_code':r.returncode,'stage':a.stage,'target_mhz':200,
        'routed':a.stage=='route','hardware_qualified':False})+'\n')
    raise SystemExit(r.returncode)
if __name__=='__main__':main()
