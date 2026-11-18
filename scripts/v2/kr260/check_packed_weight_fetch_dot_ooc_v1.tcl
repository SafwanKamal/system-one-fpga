# Offline candidate only; no hardware manager, board access or deployed build.
set root [file normalize [file join [file dirname [info script]] ../../..]]
if {[llength $argv] != 1} {error "usage: check_packed_weight_fetch_dot_ooc_v1.tcl output_directory"}
set out [file normalize [lindex $argv 0]]
file mkdir $out
set_param general.maxThreads 2
foreach bits {6 7 8} {
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [list \
        [file join $root rtl/v2/common/packed_weight_row16.sv] \
        [file join $root rtl/v2/common/packed_weight_fetch16_v1.sv] \
        [file join $root rtl/v2/common/signed_int8_dot16_v1.sv] \
        [file join $root rtl/v2/common/packed_weight_fetch_dot16_v1.sv]]
    synth_design -mode out_of_context -top packed_weight_fetch_dot16_v1 \
        -part xck26-sfvc784-2LV-c -generic BITS=$bits
    create_clock -period 10.0 [get_ports clk]
    report_utilization -file [file join $out utilization-$bits.rpt]
    report_timing_summary -file [file join $out synthesis-timing-$bits.rpt]
    write_checkpoint -force [file join $out synthesized-$bits.dcp]
    set marker [open [file join $out complete-$bits.txt] w]
    puts $marker "isolated fetch/unpack/dot synthesis complete; no routing/timing or board qualification"
    close $marker
    close_project
}
