# Separate physical-only experiment. Preserve original placed checkpoint/reports.
set_param general.maxThreads 4
set root S:/build/v2/typed200-flush-physical-v1
set out [file join $root postplace-opt-v1]
if {[file exists $out]} {error "Preserve prior optimization attempt"}
file mkdir $out
open_checkpoint [file join $root place placed.dcp]
phys_opt_design -directive Explore
write_checkpoint [file join $out optimized.dcp]
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
