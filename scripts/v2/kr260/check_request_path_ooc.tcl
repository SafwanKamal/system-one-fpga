# Cheap structural timing gate: compare only the AXI port, not the full encoder.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 axi-request-register-ooc]
if {[file exists [file join $output result.json]]} { error "Existing OOC evidence must be reviewed" }
set snapshot [file join $output rtl-snapshot]
file mkdir $snapshot
foreach source {common/sync_fifo.sv platform/kr260/axi_memory_port.sv} {
    set target [file join $snapshot [file tail $source]]
    file copy -force [file join $repo rtl v2 $source] $target
    read_verilog -sv $target
}
set out [open [file join $output result.json] w]
puts $out "\["
set separator ""
foreach registered {0 1} {
    set started [clock milliseconds]
    synth_design -mode out_of_context -top axi_memory_port -part xck26-sfvc784-2LV-c -generic REGISTERED_REQUESTS=$registered
    create_clock -name clk -period 3.333 [get_ports clk]
    set_input_delay 0 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk && NAME != reset}]
    set_output_delay 0 -clock clk [all_outputs]
    set_false_path -from [get_ports reset]
    report_utilization -file [file join $output utilization-${registered}.rpt]
    report_timing_summary -file [file join $output timing-${registered}.rpt]
    set path [get_timing_paths -quiet -from [get_ports read_request_valid] -to [get_ports write_request_ready] -max_paths 1]
    set count [llength $path]
    if {$registered == 0 && $count != 1} { error "Expected direct-mode combinational path missing; review test setup" }
    if {$registered == 1 && $count != 0} { error "Registered requests still have combinational valid-to-write-ready path" }
    if {$count} {
        report_timing -from [get_ports read_request_valid] -to [get_ports write_request_ready] -file [file join $output direct-valid-to-ready.rpt]
    }
    set elapsed [expr {([clock milliseconds]-$started)/1000.0}]
    puts $out [format {%s{"registered_requests":%d,"combinational_valid_to_write_ready_paths":%d,"wall_seconds":%.3f,"routed":false}} $separator $registered $count $elapsed]
    set separator ","
    close_design
}
puts $out "\]"
close $out
puts "PASS: native AXI request registration cuts the synthesized valid-to-write-ready path"
