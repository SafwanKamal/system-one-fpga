# KR260 (K26 SOM on the KR260 carrier): block design with the v2 encoder as a PL block.
# NOT YET RUN: written before the board arrived, from the Zynq UltraScale+ and KR260
# board-file conventions; expect to fix details on the first run (board-file versions,
# PS presets). It is a starting point, not a verified flow.
#
#   vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl [-tclargs build]
#
# Needs the KR260 board files (Vivado: Tools > Vivado Store > Boards, "Kria KR260").
#   zynq_ultra_ps_e (board preset)  M_AXI_HPM0_FPD -> smartconnect -> encoder s_axil
#                                   S_AXI_HP0_FPD (128-bit) <- smartconnect <- encoder m_axi
#                                   pl_clk0 100 MHz, pl_resetn0 -> proc_sys_reset
#                                   pl_ps_irq0 <- encoder irq
#   kr260_encoder_wrapper           rtl/v2/platform/kr260 (TILE_OUT 32, DRAIN_LANES 4)
# Address map: encoder registers at 0xA000_0000 (4 KiB); the encoder reaches DDR_LOW
# (0x0000_0000 .. 0x7FFF_FFFF). Linux must leave the image region alone: add a
# reserved-memory node (no-map) for 0x6000_0000 + 64 MiB to the device tree.
# Writes build/v2/kr260/sysone_v2_kr260.xpr; with `build`, the bitstream and an .xsa.

set repo_dir [file normalize [file join [file dirname [info script]] .. .. ..]]
set project_dir [file join $repo_dir build v2 kr260]
set build [expr {[lsearch -exact $argv build] >= 0}]

create_project sysone_v2_kr260 $project_dir -part xck26-sfvc784-2LV-c -force
set_property board_part [lindex [lsort [get_board_parts -quiet *kr260_som*]] end] [current_project]
set carrier [lindex [lsort [get_board_parts -quiet *kr260_carrier*]] end]
if {$carrier ne ""} {
    set_property board_connections [list som240_1_connector [string map {:part0 ""} $carrier]:som240_1_connector:1.0] [current_project]
}

set rtl [file join $repo_dir rtl v2]
add_files -norecurse [concat \
    [list [file join $rtl encoder encoder_pkg.sv]] \
    [glob -directory [file join $rtl encoder] *.sv] \
    [list [file join $rtl common sequential_divider.sv] [file join $rtl common sync_fifo.sv] \
          [file join $rtl platform kr260 axi_memory_port.sv] [file join $rtl platform kr260 kr260_encoder.sv] \
          [file join $rtl platform kr260 kr260_encoder_wrapper.v]]]
set_property file_type SystemVerilog [get_files *.sv]
update_compile_order -fileset sources_1

create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ultra_ps_e_0]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list \
    CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} \
    CONFIG.PSU__USE__S_AXI_GP2 {1} CONFIG.PSU__SAXIGP2__DATA_WIDTH {128} \
    CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {100} \
    CONFIG.PSU__USE__IRQ0 {1}] $ps

set enc [create_bd_cell -type module -reference kr260_encoder_wrapper encoder]
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset reset_pl0]
set sc_ctl [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect control_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $sc_ctl
set sc_mem [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect memory_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $sc_mem

set clk [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
connect_bd_net $clk [get_bd_pins encoder/clk] [get_bd_pins reset_pl0/slowest_sync_clk] \
    [get_bd_pins control_interconnect/aclk] [get_bd_pins memory_interconnect/aclk] \
    [get_bd_pins zynq_ultra_ps_e_0/maxihpm0_fpd_aclk] [get_bd_pins zynq_ultra_ps_e_0/saxihp0_fpd_aclk]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins reset_pl0/ext_reset_in]
connect_bd_net [get_bd_pins reset_pl0/peripheral_aresetn] [get_bd_pins encoder/reset_n] \
    [get_bd_pins control_interconnect/aresetn] [get_bd_pins memory_interconnect/aresetn]
connect_bd_intf_net [get_bd_intf_pins zynq_ultra_ps_e_0/M_AXI_HPM0_FPD] [get_bd_intf_pins control_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_interconnect/M00_AXI] [get_bd_intf_pins encoder/s_axil]
connect_bd_intf_net [get_bd_intf_pins encoder/m_axi] [get_bd_intf_pins memory_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins memory_interconnect/M00_AXI] [get_bd_intf_pins zynq_ultra_ps_e_0/S_AXI_HP0_FPD]
connect_bd_net [get_bd_pins encoder/irq] [get_bd_pins zynq_ultra_ps_e_0/pl_ps_irq0]

assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs encoder/s_axil/reg0]
assign_bd_address [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]
validate_bd_design
save_bd_design
make_wrapper -files [get_files system.bd] -top -import
set_property top system_wrapper [current_fileset]
puts "created [file join $project_dir sysone_v2_kr260.xpr]"

if {$build} {
    launch_runs impl_1 -to_step write_bitstream -jobs 4
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
        error "implementation failed: see the impl_1 run log"
    }
    write_hw_platform -fixed -include_bit -force [file join $project_dir sysone_v2_kr260.xsa]
    puts "bitstream and [file join $project_dir sysone_v2_kr260.xsa] written"
}
