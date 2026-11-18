# Out-of-context synthesis + implementation of the agent gate core on the K26 (KR260 SOM).
# Usage: vivado -mode batch -source scripts/v2/gate/synth_gate_ooc.tcl -tclargs <out_dir> [clock_ns]
set out_dir [lindex $argv 0]
set period  [expr {[llength $argv] > 1 ? [lindex $argv 1] : 8.0}]
set part    [expr {[llength $argv] > 2 ? [lindex $argv 2] : "xck26-sfvc784-2LV-c"}]
set here [file dirname [file normalize [info script]]]
set root [file normalize "$here/../../.."]
file mkdir $out_dir

read_verilog -sv [list "$root/rtl/v2/gate/gate_rules.sv" "$root/rtl/v2/gate/gate_core.sv"]
synth_design -top gate_core -part $part -mode out_of_context -flatten_hierarchy rebuilt
create_clock -name clk -period $period [get_ports clk]
set_input_delay  -clock clk [expr {$period * 0.2}] [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -clock clk [expr {$period * 0.2}] [get_ports -filter {DIRECTION == OUT}]
report_utilization -file "$out_dir/synth_utilization.rpt"
opt_design
place_design
route_design
report_utilization -file "$out_dir/routed_utilization.rpt"
report_utilization -hierarchical -file "$out_dir/routed_utilization_hier.rpt"
report_timing_summary -file "$out_dir/routed_timing.rpt"
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]
set fh [open "$out_dir/summary.txt" w]
puts $fh "period_ns $period"
puts $fh "wns_ns $wns"
puts $fh "whs_ns $whs"
close $fh
