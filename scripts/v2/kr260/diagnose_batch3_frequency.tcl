# Diagnostic constraints only: no placement/routing, bitstream, export or clock change.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-batch3]
open_checkpoint [file join $build sysone_v2_kr260.runs impl_1 system_wrapper_placed.dcp]
set output [open [file join $build placed-frequency-diagnostics.json] w]
puts $output "\["
set separator ""
foreach mhz {125 150 200 250 300} {
    foreach name {clk_pl_0 clk_pl_1} {
        set clock [get_clocks -quiet $name]
        if {[llength $clock] != 1} { error "Missing clock $name" }
        set sources [get_property SOURCE_PINS $clock]
        if {[llength $sources] != 1} { error "Unexpected source for $name" }
        create_clock -name $name -period [expr {1000.0 / $mhz}] [get_pins $sources]
    }
    set paths [get_timing_paths -quiet -delay_type max -max_paths 1]
    if {[llength $paths] != 1} { error "Setup paths missing" }
    set slack [get_property SLACK $paths]
    puts $output "$separator{\"mhz\": $mhz, \"estimated_setup_slack_ns\": $slack, \"routed\": false, \"qualified_for_deployment\": false}"
    set separator ","
    report_timing -delay_type max -max_paths 30 -nworst 1 -input_pins -nets -file [file join $build placed-critical-${mhz}mhz.rpt]
}
puts $output "\]"
close $output
report_timing_summary -warn_on_violation -file [file join $build placed-diagnostic-300mhz.rpt]
close_design
