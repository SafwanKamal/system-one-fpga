# Offline synthesis only. No hardware manager, programming or board access.
set root [file normalize [file join [file dirname [info script]] ../../..]]
if {[llength $argv] != 1} {error "usage: check_packed_weight_row_ooc.tcl output_directory"}
set out [file normalize [lindex $argv 0]]
file mkdir $out
set_param general.maxThreads 2
foreach bits {6 7 8} {
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [list [file join $root rtl/v2/common/packed_weight_row16.sv]]
    synth_design -mode out_of_context -top packed_weight_row16 \
        -part xck26-sfvc784-2LV-c -generic BITS=$bits
    create_clock -period 10.0 [get_ports clk]
    report_utilization -file [file join $out utilization-$bits.rpt]
    report_timing_summary -file [file join $out synthesis-timing-$bits.rpt]
    set marker [open [file join $out complete-$bits.txt] w]
    puts $marker "isolated synthesis complete; no route/timing or board qualification"
    close $marker
    close_project
}
