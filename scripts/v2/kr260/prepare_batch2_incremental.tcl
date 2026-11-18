# Configure reuse only after reviewing preflight; never launch implementation.
# Vivado project-mode INCREMENTAL_CHECKPOINT reuses prior placement/routing.
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-batch2]
set reference [file join $repo build v2 kr260-opt-memory sysone_v2_kr260.runs impl_1 system_wrapper_routed.dcp]
if {![file exists [file join $build preflight-summary.json]]} { error "Passing preflight summary required" }
if {![file exists $reference]} { error "Verified UltraRAM routed reference missing" }
open_project [file join $build sysone_v2_kr260.xpr]
if {[get_property PROGRESS [get_runs synth_1]] ne "100%" || [get_property NEEDS_REFRESH [get_runs synth_1]]} {
    error "Completed current synthesis required"
}
set run [get_runs impl_1]
if {[get_property PROGRESS $run] ne "0%"} { error "Configure reuse before starting implementation" }
set_property AUTO_INCREMENTAL_CHECKPOINT 0 $run
set_property INCREMENTAL_CHECKPOINT $reference $run
if {[lsearch -exact [list_property $run] INCREMENTAL_CHECKPOINT.DIRECTIVE] >= 0} {
    set_property INCREMENTAL_CHECKPOINT.DIRECTIVE RuntimeOptimized $run
}
set output [open [file join $build incremental-reference.txt] w]
puts $output "Reference: $reference"
puts $output "Incremental implementation configured; no placement or routing launched."
puts $output "Reuse and actual turnaround must be measured on the next qualified run."
close $output
close_project
