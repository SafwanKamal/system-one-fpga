set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 score-distance-ooc]
foreach mode {0 1} {
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [file join $repo simulation v2 score_distance_ooc.sv]
    set started [clock milliseconds]
    synth_design -top score_distance_ooc -mode out_of_context -generic FABRIC_DISTANCE=$mode
    create_clock -name kernel_clk -period 3.333333 [get_ports clk]
    report_utilization -file [file join $output utilization-$mode.rpt]
    report_timing -delay_type max -max_paths 10 -input_pins -file [file join $output critical-$mode.rpt]
    set external [get_cells -hier -filter {NAME =~ *distance_reg* && REF_NAME =~ FD*}]
    set dsp [get_cells -hier -filter {REF_NAME == DSP48E2}]
    set out [open [file join $output dsp-$mode.txt] w]
    foreach cell $dsp {
        puts $out "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"
    }
    close $out
    set path [get_timing_paths -quiet -delay_type max -max_paths 1]
    set out [open [file join $output result-$mode.json] w]
    puts $out [format {{"fabric_distance":%d,"external_distance_ff":%d,"dsps":%d,"estimated_setup_slack_ns":%s,"native_seconds":%.3f,"routed":false}} $mode [llength $external] [llength $dsp] [get_property SLACK $path] [expr {([clock milliseconds]-$started)/1000.0}]]
    close $out
    write_checkpoint [file join $output synthesized-$mode.dcp]
    close_project
}
