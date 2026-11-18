# Read-only inspection of the isolated placed checkpoint. No implementation commands.
set_param general.maxThreads 4
if {[llength $argv] != 1} {error "Expected new timing experiment build name"}
set name [lindex $argv 0]
if {![regexp {^typed200-(clock|observe|lut-capture|profile-tree)-physical-v[0-9]+$} $name]} {error "Unexpected experiment name"}
set root [file normalize [file join S:/build/v2 $name]]
set out [file join $root placement-audit]
if {[file exists $out]} {error "Preserve previous audit"}
file mkdir $out
open_checkpoint [file join $root place placed.dcp]
set clocks [lsort [get_clocks -quiet *]]
if {$clocks ne {clk_pl_0 clk_pl_1}} {error "Unexpected composed clocks: $clocks"}
if {[get_property PERIOD [get_clocks clk_pl_0]] != 5.000 || [get_property PERIOD [get_clocks clk_pl_1]] != 10.000} {error "Composed clock constraints changed"}
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
