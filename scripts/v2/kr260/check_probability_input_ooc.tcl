set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 probability-input-ooc]
foreach pipeline {0 1} {
 create_project -in_memory -part xck26-sfvc784-2LV-c
 read_verilog -sv [file join $repo rtl v2 common attention_probability.sv]
 read_verilog -sv [file join $repo build v2 probability-input-cut engine-sources attention_probability_input.sv]
 read_verilog -sv [file join $output probability_bram_ooc.sv]
 set start [clock milliseconds]
 synth_design -top probability_bram_ooc -mode out_of_context -generic INPUT_CAPTURE=$pipeline
 create_clock -period 3.333333 -name kernel_clk [get_ports clk]
 report_utilization -file [file join $output utilization-$pipeline.rpt]
 report_timing -delay_type max -max_paths 10 -input_pins -file [file join $output critical-$pipeline.rpt]
 set f [open [file join $output result-$pipeline.json] w]
 set paths [get_timing_paths -quiet -delay_type max -max_paths 1]
 puts $f [format {{"pipeline":%d,"wall_seconds":%.3f,"estimated_setup_slack_ns":%s,"routed":false}} $pipeline [expr {([clock milliseconds]-$start)/1000.0}] [get_property SLACK $paths]]
 close $f
 set f [open [file join $output dsp-$pipeline.txt] w]
 foreach cell [get_cells -hier -filter {REF_NAME == DSP48E2}] {
  puts $f "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"
 }
 close $f
 write_checkpoint [file join $output synthesized-$pipeline.dcp]
 close_project
}
