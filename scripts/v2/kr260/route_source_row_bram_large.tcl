# Route the frozen placed candidate at a conservative deployment clock.
# No synthesis or placement repetition. Failed timing never exports hardware.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-source-row-bram-large]
set mhz [lindex $argv 0]
if {$mhz ne "200"} {error "This candidate must qualify the requested200MHz target"}
set output [file join $build route-${mhz}mhz]
file mkdir $output
cd $output ;# space-free S: cwd for Vivado internal XSA bit export
if {[file exists [file join $output system_wrapper_routed.dcp]]} { error "Existing routed evidence must be reviewed" }
open_checkpoint [file join $build placement system_wrapper_placed.dcp]
proc set_fabric_clocks {mhz} {
    foreach name {clk_pl_0 clk_pl_1} {
        set clock [get_clocks -quiet $name]
        if {[llength $clock]!=1} { error "Missing clock $name" }
        create_clock -name $name -period [expr {1000.0/$mhz}] [get_pins [get_property SOURCE_PINS $clock]]
    }
}
set_fabric_clocks $mhz
set started [clock milliseconds]
phys_opt_design
set phys_seconds [expr {([clock milliseconds]-$started)/1000.0}]
write_checkpoint [file join $output system_wrapper_physopt.dcp]
set started [clock milliseconds]
route_design
set route_seconds [expr {([clock milliseconds]-$started)/1000.0}]
write_checkpoint [file join $output system_wrapper_routed.dcp]
report_route_status -file [file join $output route-status.rpt]
report_utilization -file [file join $build utilization.rpt]
report_timing_summary -warn_on_violation -file [file join $output timing-requested.rpt]
set selected $mhz
set setup [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup]!=1 || [llength $hold]!=1} { error "Missing routed timing paths" }
set wns [get_property SLACK $setup]
set whs [get_property SLACK $hold]
if {$wns<=0 || $whs<=0} {
    error "200MHz routed setup/hold failed; preserve routing, no fallback/export"
}
report_timing_summary -warn_on_violation -file [file join $build timing.rpt]
# Do not infer legal routing from a nonnegative slack on a partially routed design.
set timing_handle [open [file join $build timing.rpt] r]
set final_timing [read $timing_handle]
close $timing_handle
puts [exec [file join $repo .venv Scripts python.exe] -I [file join $repo scripts v2 kr260 check_routed_evidence.py] --timing [file join $build timing.rpt] --routes [file join $output route-status.rpt] --mhz $selected]
write_checkpoint [file join $output system_wrapper_qualified.dcp]
set bitdir [file join $build sysone_v2_kr260.runs impl_1]
file mkdir $bitdir
write_bitstream [file join $bitdir system_wrapper.bit]
write_hw_platform -fixed -include_bit -force [file join $build sysone_v2_kr260.xsa]
puts [exec [file join $repo .venv Scripts python.exe] -I [file join $repo scripts v2 kr260 canonicalize_xsa_bit.py] --bit [file join $bitdir system_wrapper.bit] --xsa [file join $build sysone_v2_kr260.xsa] --report [file join $build bit-canonicalization.json]]
set profile [open [file join $build runtime-clock.json] w]
puts $profile [format {{"clock_requested_hz":%d,"clock_timing_max_hz":%d,"timing_qualified":true,"routed_setup_slack_ns":%s,"routed_hold_slack_ns":%s,"candidate":"source-row-bram-large"}} [expr {$selected*1000000}] [expr {$selected*1000000}] $wns $whs]
close $profile
set result [open [file join $output result.json] w]
puts $result [format {{"requested_mhz":%d,"qualified_mhz":%d,"setup_slack_ns":%s,"hold_slack_ns":%s,"physical_optimization_seconds":%.3f,"routing_seconds":%.3f,"exported":true}} $mhz $selected $wns $whs $phys_seconds $route_seconds]
close $result
close_design
