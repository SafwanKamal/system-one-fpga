# Portable, fixed-netlist CPU/RAM benchmark. No routing or bitstream generation.
if {[llength $argv] != 3} { error "checkpoint output-directory threads required" }
lassign $argv checkpoint output threads
if {![string is integer -strict $threads] || $threads < 1 || $threads > 8} { error "threads must be 1..8" }
set_param general.maxThreads $threads
file mkdir $output
open_checkpoint $checkpoint
set started [clock milliseconds]
place_design
set elapsed [expr {([clock milliseconds] - $started) / 1000.0}]
set report [open [file join $output placement-result.json] w]
puts $report [format {{"placement_wall_seconds": %.3f, "threads": %d, "routing_started": false}} $elapsed $threads]
close $report
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -file [file join $output placed-timing.rpt]
close_design
