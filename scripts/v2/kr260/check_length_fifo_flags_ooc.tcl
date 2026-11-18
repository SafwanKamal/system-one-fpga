# Inspect the measured FIFO-pointer -> request-ready cone without a full build.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 axi-length-flags-probe]
if {[file exists [file join $output result.json]]} {error "Preserve existing OOC evidence"}
cd $output
set source [file join $output sources]
set result [open [file join $output result.json] w]
puts $result "\["
set separator ""
foreach profile {original flags} {
    set started [clock milliseconds]
    create_project -in_memory -part xck26-sfvc784-2LV-c
    read_verilog -sv [file join $source sync_fifo.sv]
    read_verilog -sv [file join $source sync_fifo_registered_flags.sv]
    read_verilog -sv [file join $source axi_memory_port-${profile}.sv]
    synth_design -mode out_of_context -top axi_memory_port -part xck26-sfvc784-2LV-c -generic REGISTERED_REQUESTS=1
    create_clock -name clk -period 5.000 [get_ports clk]
    set_input_delay 0 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk && NAME != reset}]
    set_output_delay 0 -clock clk [all_outputs]
    set_false_path -from [get_ports reset]
    set pointers [get_cells -hier -filter {NAME =~ *length_queue_inst* && IS_SEQUENTIAL == 1 && (NAME =~ *read_pointer_reg* || NAME =~ *rp_reg*)}]
    if {[llength $pointers]==0} {error "Missing length FIFO read pointers"}
    set paths [get_timing_paths -quiet -from $pointers -to [get_ports read_request_ready] -max_paths 1]
    set count [llength $paths]
    report_timing -to [get_ports read_request_ready] -max_paths 10 -file [file join $output ${profile}-ready.rpt]
    report_timing_summary -file [file join $output ${profile}-timing.rpt]
    report_utilization -file [file join $output ${profile}-utilization.rpt]
    write_checkpoint [file join $output ${profile}.dcp]
    set ff [llength [get_cells -hier -filter {REF_NAME =~ FD*}]]
    set lut [llength [get_cells -hier -filter {REF_NAME =~ LUT*}]]
    puts $result [format {%s{"profile":"%s","pointer_to_request_ready_paths":%d,"ff":%d,"lut_primitives":%d,"wall_seconds":%.3f,"routed":false}} $separator $profile $count $ff $lut [expr {([clock milliseconds]-$started)/1000.0}]]
    flush $result
    if {$profile eq "original" && $count!=1} {error "Baseline measured cone not reproduced"}
    if {$profile eq "flags" && $count!=0} {error "Registered flags did not break measured cone"}
    set separator ","
    close_project
}
puts $result "\]"
close $result
puts "PASS: registered flags break length FIFO pointer -> request-ready cone; not full timing closure"
