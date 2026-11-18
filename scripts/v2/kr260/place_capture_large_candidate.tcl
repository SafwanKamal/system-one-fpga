# One full-placement diagnostic for the frozen, regression-verified capture-large design.
# No incremental constraints, routing, bitstream generation or board deployment.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-capture-large]
set output [file join $build placement]
file mkdir $output
if {[file exists [file join $output system_wrapper_placed.dcp]]} {
    error "Capture large already placed; inspect existing evidence"
}
open_project [file join $build sysone_v2_kr260.xpr]
open_run synth_1
if {[llength [get_pblocks -quiet]]} { error "Unexpected pblocks; inspect before placement" }
set started [clock milliseconds]
opt_design
set opt_seconds [expr {([clock milliseconds]-$started)/1000.0}]
write_checkpoint [file join $output system_wrapper_opt.dcp]
set started [clock milliseconds]
place_design
set place_seconds [expr {([clock milliseconds]-$started)/1000.0}]
write_checkpoint [file join $output system_wrapper_placed.dcp]
report_utilization -file [file join $output utilization.rpt]
report_design_analysis -congestion -file [file join $output congestion.rpt]
report_high_fanout_nets -timing -load_types -max_nets 40 -file [file join $output fanout.rpt]
set summary [open [file join $output frequency-diagnostics.json] w]
puts $summary "\["
set separator ""
foreach mhz {125 150 200 250 300} {
    foreach name {clk_pl_0 clk_pl_1} {
        set clock [get_clocks -quiet $name]
        if {[llength $clock]!=1} { error "Missing clock $name" }
        create_clock -name $name -period [expr {1000.0/$mhz}] [get_pins [get_property SOURCE_PINS $clock]]
    }
    report_timing -delay_type max -max_paths 30 -nworst 1 -input_pins -file [file join $output critical-${mhz}mhz.rpt]
    report_timing_summary -file [file join $output timing-${mhz}mhz.rpt]
    set path [get_timing_paths -quiet -delay_type max -max_paths 1]
    if {[llength $path]!=1} { error "Missing timing path" }
    puts $summary "$separator{\"mhz\":$mhz,\"estimated_setup_slack_ns\":[get_property SLACK $path],\"routed\":false}"
    set separator ","
}
puts $summary "\]"
close $summary
set summary [open [file join $output placement-result.json] w]
puts $summary [format {{"optimization_wall_seconds":%.3f,"placement_wall_seconds":%.3f,"incremental":false,"routing_started":false}} $opt_seconds $place_seconds]
close $summary
close_design
