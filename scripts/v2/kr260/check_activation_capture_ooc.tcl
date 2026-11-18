# Focused inference comparison; deliberately no full encoder placement/route.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set output [file join $repo build v2 activation-capture-ooc]
if {[file exists $output]} {error "Preserve existing probe; choose a fresh output"}
file mkdir $output
cd $output
set snapshot [file join $output rtl-snapshot]
file mkdir $snapshot
foreach item {encoder/activation_buffer.sv common/activation_read_capture.sv common/activation_capture_probe.sv} {
    file copy [file join $repo rtl v2 $item] [file join $snapshot [file tail $item]]
}
set result [open [file join $output result.json] w]
puts $result "\["
set separator ""
foreach capture {0 1} {
    set started [clock milliseconds]
    create_project -in_memory -part xck26-sfvc784-2LV-c
    foreach item {activation_buffer.sv activation_read_capture.sv activation_capture_probe.sv} {
        read_verilog -sv [file join $snapshot $item]
    }
    synth_design -mode out_of_context -top activation_capture_probe -part xck26-sfvc784-2LV-c -generic CAPTURE=$capture
    create_clock -name clk -period 3.333 [get_ports clk]
    report_utilization -file [file join $output capture${capture}-utilization.rpt]
    report_timing_summary -file [file join $output capture${capture}-timing.rpt]
    report_timing -from [get_cells -hier -filter {REF_NAME == URAM288}] -max_paths 10 -file [file join $output capture${capture}-uram-paths.rpt]
    write_checkpoint [file join $output capture${capture}.dcp]
    set uram [llength [get_cells -hier -filter {REF_NAME == URAM288}]]
    set ff [llength [get_cells -hier -filter {REF_NAME =~ FD*}]]
    set lut [llength [get_cells -hier -filter {REF_NAME =~ LUT*}]]
    set localff [llength [get_cells -hier -filter {NAME =~ *gen_capture* && REF_NAME =~ FD*}]]
    set elapsed [expr {([clock milliseconds]-$started)/1000.0}]
    puts $result [format {%s{"capture":%d,"uram":%d,"ff":%d,"lut_primitives":%d,"local_capture_ff":%d,"wall_seconds":%.3f,"routed":false}} $separator $capture $uram $ff $lut $localff $elapsed]
    flush $result
    if {$uram != 36} {error "Expected unchanged 36 UltraRAM primitives"}
    if {$capture == 1 && $localff != 896} {error "Local physical capture was not preserved"}
    set separator ","
    close_project
}
puts $result "\]"
close $result
puts "PASS: activation capture inference comparison; not routed qualification"
