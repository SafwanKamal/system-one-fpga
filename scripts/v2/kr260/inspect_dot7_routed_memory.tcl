# Read-only primitive/topology/timing inspection; no optimization or rebuild.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-dot7-large]
set output [file join $build routed-memory-inspection]
cd $output
open_checkpoint [file join $build route-125mhz export-recovery-2 system_wrapper_qualified.dcp]
set memories [get_cells -hier -filter {REF_NAME == URAM288}]
if {[llength $memories]!=36} {error "Expected frozen 36-URAM candidate"}
set f [open [file join $output primitive-properties.rpt] w]
foreach cell $memories {
    puts $f "CELL $cell"
    foreach property [lsort [list_property $cell]] {
        if {[regexp {OREG|CAS|REG|MODE|LOC|BEL} $property]} {
            puts $f "$property=[get_property $property $cell]"
        }
    }
    puts $f ""
}
close $f
report_timing -from $memories -delay_type max -max_paths 30 -nworst 1 -input_pins -file [file join $output uram-paths.rpt]
report_high_fanout_nets -timing -load_types -max_nets 40 -file [file join $output fanout.rpt]
close_design
