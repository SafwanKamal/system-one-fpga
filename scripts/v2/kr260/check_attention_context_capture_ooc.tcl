set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 attention-context-capture-ooc]
foreach mode {baseline fabric} {
 create_project -in_memory -part xck26-sfvc784-2LV-c
 foreach name {encoder/encoder_pkg.sv common/sequential_divider.sv common/attention_probability.sv common/attention_probability_input.sv} {
  read_verilog -sv [file join $repo build v2 kr260-opt-request-window-embed-large rtl-snapshot $name]
 }
 if {$mode eq "baseline"} {
  read_verilog -sv [file join $repo build v2 kr260-opt-request-window-embed-large rtl-snapshot encoder attention_engine.sv]
 } else {
  read_verilog -sv [file join $repo build v2 attention-context-capture engine-sources attention_engine.sv]
 }
 set started [clock milliseconds]
 synth_design -top attention_engine -mode out_of_context -generic LANES=16 -generic READ_LATENCY=5 -generic MAC_LATENCY=2 -generic PIPELINED_DOT=1 -generic LOCAL_QUERY_REGISTERS=1 -generic LOCAL_ACCUMULATOR_CONTROLS=3 -generic EXP_TABLE_IN_BRAM=1 -generic PROBABILITY_PIPELINE=1 -generic PROBABILITY_INPUT_CAPTURE=1 -generic FABRIC_SCORE_DISTANCE=1
 create_clock -period 3.333333 -name engine_clk [get_ports clk]
 report_utilization -file [file join $output utilization-$mode.rpt]
 report_timing -delay_type max -max_paths 30 -input_pins -file [file join $output critical-$mode.rpt]
 set ffs [get_cells -hier -filter {NAME =~ *w_sum_reg* && REF_NAME =~ FD*}]
 set dsps [get_cells -hier -filter {NAME =~ *w_product_reg* && REF_NAME == DSP48E2}]
 set out [open [file join $output context-dsp-$mode.txt] w]
 foreach cell $dsps {puts $out "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"}
 close $out
 set path [get_timing_paths -quiet -delay_type max -max_paths 1]
 set out [open [file join $output result-$mode.json] w]
 puts $out [format {{"fabric_context_ff":%d,"context_dsps":%d,"estimated_setup_slack_ns":%s,"native_seconds":%.3f,"routed":false}} [llength $ffs] [llength $dsps] [get_property SLACK $path] [expr {([clock milliseconds]-$started)/1000.0}]]
 close $out
 write_checkpoint [file join $output synthesized-$mode.dcp]
 close_project
}
