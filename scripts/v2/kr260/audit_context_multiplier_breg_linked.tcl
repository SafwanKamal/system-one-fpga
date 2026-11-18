set_param general.maxThreads 2
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 kr260-opt-attention-context-capture-large]
foreach mode {previous current} {
 if {$mode eq "previous"} {set checkpoint [file join $repo build v2 kr260-opt-request-window-embed-large sysone_v2_kr260.runs synth_1 system_wrapper.dcp]} else {set checkpoint [file join $output sysone_v2_kr260.runs synth_1 system_wrapper.dcp]}
 open_project [file join [file dirname [file dirname [file dirname $checkpoint]]] sysone_v2_kr260.xpr]
 open_run synth_1
 set out [open [file join $output context-b-linked-$mode.txt] w]
 foreach cell [get_cells -hier -filter {NAME =~ *attention_inst*w_product_reg* && REF_NAME == DSP48E2}] {
  puts $out "$cell AREG=[get_property AREG $cell] BREG=[get_property BREG $cell] MREG=[get_property MREG $cell] PREG=[get_property PREG $cell]"
  foreach name {B CEB1 CEB2 RSTB} {
   set pins [get_pins -of_objects $cell -filter "REF_PIN_NAME =~ ${name}*"]
   foreach pin $pins {
    set nets [get_nets -of_objects $pin]
    set drivers [get_pins -leaf -of_objects $nets -filter {DIRECTION == OUT}]
    puts $out "$pin NET=$nets DRIVER=$drivers"
   }
  }
 }
 close $out
 close_project
}
