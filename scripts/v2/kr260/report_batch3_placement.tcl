# Read-only reporting from a completed placement checkpoint, never rerun placement.
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-batch3]
set placed [file join $build sysone_v2_kr260.runs impl_1 system_wrapper_placed.dcp]
if {![file exists $placed]} { error "Completed placement checkpoint required" }
if {[llength [get_projects -quiet]]} { close_project }
open_checkpoint $placed
report_utilization -file [file join $build placed-utilization.rpt]
report_timing_summary -warn_on_violation -file [file join $build placed-timing.rpt]
report_high_fanout_nets -timing -load_types -max_nets 40 -file [file join $build placed-fanout.rpt]
report_design_analysis -congestion -file [file join $build placed-congestion.rpt]
report_incremental_reuse -file [file join $build placed-reuse.rpt]
close_design
