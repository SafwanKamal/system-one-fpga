# Program the Nexys 4 DDR with the bitstream from scripts/build_sysone.tcl.
#
# Board on USB (the PROG/UART port), then from the repository root:
#   vivado -mode batch -source scripts/program_board.tcl
#
# This loads the FPGA over JTAG; the design is lost at power-off. To keep it,
# write the configuration flash from the Hardware Manager instead.

set repo_dir [file normalize [file join [file dirname [info script]] ..]]
set bitstream [file join $repo_dir build top sysone_top.bit]

if {![file exists $bitstream]} {
    error "no bitstream at $bitstream: run scripts/build_sysone.tcl first"
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
