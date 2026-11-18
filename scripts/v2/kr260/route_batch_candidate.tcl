# Resume the frozen, synthesis-qualified project; never recreate its sources.
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-batch]
open_project [file join $build sysone_v2_kr260.xpr]
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Completed synthesis required" }
if {[get_property NEEDS_REFRESH [get_runs synth_1]]} { error "Synthesis is stale" }
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation failed" }
open_run impl_1
report_utilization -file [file join $build utilization.rpt]
report_timing_summary -warn_on_violation -file [file join $build timing.rpt]
set meets_timing 1
foreach delay {max min} {
    set path [get_timing_paths -quiet -delay_type $delay -max_paths 1]
    if {[llength $path] == 0 || [get_property SLACK $path] < 0} { set meets_timing 0 }
}
if {$meets_timing} {
    write_hw_platform -fixed -include_bit -force [file join $build sysone_v2_kr260.xsa]
    set output [open [file join $build runtime-clock.json] w]
    puts $output {"clock_requested_hz": 125000000, "clock_timing_max_hz": 125000000}
    close $output
} else {
    puts "125 MHz timing failed; no hardware export. Clock sweep required."
}
close_project
