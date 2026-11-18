set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 embed-dsp-ooc]
open_checkpoint [file join $output synthesized-1.dcp]
set cells [get_cells -hier -filter {REF_NAME == DSP48E2}]
if {[llength $cells]!=2} {error "Expected two address DSPs"}
set f [open [file join $output dsp-complete.txt] w]
foreach cell $cells {
    puts $f "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] CREG=[get_property CREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"
}
close $f
close_design
