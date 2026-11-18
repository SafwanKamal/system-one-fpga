# Inspect the clock definitions actually stored in the custom encoder's OOC DCP.
# Run after placement finishes, to avoid competing for memory with implementation.
set_param general.maxThreads 2
set root S:/build/v2/typed200-flush-physical-v1
set out [file join $root encoder-ooc-clock-audit]
if {[file exists $out]} {error "Preserve previous clock audit"}
file mkdir $out
open_checkpoint [file join $root sysone_v2_kr260.runs system_encoder_0_synth_1 system_encoder_0.dcp]
set f [open [file join $out clocks.txt] w]
set clocks [get_clocks -quiet *]
puts $f "Stored OOC clocks: [llength $clocks]"
foreach c $clocks {puts $f "$c period [get_property PERIOD $c]"}
close $f
if {[llength $clocks]>0} {
    report_clocks -file [file join $out clocks.rpt]
} else {
    set f [open [file join $out clocks.rpt] w]
    puts $f "Native get_clocks query found zero clocks in the encoder OOC checkpoint."
    close $f
}
close_design
