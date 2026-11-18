# Linux bring-up fallback: retain the routed placement, check an 80 MHz ceiling,
# and request 75 MHz through the runtime overlay. The base PS preset stays at
# 100 MHz; Ubuntu's clock driver, not XSA PS initialization, owns the live rate.
# No physical connections or RTL are changed. Never use this to bypass hold DRC.
# For a completed optimized candidate: -tclargs optimized <ceiling MHz> <request MHz>.
set repo_dir [file normalize [file join [file dirname [info script]] .. .. ..]]
set build_dir [file join $repo_dir build v2 kr260]
set optimized [expr {[llength $argv] > 0 && [lindex $argv 0] eq "optimized"}]
set ceiling_mhz 80
set requested_mhz 75
if {$optimized} {
    set build_dir [file join $repo_dir build v2 kr260-opt]
    if {[llength $argv] ni {3 4 5}} { error "optimized requires ceiling MHz, requested MHz and optional bram/wide" }
    if {[llength $argv] >= 4} {
        if {[lindex $argv 3] ne "bram"} { error "Unknown runtime variant" }
        set build_dir [file join $repo_dir build v2 kr260-opt-bram]
    }
    if {[llength $argv] == 5} {
        if {[lindex $argv 4] ne "wide"} { error "Unknown runtime variant" }
        set build_dir [file join $repo_dir build v2 kr260-opt-wide]
    }
    set ceiling_mhz [lindex $argv 1]
    set requested_mhz [lindex $argv 2]
    foreach value [list $ceiling_mhz $requested_mhz] {
        if {![string is double -strict $value] || $value <= 0} { error "Positive MHz required" }
    }
    if {$requested_mhz > $ceiling_mhz} { error "Requested clock exceeds timing ceiling" }
}
open_project [file join $build_dir sysone_v2_kr260.xpr]
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "A completed routed implementation is required"
}
open_run impl_1
set original [file join $build_dir [expr {$optimized ? "timing-before-runtime.rpt" : "timing-100mhz.rpt"}]]
report_timing_summary -file $original
foreach name {clk_pl_0 clk_pl_1} {
    set clock [get_clocks -quiet $name]
    if {[llength $clock] != 1} { error "Missing primary clock $name" }
    set sources [get_property SOURCE_PINS $clock]
    if {[llength $sources] != 1} { error "Unexpected source for $name: $sources" }
    create_clock -name $name -period [expr {1000.0 / $ceiling_mhz}] [get_pins $sources]
}
report_timing_summary -warn_on_violation -file [file join $build_dir timing.rpt]
report_utilization -file [file join $build_dir utilization.rpt]
report_route_status -file [file join $build_dir route-status.rpt]
foreach delay {max min} {
    set path [get_timing_paths -quiet -delay_type $delay -max_paths 1]
    if {[llength $path] == 0 || [get_property SLACK $path] < 0} {
        error "Runtime-clock validation fails $delay timing; no export produced"
    }
}
write_checkpoint -force [file join $build_dir runtime-clock-${ceiling_mhz}mhz.dcp]
set bit [file join $build_dir sysone_v2_kr260.runs impl_1 system_wrapper.bit]
set backup [file join $build_dir [expr {$optimized ? "system_wrapper-before-runtime.bit" : "system_wrapper-100mhz.bit"}]]
if {![file exists $backup]} { file copy $bit $backup }
write_bitstream -force $bit
write_hw_platform -fixed -include_bit -force [file join $build_dir sysone_v2_kr260.xsa]
set profile [open [file join $build_dir runtime-clock.json] w]
puts $profile "{\"clock_requested_hz\": [expr {int($requested_mhz * 1000000)}], \"clock_timing_max_hz\": [expr {int($ceiling_mhz * 1000000)}]}"
close $profile
puts "Linux runtime export checked at $ceiling_mhz MHz; overlay must request $requested_mhz MHz"
close_project
