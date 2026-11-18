# Report mapped control and clocked designs at the same 5ns analysis period.
# Creating a clock after synthesis on the CONTROL is analysis only.
set_param general.maxThreads 2
set root S:/build/v2/typed200-synthesis-clock-v3
foreach mode {control clocked} {
    set output [file join $root ${mode}-analysis]
    if {[file exists $output]} {error "Preserve previous analysis"}
    file mkdir $output
    open_checkpoint [file join $root $mode encoder.dcp]
    if {$mode eq "control"} {
        if {[llength [get_clocks -quiet *]] != 0} {error "Control was not unconstrained"}
        create_clock -name analysis_only_200 -period 5.000 [get_ports clk]
    } else {
        if {[llength [get_clocks -quiet encoder_ooc_200]] != 1} {error "Missing synthesis clock"}
    }
    report_clocks -file [file join $output clocks.rpt]
    report_timing_summary -report_unconstrained -file [file join $output timing.rpt]
    report_timing -delay_type max -max_paths 30 -input_pins -file [file join $output critical.rpt]
    report_utilization -file [file join $output utilization.rpt]
    check_timing -verbose -file [file join $output check-timing.rpt]
    set f [open [file join $output timing.json] w]
    puts $f [format {{"setup_ns":%s,"hold_ns":%s,"period_ns":5.000,"routed":false,"hardware_qualified":false}} [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]]
    close $f
    close_design
}
