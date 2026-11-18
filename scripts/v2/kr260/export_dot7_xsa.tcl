# Export the qualified checkpoint from a space-free temporary working directory.
# No synthesis, placement or routing. Preserve the previously generated bitstream.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-dot7-large]
set output [file join $build route-125mhz xsa-export]
cd $output
if {[string first " " [pwd]]>=0} {error "XSA export temporary directory must not contain spaces"}
open_checkpoint [file join $build route-125mhz export-recovery-2 system_wrapper_qualified.dcp]
puts [exec [file join $repo .venv Scripts python.exe] -I [file join $repo scripts v2 kr260 check_routed_evidence.py] --timing [file join $build route-125mhz export-recovery-2 timing.rpt] --routes [file join $build route-125mhz export-recovery-2 route-status.rpt] --mhz 125]
write_hw_platform -fixed -include_bit -force [file join $build sysone_v2_kr260.xsa]
set profile [open [file join $build runtime-clock.json] w]
puts $profile {{"clock_requested_hz":125000000,"clock_timing_max_hz":125000000,"timing_qualified":true,"routed_setup_slack_ns":0.401,"routed_hold_slack_ns":0.010,"candidate":"dot7-large"}}
close $profile
close_design
