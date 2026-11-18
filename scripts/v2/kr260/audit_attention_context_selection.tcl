set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 attention-context-capture-ooc]
foreach mode {baseline fabric} {
 open_checkpoint [file join $output synthesized-$mode.dcp]
 set target [get_cells -hier -filter {NAME =~ *w_sum_reg* && REF_NAME =~ FD*}]
 if {$mode eq "baseline"} {set target [get_cells -hier -filter {NAME =~ *w_product_reg* && REF_NAME == DSP48E2}]}
 report_timing -to $target -delay_type max -max_paths 10 -input_pins -file [file join $output context-selection-$mode.rpt]
 set paths [get_timing_paths -to $target -delay_type max -max_paths 1]
 set out [open [file join $output context-selection-$mode.json] w]
 puts $out [format {{"slack_ns":%s,"data_delay_ns":%s}} [get_property SLACK $paths] [get_property DATAPATH_DELAY $paths]]
 close $out
 close_design
}
