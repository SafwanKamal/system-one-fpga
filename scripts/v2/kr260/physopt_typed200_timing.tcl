# Separate physical-only experiment. Preserve original placed checkpoint/reports.
set_param general.maxThreads 4
if {[llength $argv] != 1} {error "Expected a completed new timing experiment"}
set name [lindex $argv 0]
if {![regexp {^typed200-(clock|profile-tree)-physical-v[0-9]+$} $name]} {error "Unexpected experiment"}
set root [file normalize [file join S:/build/v2 $name]]
set out [file join $root postplace-opt-v1]
if {[file exists $out]} {error "Preserve prior optimization attempt"}
file mkdir $out
open_checkpoint [file join $root place placed.dcp]
phys_opt_design -directive Explore
write_checkpoint [file join $out optimized.dcp]
if {[lsort [get_clocks -quiet *]] ne {clk_pl_0 clk_pl_1}} {error "Unexpected full clocks"}
if {[get_property PERIOD [get_clocks clk_pl_0]] != 5.000 || [get_property PERIOD [get_clocks clk_pl_1]] != 10.000} {error "Clock period changed"}
report_clocks -file [file join $out clocks.rpt]
set retain [open [file join $out retention.txt] w]
foreach pattern {*epoch_inst* *publication_inst* *deployment_permit*} {
    set retained [get_cells -hier -filter "NAME =~ $pattern"]
    puts $retain "$pattern cells [llength $retained]"
    if {[llength $retained]==0} {error "Missing retained typed control $pattern"}
}
close $retain
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_timing -delay_type max -max_paths 30 -input_pins -file [file join $out critical.rpt]
report_utilization -file [file join $out utilization.rpt]
report_methodology -file [file join $out methodology.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
check_timing -verbose -file [file join $out check-timing.rpt]
set cells [get_cells -quiet -hier -filter {NAME =~ *gen_stream_results.stream_inst/fifo_inst*}]
set async [get_cells -quiet -hier -filter {NAME =~ *gen_stream_results.stream_inst/fifo_inst* && (REF_NAME == FDCE || REF_NAME == FDPE || REF_NAME == FDCP)}]
set f [open [file join $out fifo-reset-mapping.txt] w]
puts $f "FIFO cells: [llength $cells]"
puts $f "FIFO asynchronous reset/preset flip-flops: [llength $async]"
close $f
if {[llength $cells]==0 || [llength $async]!=0} {error "Synchronous FIFO mapping failed"}
set f [open [file join $out timing.json] w]
puts $f [format {{"setup_ns":%s,"hold_ns":%s,"routed":false}} [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]]
close $f
close_design
