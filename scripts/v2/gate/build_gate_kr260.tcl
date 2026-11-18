# KR260 bitstream for the agent-gate bridge.
# vivado -mode batch -source build_gate_kr260.tcl -tclargs <build_dir> <src_dir> <variant>
#   variant = prod  : production bridge (no loopback, no injector)
#           = loop  : TEST build (PHY MII loopback + fabric frame injector)
# <src_dir> holds copies of the RTL, the XDC and (for loop) gate_inject_rom.hex.
set build_dir [lindex $argv 0]
set src_dir   [lindex $argv 1]
set variant   [lindex $argv 2]
set_param general.maxThreads 4
file mkdir $build_dir
create_project gate_kr260 $build_dir -part xck26-sfvc784-2LV-c -force
set som [lindex [lsort [get_board_parts -quiet *kr260_som*]] end]
if {$som eq ""} {error "KR260 board preset missing"}
set_property board_part $som [current_project]

# ---------------- PS block design: HPM0 FPD -> AXI4-Lite status window at 0xA000_0000
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ultra_ps_e_0]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__MAXIGP0__DATA_WIDTH {32} \
    CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} CONFIG.PSU__USE__S_AXI_GP2 {0} \
    CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {100} \
    CONFIG.PSU__FPGA_PL1_ENABLE {0} CONFIG.PSU__USE__IRQ0 {0}] $ps
set ic  [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect ctl_ic]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $ic
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset rst_axi]
create_bd_port -dir I -type clk -freq_hz 125000000 axi_clk
create_bd_port -dir I axi_locked
create_bd_port -dir O -type rst axi_aresetn
create_bd_port -dir O -type rst pl_resetn
set m [create_bd_intf_port -mode Master -vlnv xilinx.com:interface:aximm_rtl:1.0 M_AXI]
set_property -dict [list CONFIG.PROTOCOL {AXI4LITE} CONFIG.ADDR_WIDTH {40} CONFIG.DATA_WIDTH {32} \
    CONFIG.FREQ_HZ {125000000}] $m
set_property CONFIG.ASSOCIATED_BUSIF {M_AXI} [get_bd_ports axi_clk]
set_property CONFIG.ASSOCIATED_RESET {axi_aresetn} [get_bd_ports axi_clk]
connect_bd_net [get_bd_ports axi_clk] [get_bd_pins zynq_ultra_ps_e_0/maxihpm0_fpd_aclk] \
    [get_bd_pins ctl_ic/aclk] [get_bd_pins rst_axi/slowest_sync_clk]
connect_bd_net [get_bd_ports axi_locked] [get_bd_pins rst_axi/dcm_locked]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins rst_axi/ext_reset_in] [get_bd_ports pl_resetn]
connect_bd_net [get_bd_pins rst_axi/peripheral_aresetn] [get_bd_pins ctl_ic/aresetn] [get_bd_ports axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins zynq_ultra_ps_e_0/M_AXI_HPM0_FPD] [get_bd_intf_pins ctl_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ctl_ic/M00_AXI] $m
assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs M_AXI/Reg]
validate_bd_design
save_bd_design
make_wrapper -files [get_files system.bd] -top -import
generate_target all [get_files system.bd]

# ---------------- RTL
set rtl [list gate_bridge_prims.sv gate_rules.sv gate_core.sv gate_async_fifo.sv gate_eth_rx.sv \
             gate_rgmii.sv gate_mdio.sv gate_test_injector.sv gate_bridge_core.sv gate_bridge_io.sv \
             gate_bridge_top.v gate_kr260_top.v]
foreach f $rtl { add_files -norecurse [file join $src_dir $f] }
add_files -fileset constrs_1 -norecurse [file join $src_dir kr260_gate_bridge.xdc]
set_property top gate_kr260_top [current_fileset]
if {$variant eq "loop"} {
    set rom [file join $src_dir gate_inject_rom.hex]
    set_property generic "LOOPBACK=1 TEST_INJECT=1 INJ_ROM_FILE=\"$rom\"" [current_fileset]
} elseif {$variant ne "prod"} { error "variant must be prod or loop" }

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_timing_summary -file [file join $build_dir routed-timing.rpt]
report_utilization -file [file join $build_dir routed-utilization.rpt]
report_datasheet -file [file join $build_dir routed-datasheet.rpt]
report_methodology -file [file join $build_dir routed-methodology.rpt]
report_drc -file [file join $build_dir routed-drc.rpt]
set setup [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set hold  [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set fh [open [file join $build_dir summary.txt] w]
puts $fh "variant $variant"
puts $fh "wns_ns $setup"
puts $fh "whs_ns $hold"
close $fh
set bit [glob -nocomplain [file join $build_dir gate_kr260.runs impl_1 *.bit]]
file copy -force [lindex $bit 0] [file join $build_dir gate_kr260_top.bit]
puts "GATE_BUILD_DONE wns=$setup whs=$hold"
exit
