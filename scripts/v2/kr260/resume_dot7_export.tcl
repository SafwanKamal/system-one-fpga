# Resume export only: no synth, opt, place or route calls.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-dot7-large]
set attempt [lindex $argv 0]
if {$attempt ni {export-recovery export-recovery-2}} {error "Explicit export attempt directory required"}
set output [file join $build route-125mhz $attempt]
set bitdir [file join $build sysone_v2_kr260.runs impl_1]
if {[file exists [file join $bitdir system_wrapper.bit]] || [file exists [file join $build sysone_v2_kr260.xsa]]} {error "Existing export must be reviewed"}
open_checkpoint [file join $build route-125mhz system_wrapper_routed.dcp]
report_route_status -file [file join $output route-status.rpt]
report_timing_summary -warn_on_violation -file [file join $output timing.rpt]
puts [exec [file join $repo .venv Scripts python.exe] -I [file join $repo scripts v2 kr260 check_routed_evidence.py] --timing [file join $output timing.rpt] --routes [file join $output route-status.rpt] --mhz 125]
set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
set wns [get_property SLACK $setup]
set whs [get_property SLACK $hold]
if {$wns<=0 || $whs<=0} {error "Positive routed setup and hold required"}
write_checkpoint [file join $output system_wrapper_qualified.dcp]
file mkdir $bitdir
write_bitstream [file join $bitdir system_wrapper.bit]
write_hw_platform -fixed -include_bit -force [file join $build sysone_v2_kr260.xsa]
set profile [open [file join $build runtime-clock.json] w]
puts $profile [format {{"clock_requested_hz":125000000,"clock_timing_max_hz":125000000,"timing_qualified":true,"routed_setup_slack_ns":%s,"routed_hold_slack_ns":%s,"candidate":"dot7-large"}} $wns $whs]
close $profile
set result [open [file join $output result.json] w]
puts $result [format {{"qualified_mhz":125,"setup_slack_ns":%s,"hold_slack_ns":%s,"routing_repeated":false,"exported":true}} $wns $whs]
close $result
close_design
