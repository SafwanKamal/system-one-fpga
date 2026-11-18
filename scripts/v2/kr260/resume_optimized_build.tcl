# Resume an isolated candidate after an infrastructure failure, retaining good
# synthesis checkpoints. Invoke through a short subst path on Windows.
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt]
open_project [file join $build sysone_v2_kr260.xpr]
foreach run [get_runs] {
    set status [get_property STATUS $run]
    puts "RUN $run: $status; directory [get_property DIRECTORY $run]"
    if {[string match -nocase *error* $status]} { reset_run $run }
}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation incomplete" }
open_run impl_1
report_utilization -file [file join $build utilization.rpt]
report_timing_summary -warn_on_violation -file [file join $build timing.rpt]
foreach delay {max min} {
    set path [get_timing_paths -quiet -delay_type $delay -max_paths 1]
    if {[llength $path] != 1 || [get_property SLACK $path] < 0} {
        error "Candidate fails $delay timing; no validated export produced"
    }
}
write_hw_platform -fixed -include_bit -force [file join $build sysone_v2_kr260.xsa]
set profile [open [file join $build runtime-clock.json] w]
puts $profile {{"clock_requested_hz": 125000000, "clock_timing_max_hz": 125000000}}
close $profile
close_project
