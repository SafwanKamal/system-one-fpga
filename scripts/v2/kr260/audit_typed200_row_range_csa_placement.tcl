# Read-only inspection of the isolated placed checkpoint. No implementation commands.
set_param general.maxThreads 4
if {[llength $argv] != 1} {error "Expected new timing experiment build name"}
set name [lindex $argv 0]
if {![regexp {^typed200-(row-range-csa)-physical-v[0-9]+$} $name]} {error "Unexpected experiment name"}
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
set flags [get_cells -quiet -hier -filter {NAME =~ *profile_byte_equal_reg*}]
set f [open [file join $out profile-cache-mapping.txt] w]
puts $f "Mapped profile flag cells: [llength $flags]"
foreach c $flags {puts $f "$c [get_property REF_NAME $c]"}
set raw 0
foreach c [get_cells -quiet -hier -filter {NAME =~ *publication_inst*bank_reg*}] {
    if {[regexp {bank_reg\[(6|7|8|9|10|11|12|13)\]} $c]} {incr raw;puts $f "RAW $c [get_property REF_NAME $c]"}
}
puts $f "Retained raw request-profile bank cells: $raw"
close $f
if {[llength $flags]<32} {error "Expected all32 byte-equality registers"}
set flag_q [get_pins -of_objects $flags -filter {REF_PIN_NAME == Q}]
if {[llength $flag_q]<32} {error "Missing flag register Q pins"}
report_timing -from $flag_q -delay_type max -max_paths 10 -input_pins -file [file join $out profile-cache-paths.rpt]
set f [open [file join $out reopened-timing.json] w]
puts $f [format {{"setup_ns":%s,"hold_ns":%s}} [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]]
close $f
set skip_regs [get_cells -quiet -hier -filter {NAME =~ *add_skip_inst/skip_clamped_reg* && REF_NAME =~ FD*}]
if {[llength $skip_regs] != 128} {error "Expected128 clamped stage registers"}
report_timing -to $skip_regs -delay_type max -max_paths 10 -input_pins -file [file join $out rounding-stage-paths.rpt]
set skip_pins [get_pins -of_objects $skip_regs -filter {REF_PIN_NAME == Q}]
report_timing -from $skip_pins -delay_type max -max_paths 10 -input_pins -file [file join $out output-stage-paths.rpt]
set bias_regs [get_cells -quiet -hier -filter {NAME =~ *encoder_inst/add_round_bias_reg* && REF_NAME =~ FD*}]
if {[llength $bias_regs]==0} {error "Missing captured rounding bias registers"}
report_timing -to $bias_regs -delay_type max -max_paths 10 -input_pins -file [file join $out predecode-paths.rpt]
set product_regs [get_cells -quiet -hier -filter {NAME =~ *add_skip_inst/product_reg* && REF_NAME =~ FD*}]
if {[llength $product_regs]==0} {error "Missing ADD_SKIP product registers"}
report_timing -to $product_regs -delay_type max -max_paths 10 -input_pins -file [file join $out product-paths.rpt]
set shape_regs [get_cells -quiet -hier -regexp {.*publication_inst/bank_reg\[(5|28)\].*}]
set shape_regs [filter $shape_regs {REF_NAME =~ FD*}]
if {[llength $shape_regs]==0} {error "Missing shape bank registers"}
report_timing -from $shape_regs -delay_type max -max_paths 20 -input_pins -file [file join $out row-range-paths.rpt]
close_design
