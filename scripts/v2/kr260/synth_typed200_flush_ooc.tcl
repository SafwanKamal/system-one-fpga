# Isolated streamer mapping audit only; no package or device access.
set_param general.maxThreads 4
set root S:/build/v2/typed200-flush-ooc-v1
if {[file exists $root]} {error "Preserve previous attempt"}
file mkdir $root
set rtl S:/rtl/v2/candidates/typed200_flush
foreach src {common/stream_fifo_sync_clear.sv encoder/result_streamer.sv} {
    set dest [file join $root [file tail $src]]
    file copy [file join $rtl $src] $dest
    read_verilog -sv $dest
}
synth_design -top result_streamer -part xck26-sfvc784-2LV-c -mode out_of_context
create_clock -period 5.0 [get_ports clk]
write_checkpoint [file join $root synthesized.dcp]
report_utilization -file [file join $root utilization.rpt]
report_methodology -file [file join $root methodology.rpt]
set async [get_cells -hier -filter {REF_NAME == FDCE || REF_NAME == FDPE || REF_NAME == FDCP}]
set f [open [file join $root reset-mapping.txt] w]
puts $f "Asynchronous reset/preset flip-flops: [llength $async]"
puts $f "All cells: [get_cells -hier]"
close $f
if {[llength $async]!=0} {error "Asynchronous streamer reset remains"}
close_design
