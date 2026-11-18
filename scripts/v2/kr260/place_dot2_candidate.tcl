# Stop at placement for review; reuse the qualified memory candidate where possible.
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-dot2]
set reference [file join $repo build v2 kr260-opt-batch3 sysone_v2_kr260.runs impl_1 system_wrapper_placed.dcp]
open_project [file join $build sysone_v2_kr260.xpr]
if {[get_property PROGRESS [get_runs synth_1]] ne "100%" || [get_property NEEDS_REFRESH [get_runs synth_1]]} {
    error "Completed current synthesis required"
}
set run [get_runs impl_1]
if {[get_property PROGRESS $run] ne "0%"} { error "Implementation already started; review before resuming" }
if {![file exists $reference]} { error "Qualified incremental reference missing" }
set_property AUTO_INCREMENTAL_CHECKPOINT 0 $run
set_property INCREMENTAL_CHECKPOINT $reference $run
if {[lsearch -exact [list_property $run] INCREMENTAL_CHECKPOINT.DIRECTIVE] >= 0} {
    set_property INCREMENTAL_CHECKPOINT.DIRECTIVE RuntimeOptimized $run
}
set started [clock milliseconds]
launch_runs impl_1 -to_step place_design -jobs 1
wait_on_run impl_1
set placed [file join $build sysone_v2_kr260.runs impl_1 system_wrapper_placed.dcp]
if {![file exists $placed] || [string match -nocase "*error*" [get_property STATUS $run]] || [get_property NEEDS_REFRESH $run]} {
    error "Placement incomplete: [get_property STATUS $run]"
}
set elapsed [expr {([clock milliseconds] - $started) / 1000.0}]
source [file join $repo scripts v2 kr260 report_dot2_placement.tcl]
set output [open [file join $build placement-result.json] w]
puts $output [format {{"optimization_and_placement_wall_seconds": %.3f, "routing_started": false, "incremental_reference": "kr260-opt-batch3 placed"}} $elapsed]
close $output
