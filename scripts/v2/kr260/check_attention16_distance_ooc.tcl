set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 attention16-distance-ooc]
foreach lanes {32 16} {
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [file join $repo rtl v2 encoder encoder_pkg.sv]
    read_verilog -sv [file join $repo rtl v2 common sequential_divider.sv]
    read_verilog -sv [file join $repo rtl v2 common attention_probability.sv]
    read_verilog -sv [file join $repo rtl v2 common attention_probability_input.sv]
    if {$lanes==32} {
        read_verilog -sv [file join $repo build v2 kr260-opt-source-row-bram-large rtl-snapshot encoder attention_engine.sv]
    } else {
        read_verilog -sv [file join $repo build v2 score-distance-cut engine-sources attention_engine.sv]
    }
    set started [clock milliseconds]
    synth_design -top attention_engine -mode out_of_context -generic LANES=$lanes -generic READ_LATENCY=5 -generic MAC_LATENCY=2 -generic PIPELINED_DOT=1 -generic LOCAL_QUERY_REGISTERS=1 -generic LOCAL_ACCUMULATOR_CONTROLS=3 -generic EXP_TABLE_IN_BRAM=1 -generic PROBABILITY_PIPELINE=1 -generic PROBABILITY_INPUT_CAPTURE=1
    create_clock -period 3.333333 -name engine_clk [get_ports clk]
    report_utilization -file [file join $output utilization-$lanes.rpt]
    report_timing -delay_type max -max_paths 10 -input_pins -file [file join $output critical-$lanes.rpt]
    set distance [get_cells -hier -filter {NAME =~ *e_distance_reg* && REF_NAME =~ FD*}]
    set dsps [get_cells -hier -filter {NAME =~ *e_product_reg* && REF_NAME == DSP48E2}]
    set out [open [file join $output distance-dsp-$lanes.txt] w]
    foreach cell $dsps {
        puts $out "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"
    }
    close $out
    set path [get_timing_paths -quiet -delay_type max -max_paths 1]
    set out [open [file join $output result-$lanes.json] w]
    puts $out [format {{"lanes":%d,"external_distance_ff":%d,"distance_dsps":%d,"estimated_setup_slack_ns":%s,"native_seconds":%.3f,"routed":false}} $lanes [llength $distance] [llength $dsps] [get_property SLACK $path] [expr {([clock milliseconds]-$started)/1000.0}]]
    close $out
    write_checkpoint [file join $output synthesized-$lanes.dcp]
    close_project
}
