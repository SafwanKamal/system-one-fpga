set repo S:/
set project_dir S:/build/v2/core-feasibility/p4/vivado
set_param general.maxThreads 4
set board_store [file join $repo build v2 board-store boards Xilinx]
if {[file isdirectory $board_store]} {set_param board.repoPaths [concat [get_param board.repoPaths] [list $board_store]]}
create_project qwen_decoder_kr260 $project_dir -part xck26-sfvc784-2LV-c
set som [lindex [lsort [get_board_parts -quiet *kr260_som*]] end]
if {$som eq ""} {error "KR260 board preset missing"}
set_property board_part $som [current_project]
set_property ip_repo_paths S:/build/v2/core-feasibility/p4/hls/solution/impl/ip [current_project]
update_ip_catalog
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ultra_ps_e_0]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} CONFIG.PSU__USE__S_AXI_GP2 {1} CONFIG.PSU__SAXIGP2__DATA_WIDTH {128} CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {125} CONFIG.PSU__FPGA_PL1_ENABLE {1} CONFIG.PSU__CRL_APB__PL1_REF_CTRL__FREQMHZ {250} CONFIG.PSU__USE__IRQ0 {1}] $ps
set dec [create_bd_cell -type ip -vlnv xilinx.com:hls:qwen_decoder:1.0 decoder]
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset reset_pl0]
set ctl [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect control_interconnect]
set mem [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect memory_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $ctl
set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {1} CONFIG.NUM_CLKS {2}] $mem
set clk [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
set memclk [get_bd_pins zynq_ultra_ps_e_0/pl_clk1]
connect_bd_net $clk [get_bd_pins decoder/ap_clk] [get_bd_pins reset_pl0/slowest_sync_clk] [get_bd_pins control_interconnect/aclk] [get_bd_pins memory_interconnect/aclk] [get_bd_pins zynq_ultra_ps_e_0/maxihpm0_fpd_aclk]
connect_bd_net $memclk [get_bd_pins memory_interconnect/aclk1] [get_bd_pins zynq_ultra_ps_e_0/saxihp0_fpd_aclk]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins reset_pl0/ext_reset_in]
connect_bd_net [get_bd_pins reset_pl0/peripheral_aresetn] [get_bd_pins decoder/ap_rst_n] [get_bd_pins control_interconnect/aresetn] [get_bd_pins memory_interconnect/aresetn]
connect_bd_intf_net [get_bd_intf_pins zynq_ultra_ps_e_0/M_AXI_HPM0_FPD] [get_bd_intf_pins control_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_interconnect/M00_AXI] [get_bd_intf_pins decoder/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins decoder/m_axi_weights] [get_bd_intf_pins memory_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins decoder/m_axi_state] [get_bd_intf_pins memory_interconnect/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins memory_interconnect/M00_AXI] [get_bd_intf_pins zynq_ultra_ps_e_0/S_AXI_HP0_FPD]
connect_bd_net [get_bd_pins decoder/interrupt] [get_bd_pins zynq_ultra_ps_e_0/pl_ps_irq0]
assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs decoder/s_axi_control/Reg]
assign_bd_address [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]
validate_bd_design
save_bd_design
make_wrapper -files [get_files system.bd] -top -import
set_property top system_wrapper [current_fileset]
generate_target all [get_files system.bd]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
# v9d/v9e: congestion-oriented implementation for ~96% CLB occupancy (v8-v9c used defaults).
set_property STEPS.OPT_DESIGN.ARGS.DIRECTIVE Explore [get_runs impl_1]
set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE Explore [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_timing_summary -file [file join $project_dir routed-timing.rpt]
report_utilization -file [file join $project_dir routed-utilization.rpt]
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup]==0 || [llength $hold]==0} {error "Missing routed timing evidence"}
if {[get_property SLACK $setup] < 0 || [get_property SLACK $hold] < 0} {error "Routed timing failed; do not deploy"}
write_hw_platform -fixed -include_bit -force -file [file join $project_dir qwen_decoder.xsa]
puts "QWEN_FPGA_ROUTED_READY"
exit
