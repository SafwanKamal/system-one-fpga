# Only run after full private output/cycle gates; no full design or routing.
set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 linear-request-window-ooc]
if {[file exists $output]} {error "Preserve existing request-window OOC evidence"}
if {![file exists [file join $repo build v2 rtl-request-window-check review.json]]} {error "Completed numerical/cycle review required"}
file mkdir $output
foreach cached {0 1} {
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [file join $repo simulation v2 linear_request_window_composition.sv]
    set started [clock milliseconds]
    synth_design -top linear_request_window_probe -mode out_of_context -generic CACHED_LIMIT=$cached
    create_clock -name kernel_clk -period 3.333333 [get_ports clk]
    report_utilization -file [file join $output utilization-$cached.rpt]
    report_timing -delay_type max -max_paths 10 -input_pins -file [file join $output critical-$cached.rpt]
    set path [get_timing_paths -quiet -delay_type max -max_paths 1]
    set f [open [file join $output result-$cached.json] w]
    puts $f [format {{"cached_limit":%d,"native_seconds":%.3f,"estimated_setup_slack_ns":%s,"routed":false}} $cached [expr {([clock milliseconds]-$started)/1000.0}] [get_property SLACK $path]]
    close $f
    write_checkpoint [file join $output synthesized-$cached.dcp]
    close_project
}
