"""Separate origin-probe physical implementation. No PS init or target action.

Bitstream generation is a separate stage after independent routed review.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-amp-deployment-v1'
RTL=ROOT/'rtl/v2/candidates/typed200_amp_probe/axi_origin_probe.v'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True)
 ap.add_argument('--simulation',default='probe-sim-v4')
 ap.add_argument('--stage',choices=['implementation','bitstream'],default='implementation');a=ap.parse_args()
 assert re.fullmatch(r'probe-physical-v[0-9]+',a.attempt)
 out=BASE/a.attempt;short='S:/'+out.relative_to(ROOT).as_posix()
 assert Path('S:/').samefile(ROOT)
 if a.stage=='implementation':
  assert re.fullmatch(r'probe-sim-v[0-9]+',a.simulation)
  r=json.loads((BASE/a.simulation/'receipt.json').read_text())
  assert r['passed'] and r['rtl_sha256']==hashlib.sha256(RTL.read_bytes()).hexdigest()
  out.mkdir(exist_ok=False)
  source=out/'axi_origin_probe.v';source.write_bytes(RTL.read_bytes())
  preset=ROOT/'build/v2/typed200-amp-ownership-v1/ps-profile-v4/source-receipt.json'
  config=json.loads(preset.read_text())['config']
  config.update({'CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ':'100',
   'CONFIG.PSU__FPGA_PL1_ENABLE':'0','CONFIG.PSU__USE__S_AXI_GP2':'0',
   'CONFIG.PSU__USE__IRQ0':'0','CONFIG.PSU__MAXIGP0__DATA_WIDTH':'128'})
  for k,v in config.items():assert not any(x in k+v for x in '{}$[];\n\r')
  tcl=f'''set_param general.maxThreads 4
create_project amp_probe {{{short}/project}} -part xck26-sfvc784-2LV-c
add_files -norecurse {{{short}/axi_origin_probe.v}}
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e ps]
set_property -dict [list {' '.join('{'+k+'} {'+v+'}' for k,v in config.items())}] $ps
set probe [create_bd_cell -type module -reference axi_origin_probe origin_probe]
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset reset_pl0]
connect_bd_net [get_bd_pins ps/pl_clk0] [get_bd_pins origin_probe/clk] [get_bd_pins reset_pl0/slowest_sync_clk] [get_bd_pins ps/maxihpm0_fpd_aclk]
connect_bd_net [get_bd_pins ps/pl_resetn0] [get_bd_pins reset_pl0/ext_reset_in]
connect_bd_net [get_bd_pins reset_pl0/peripheral_aresetn] [get_bd_pins origin_probe/reset_n]
connect_bd_intf_net [get_bd_intf_pins ps/M_AXI_HPM0_FPD] [get_bd_intf_pins origin_probe/s_axi]
assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs origin_probe/s_axi/reg0]
validate_bd_design
save_bd_design
write_bd_tcl -force {{{short}/composed-bd.tcl}}
set f [open {{{short}/interface-properties.txt}} w]
foreach x [list [get_bd_intf_pins ps/M_AXI_HPM0_FPD] [get_bd_intf_pins origin_probe/s_axi]] {{
 puts $f $x
 foreach p [lsort [list_property $x]] {{puts $f "$p=[get_property $p $x]"}}
}}
close $f
make_wrapper -files [get_files system.bd] -top -import
set_property top system_wrapper [current_fileset]
set_property synth_checkpoint_mode None [get_files system.bd]
generate_target all [get_files system.bd]
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {{[get_property PROGRESS [get_runs synth_1]] ne "100%"}} {{error "synthesis failed"}}
open_run synth_1
report_timing_summary -report_unconstrained -file {{{short}/synthesis-timing.rpt}}
report_clocks -file {{{short}/synthesis-clocks.rpt}}
write_checkpoint {{{short}/synthesized.dcp}}
opt_design
place_design
write_checkpoint {{{short}/placed.dcp}}
report_timing_summary -report_unconstrained -file {{{short}/placement-timing.rpt}}
set setup [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set f [open {{{short}/placement-gate.json}} w]
puts $f [format {{{{"setup_ns":%s,"required_setup_ns":0.500}}}} $setup]
close $f
if {{$setup<0.500}} {{error "placement rejected; do not route"}}
route_design
write_checkpoint {{{short}/routed.dcp}}
report_timing_summary -report_unconstrained -file {{{short}/route-timing.rpt}}
report_timing -delay_type max -max_paths 20 -file {{{short}/route-critical.rpt}}
report_clocks -file {{{short}/route-clocks.rpt}}
report_cdc -details -file {{{short}/route-cdc.rpt}}
report_clock_interaction -file {{{short}/route-clock-interaction.rpt}}
report_drc -file {{{short}/route-drc.rpt}}
report_exceptions -coverage -file {{{short}/route-exceptions.rpt}}
check_timing -verbose -file {{{short}/route-check-timing.rpt}}
report_utilization -file {{{short}/route-utilization.rpt}}
set setup [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set hold [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set f [open {{{short}/route-status.json}} w]
puts $f [format {{{{"setup_ns":%s,"hold_ns":%s,"routed":true,"bitstream_created":false}}}} $setup $hold]
close $f
if {{$setup<0 || $hold<0}} {{error "routed timing failed"}}
close_project
exit
'''
  (out/'source-receipt.json').write_text(json.dumps(dict(rtl_sha256=r['rtl_sha256'],ps_config=config,
   simulation_receipt_sha256=hashlib.sha256((BASE/a.simulation/'receipt.json').read_bytes()).hexdigest(),
   ps_init_executed=False,target_modified=False),indent=2)+'\n')
 else:
  assert out.is_dir()
  review=json.loads((out/'physical-review.json').read_text());assert review['bitstream_admitted']
  for n,h in review['sha256'].items():assert hashlib.sha256((out/n).read_bytes()).hexdigest()==h,n
  assert not (out/'probe.bit').exists()
  tcl=f'''open_checkpoint {{{short}/routed.dcp}}
write_bitstream {{{short}/probe.bit}}
exit
'''
 script=out/(a.stage+'.tcl');assert not script.exists();script.write_text(tcl)
 cmd=['C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',
      short+'/'+script.name,'-log',short+'/'+a.stage+'-vivado.log','-journal',short+'/'+a.stage+'.jou']
 with (out/(a.stage+'-console.log')).open('wb') as f:
  r=subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
 (out/(a.stage+'-completion.json')).write_text(json.dumps(dict(exit_code=r.returncode,complete=True,stage=a.stage))+'\n')
 assert r.returncode==0,'preserve failed attempt: '+str(out)
 print('PASS probe '+a.stage+'; no PS init or board action',flush=True)
if __name__=='__main__':main()
