# Standalone timing-only implementation. Never opens or saves the sealed project.
set_param general.maxThreads 4
set out {S:/build/v2/typed200-row-range-csa-route-v1}
open_checkpoint [file join $out input placed.dcp]
set clocks [lsort [get_clocks -quiet *]]
if {$clocks ne {clk_pl_0 clk_pl_1}} {error "Unexpected input clocks"}
if {[get_property PERIOD [get_clocks clk_pl_0]]!=5.000 || [get_property PERIOD [get_clocks clk_pl_1]]!=10.000} {error "Input clock periods changed"}
report_clocks -file [file join $out input-clocks.rpt]
report_exceptions -coverage -file [file join $out input-exceptions.rpt]
# Same default timing-only physical optimization used by the established flow.
# No retiming, RTL changes, timing exceptions, clock edits or bitstream commands.
phys_opt_design
route_design
write_checkpoint [file join $out routed.dcp]
report_route_status -file [file join $out route-status.rpt]
report_utilization -file [file join $out utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $out timing.rpt]
report_timing -delay_type max -max_paths 30 -input_pins -file [file join $out setup-critical.rpt]
report_timing -delay_type min -max_paths 30 -input_pins -file [file join $out hold-critical.rpt]
report_cdc -details -file [file join $out cdc.rpt]
report_clock_interaction -file [file join $out clock-interaction.rpt]
report_clocks -file [file join $out clocks.rpt]
report_exceptions -coverage -file [file join $out exceptions.rpt]
report_drc -file [file join $out drc.rpt]
report_methodology -file [file join $out methodology.rpt]
check_timing -verbose -file [file join $out check-timing.rpt]
set fifo_cells [get_cells -quiet -hier -filter {NAME =~ *gen_stream_results.stream_inst/fifo_inst*}]
set fifo_async [get_cells -quiet -hier -filter {NAME =~ *gen_stream_results.stream_inst/fifo_inst* && (REF_NAME == FDCE || REF_NAME == FDPE || REF_NAME == FDCP)}]
set f [open [file join $out fifo-reset-mapping.txt] w]
puts $f "FIFO cells: [llength $fifo_cells]"
puts $f "FIFO asynchronous reset/preset flip-flops: [llength $fifo_async]"
close $f
if {[llength $fifo_cells]==0 || [llength $fifo_async]!=0} {error "FIFO mapping changed"}
set f [open [file join $out timing.json] w]
puts $f [format {{"setup_ns":%s,"hold_ns":%s,"routed":true}} [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]]
close $f
close_design
