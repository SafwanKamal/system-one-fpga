set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 linear-accumulator-ooc]
file mkdir $output
foreach bram {0 1} {
 create_project -in_memory -part xck26-sfvc784-2LV-c
 read_verilog -sv [file join $repo simulation v2 linear_accumulator_probe.sv]
 set start [clock milliseconds]
 synth_design -top linear_accumulator_probe -mode out_of_context -generic USE_BRAM=$bram
 create_clock -period 3.333333 -name kernel_clk [get_ports clk]
 report_utilization -file [file join $output utilization-$bram.rpt]
 report_timing -delay_type max -max_paths 10 -input_pins -file [file join $output critical-$bram.rpt]
 set f [open [file join $output memory-$bram.txt] w]
 foreach cell [get_cells -hier -filter {REF_NAME =~ RAMB*}] {
  puts $f "$cell REF=[get_property REF_NAME $cell] WRITE_MODE_A=[get_property WRITE_MODE_A $cell] WRITE_MODE_B=[get_property WRITE_MODE_B $cell] DOA_REG=[get_property DOA_REG $cell] DOB_REG=[get_property DOB_REG $cell]"
 }
 close $f
 set f [open [file join $output result-$bram.json] w]
 puts $f [format {{"bram":%d,"wall_seconds":%.3f,"routed":false}} $bram [expr {([clock milliseconds]-$start)/1000.0}]]
 close $f
 write_checkpoint [file join $output synthesized-$bram.dcp]
 close_project
}
