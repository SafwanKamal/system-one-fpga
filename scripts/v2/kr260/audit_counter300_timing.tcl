# Read-only checkpoint analysis after the separate diagnostic placement completes.
# No optimization, placement, routing, timing exceptions or checkpoint overwrite.
set build {S:/build/v2/counter300-encoder384}
set output [file join $build counter-path-audit]
if {![file exists [file join $build place-status.json]]} {error "Placement must complete first"}
if {[file exists $output]} {error "Preserve existing path audit"}
file mkdir $output
set_param general.maxThreads 4
open_checkpoint [file join $build placement placed.dcp]
set period [get_property PERIOD [get_clocks clk_pl_0]]
if {abs($period - 3.333) > 0.001} {error "Expected original 300 MHz placement constraint"}
set out [open [file join $output timing.json] w]
puts $out "\["
set separator ""
foreach {label pattern} {
    read_due {*telemetry_inst*read_due_reg*}
    write_due {*telemetry_inst*write_due_reg*}
    read_delta {*telemetry_inst*read_delta_reg*}
    write_delta {*telemetry_inst*write_delta_reg*}
    event_counters {*telemetry_inst*counts_reg*}
} {
    set cells [get_cells -hier -filter "IS_SEQUENTIAL == 1 && NAME =~ $pattern"]
    if {![llength $cells]} {error "Expected telemetry endpoint group: $label"}
    set pins [get_pins -of_objects $cells -filter {REF_PIN_NAME == D}]
    set path [get_timing_paths -to $pins -delay_type max -max_paths 1]
    if {[llength $path] != 1} {error "Expected constrained path: $label"}
    report_timing -to $pins -delay_type max -max_paths 10 -input_pins -file [file join $output ${label}.rpt]
    puts $out [format {%s{"group":"%s","endpoint_registers":%d,"slack_ns":%s,"data_delay_ns":%s,"routed":false}} $separator $label [llength $cells] [get_property SLACK $path] [get_property DATAPATH_DELAY $path]]
    set separator ","
}
puts $out "\]"
close $out
close_design
