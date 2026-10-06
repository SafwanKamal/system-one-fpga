# Create the v2 Vivado project (project mode, unlike v1's non-project build script).
#
#   vivado -mode batch -source scripts/v2/create_project_v2.tcl                        # create
#   vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build         # + bitstream
#   vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build ddr_test
#   vivado build/v2/nexys4ddr/sysone_v2_nexys4ddr.xpr                                  # GUI
#
# Board: Nexys 4 DDR (xc7a100tcsg324-1). Tops (rtl/v2/README.md, bring-up steps):
#   link      nexys4ddr_link_top      step 2: DDR2 read/write over Ethernet (default)
#   ddr_test  nexys4ddr_ddr_test_top  step 1: DDR2 self-test and bandwidth
# Both tops and both constraint files are in the project; the one not selected is
# disabled, so switching is `set_property top ...` plus enabling its XDC (or rerun
# this script). The v1 blocks that v2 reuses (Ethernet RX/TX, CRC, dense_engine,
# channel_requantizer) are part of the project.
#
# The MIG DDR2 controller is generated from ip/v2/nexys4ddr/mig_ddr2.prj (Digilent's
# out-of-box configuration for this board). The project lives under build/, which
# is gitignored; everything needed to recreate it is in this script and the repo.
#
# Every path goes through [list ...] or a quoted variable, because the repository
# may sit under a folder whose name contains spaces.

set repo_dir [file normalize [file join [file dirname [info script]] .. ..]]
set part xc7a100tcsg324-1
set board nexys4ddr
set project_name sysone_v2_$board
set project_dir [file join $repo_dir build v2 $board]
set build [expr {[lsearch -exact $argv build] >= 0}]
set top_name [expr {[lsearch -exact $argv ddr_test] >= 0 ? "ddr_test" : "link"}]
set tops [dict create link nexys4ddr_link_top ddr_test nexys4ddr_ddr_test_top]
set xdcs [dict create link nexys4ddr_link.xdc ddr_test nexys4ddr_ddr_test.xdc]
set top [dict get $tops $top_name]

create_project $project_name $project_dir -part $part -force
set_property target_language Verilog [current_project]
set_property default_lib work [current_project]

# ------------------------------------------------------------------ sources
set rtl_dir [file join $repo_dir rtl]
set v2_sources [concat \
    [glob -nocomplain -directory [file join $rtl_dir v2 common] *.sv] \
    [glob -nocomplain -directory [file join $rtl_dir v2 test] *.sv] \
    [glob -nocomplain -directory [file join $rtl_dir v2 link] *.sv] \
    [glob -nocomplain -directory [file join $rtl_dir v2 platform $board] *.sv]]
add_files -norecurse -fileset sources_1 $v2_sources

set shared {
    ethernet_CRC32.sv rmii_RX.sv rmii_TX.sv ethernet_RX.sv ethernet_TX.sv
    ethernet_RX_buffer.sv ethernet_TX_buffer.sv dense_engine.sv channel_requantizer.sv
}
set shared_sources {}
foreach f $shared { lappend shared_sources [file join $rtl_dir $f] }
add_files -norecurse -fileset sources_1 $shared_sources

set_property file_type SystemVerilog [get_files -of_objects [get_filesets sources_1] *.sv]
set_property include_dirs [list $rtl_dir] [get_filesets sources_1]
set_property top $top [get_filesets sources_1]

foreach name [dict keys $xdcs] {
    set xdc [file join $repo_dir constraints v2 [dict get $xdcs $name]]
    add_files -norecurse -fileset constrs_1 [list $xdc]
    set_property is_enabled [expr {$name eq $top_name}] [get_files [list $xdc]]
}

# simulation fileset: the behavioural MIG model and testbench (Verilator is the
# reference flow, see simulation/v2/Makefile; these are here for xsim convenience)
set sim_dir [file join $repo_dir simulation v2]
set sim_sources [glob -nocomplain -directory $sim_dir *.sv]
if {[llength $sim_sources] > 0} {
    add_files -norecurse -fileset sim_1 $sim_sources
    set_property file_type SystemVerilog [get_files -of_objects [get_filesets sim_1] *.sv]
    set_property top memory_link_tb [get_filesets sim_1]
}

# ---------------------------------------------------------------- MIG DDR2
create_ip -name mig_7series -vendor xilinx.com -library ip -module_name mig_ddr2
set mig_xci [get_files mig_ddr2.xci]
set mig_dir [file dirname $mig_xci]
file copy -force [file join $repo_dir ip v2 $board mig_ddr2.prj] [file join $mig_dir mig_ddr2.prj]
set_property -dict [list CONFIG.XML_INPUT_FILE {mig_ddr2.prj} \
                         CONFIG.RESET_BOARD_INTERFACE {Custom} \
                         CONFIG.MIG_DONT_TOUCH_PARAM {Custom} \
                         CONFIG.BOARD_MIG_PARAM {Custom}] [get_ips mig_ddr2]
generate_target all $mig_xci
create_ip_run $mig_xci

update_compile_order -fileset sources_1
puts "created [file join $project_dir $project_name.xpr] (top $top)"

# ------------------------------------------------------------------ build
if {$build} {
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
        error "synthesis failed: see [file join $project_dir $project_name.runs synth_1 runme.log]"
    }
    launch_runs impl_1 -to_step write_bitstream -jobs 4
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
        error "implementation failed: see [file join $project_dir $project_name.runs impl_1 runme.log]"
    }
    open_run impl_1
    set report_dir [file join $repo_dir build v2 $board reports]
    file mkdir $report_dir
    report_utilization -file [file join $report_dir utilization.rpt]
    report_timing_summary -file [file join $report_dir timing_summary.rpt]
    set bit [glob -nocomplain -directory [file join $project_dir $project_name.runs impl_1] *.bit]
    file copy -force [lindex $bit 0] [file join $repo_dir build v2 $board $top.bit]
    puts "bitstream: [file join $repo_dir build v2 $board $top.bit]"
}
