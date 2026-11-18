# Measure the completed candidate at several Linux PL clock rates. This does not
# export hardware or change the project; all reports refer to the same placement.
# vivado -mode batch -source scripts/v2/kr260/report_clock_candidates.tcl
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt]
if {[lsearch -exact $argv bram] >= 0} { set build [file join $repo build v2 kr260-opt-bram] }
if {[lsearch -exact $argv wide] >= 0} { set build [file join $repo build v2 kr260-opt-wide] }
if {[lsearch -exact $argv memory] >= 0} { set build [file join $repo build v2 kr260-opt-memory] }
if {[lsearch -exact $argv batch] >= 0} { set build [file join $repo build v2 kr260-opt-batch] }
open_project [file join $build sysone_v2_kr260.xpr]
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Completed routed candidate required"
}
open_run impl_1
report_utilization -hierarchical -hierarchical_depth 5 -file [file join $build utilization-hierarchical.rpt]
set output [open [file join $build clock-candidates.json] w]
puts $output "\["
set separator ""
foreach mhz {80 100 110 125 150} {
    foreach name {clk_pl_0 clk_pl_1} {
        set clock [get_clocks -quiet $name]
        if {[llength $clock] != 1} { error "Missing primary clock $name" }
        set sources [get_property SOURCE_PINS $clock]
        if {[llength $sources] != 1} { error "Unexpected clock source $sources" }
        create_clock -name $name -period [expr {1000.0 / $mhz}] [get_pins $sources]
    }
    report_timing_summary -warn_on_violation -file [file join $build timing-${mhz}mhz.rpt]
    set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
    set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
    if {[llength $setup] != 1 || [llength $hold] != 1} { error "Timing paths missing" }
    set wns [get_property SLACK $setup]
    set whs [get_property SLACK $hold]
    set pass [expr {$wns >= 0 && $whs >= 0 ? "true" : "false"}]
    puts $output "$separator{\"mhz\": $mhz, \"setup_slack_ns\": $wns, \"hold_slack_ns\": $whs, \"passes\": $pass}"
    set separator ","
}
puts $output "\]"
close $output
close_project
