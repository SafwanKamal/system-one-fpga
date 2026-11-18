# Read-only inspection of the isolated placed checkpoint. No implementation commands.
set_param general.maxThreads 4
set root S:/build/v2/typed200-flush-physical-v1
set out [file join $root placement-audit]
if {[file exists $out]} {error "Preserve previous audit"}
file mkdir $out
open_checkpoint [file join $root place placed.dcp]
report_clocks -file [file join $out clocks.rpt]
report_utilization -hierarchical -hierarchical_depth 4 -file [file join $out hierarchy.rpt]
report_exceptions -coverage -file [file join $out exceptions.rpt]
file copy [file join $root place methodology.rpt] [file join $out methodology.rpt]
set f [open [file join $out retention.txt] w]
foreach pattern {*epoch_inst* *publication_inst* *deployment_permit*} {
    set cells [get_cells -hier -filter "NAME =~ $pattern"]
    puts $f "$pattern cells [llength $cells]"
    if {[llength $cells]==0} {error "Missing retained $pattern"}
}
foreach pattern {*deployment_ready* *gpio_io_o*} {
    foreach n [get_nets -hier -filter "NAME =~ $pattern"] {
        puts $f "NET $n"
        puts $f "PINS [get_pins -of_objects $n]"
    }
}
close $f
close_design
