# Out-of-context synthesis + implementation of the v3 agent gate (core or bridge core) on the K26 (KR260 SOM).
# Usage: vivado -mode batch -source scripts/v2/gate/synth_gate_v3_ooc.tcl -tclargs <out_dir> <core|bridge> [clock_ns]
set out_dir [lindex $argv 0]
set which   [lindex $argv 1]
set period  [expr {[llength $argv] > 2 ? [lindex $argv 2] : 8.0}]
set part    "xck26-sfvc784-2LV-c"
set here [file dirname [file normalize [info script]]]
set root [file normalize "$here/../../.."]
file mkdir $out_dir

set g "$root/rtl/v2/gate"
if {$which eq "core"} {
    set files [list $g/gate_rules.sv $g/gate_csum.sv $g/gate_core_v3.sv]
    set top gate_core_v3
} else {
    set files [list $g/bridge/gate_bridge_prims.sv $g/gate_rules.sv $g/gate_csum.sv $g/gate_core_v3.sv \
               $g/bridge/gate_async_fifo.sv $g/bridge/gate_eth_rx.sv $g/bridge/gate_bridge_core_v3.sv]
    set top gate_bridge_core_v3
}
read_verilog -sv $files
synth_design -top $top -part $part -mode out_of_context -flatten_hierarchy rebuilt
create_clock -name clk -period $period [get_ports clk]
if {$which ne "core"} {
    create_clock -name rxc_a -period $period [get_ports rxc_a]
    create_clock -name rxc_b -period $period [get_ports rxc_b]
    set_clock_groups -asynchronous -group [get_clocks clk] -group [get_clocks rxc_a] -group [get_clocks rxc_b]
}
set_input_delay  -clock clk [expr {$period * 0.2}] [get_ports -filter {DIRECTION == IN && NAME != clk && NAME !~ rxc_*}]
set_output_delay -clock clk [expr {$period * 0.2}] [get_ports -filter {DIRECTION == OUT}]
report_utilization -file "$out_dir/synth_utilization.rpt"
opt_design
place_design
route_design
report_utilization -file "$out_dir/routed_utilization.rpt"
report_utilization -hierarchical -file "$out_dir/routed_utilization_hier.rpt"
report_timing_summary -file "$out_dir/routed_timing.rpt"
report_timing -max_paths 5 -nworst 1 -file "$out_dir/worst_paths.rpt"
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]
set fh [open "$out_dir/summary.txt" w]
puts $fh "top $top"
puts $fh "period_ns $period"
puts $fh "wns_ns $wns"
puts $fh "whs_ns $whs"
close $fh
