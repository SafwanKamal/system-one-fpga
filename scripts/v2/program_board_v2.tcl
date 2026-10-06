# Program the Nexys 4 DDR with the v2 bitstream over JTAG.
#
#   vivado -mode batch -source scripts/v2/program_board_v2.tcl
#   vivado -mode batch -source scripts/v2/program_board_v2.tcl -tclargs ddr_test
#   vivado -mode batch -source scripts/v2/program_board_v2.tcl -tclargs <file.bit>

set repo_dir [file normalize [file join [file dirname [info script]] .. ..]]
set build_dir [file join $repo_dir build v2 nexys4ddr]
if {[llength $argv] == 0} {
    set bitstream [file join $build_dir nexys4ddr_link_top.bit]
} elseif {[lindex $argv 0] eq "ddr_test"} {
    set bitstream [file join $build_dir nexys4ddr_ddr_test_top.bit]
} else {
    set bitstream [file normalize [lindex $argv 0]]
}
if {![file exists $bitstream]} {
    error "no bitstream at $bitstream: run scripts/v2/create_project_v2.tcl -tclargs build first"
}

open_hw_manager
connect_hw_server
open_hw_target
set device [lindex [get_hw_devices xc7a100t*] 0]
if {$device eq ""} {
    error "no xc7a100t found on the JTAG chain: is the board on and plugged in?"
}
current_hw_device $device
set_property PROGRAM.FILE $bitstream $device
program_hw_devices $device
puts "programmed $device with $bitstream"
close_hw_target
disconnect_hw_server
close_hw_manager
