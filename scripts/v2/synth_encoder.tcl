# Out-of-context implementation of the v2 encoder datapath (rtl/v2/encoder), to see
# whether it fits the Nexys 4 DDR's xc7a100t and at what clock, before it goes into a
# board top. Synthesis, placement and routing of `encoder_layer` alone, no pins.
#
#   vivado -mode batch -source scripts/v2/synth_encoder.tcl                     # both, 75 MHz
#   vivado -mode batch -source scripts/v2/synth_encoder.tcl -tclargs minilm 10.0
#
# Configurations (first argument):
#   both       MAX_HIDDEN 384, MAX_HEAD_DIM 64: runs the bert-mini and MiniLM-L6 images
#   minilm     MAX_HIDDEN 384, MAX_HEAD_DIM 32: MiniLM-L6 only
#   bert-mini  MAX_HIDDEN 256, MAX_HEAD_DIM 64: bert-mini only
# Second argument: clock period in ns (default 13.333 = the MIG's 75 MHz ui_clk).
# All configurations: MAX_TOKENS 128, 16 x 12 multiplier array.
#
# Writes build/v2/encoder_ooc/<config>/: utilization.txt (flat and hierarchical),
# timing_summary.txt, timing_groups.txt (failing paths by block), the routed
# checkpoint, and summary.txt with the headline numbers.
# The tool's numbers are estimates for this block alone; the MIG, the Ethernet link
# and the clocking come on top in the real design (~3-5 BRAM tiles, a few k LUTs).
#
# Every path goes through [list ...] or a quoted variable, because the repository may
# sit under a folder whose name contains spaces.

set repo_dir [file normalize [file join [file dirname [info script]] .. ..]]
set part xc7a100tcsg324-1
set config [expr {[llength $argv] > 0 ? [lindex $argv 0] : "both"}]
set period [expr {[llength $argv] > 1 ? [lindex $argv 1] : 13.333}]

set configs [dict create \
    both      [list MAX_HIDDEN=384 MAX_HEAD_DIM=64] \
    minilm    [list MAX_HIDDEN=384 MAX_HEAD_DIM=32] \
    bert-mini [list MAX_HIDDEN=256 MAX_HEAD_DIM=64]]
if {![dict exists $configs $config]} {
    error "unknown configuration '$config' (both, minilm, bert-mini)"
}
set generics [concat [dict get $configs $config] [list MAX_TOKENS=128 TILE_OUT=12]]

set out_dir [file join $repo_dir build v2 encoder_ooc $config]
file mkdir $out_dir

set rtl_dir [file join $repo_dir rtl v2]
set sources [list \
    [file join $rtl_dir common sequential_divider.sv] \
    [file join $rtl_dir encoder encoder_pkg.sv] \
    [file join $rtl_dir encoder activation_buffer.sv] \
    [file join $rtl_dir encoder mac_array.sv] \
    [file join $rtl_dir encoder linear_engine.sv] \
    [file join $rtl_dir encoder attention_engine.sv] \
    [file join $rtl_dir encoder add_skip_engine.sv] \
    [file join $rtl_dir encoder layernorm_engine.sv] \
    [file join $rtl_dir encoder encoder_layer.sv]]
foreach f $sources {
    read_verilog -sv [list $f]
}

set generic_args {}
foreach g $generics {
    lappend generic_args -generic $g
}

synth_design -top encoder_layer -part $part -mode out_of_context \
    -flatten_hierarchy rebuilt -retiming {*}$generic_args

create_clock -name clk -period $period [get_ports clk]

report_utilization -file [file join $out_dir utilization_synth.txt]
report_utilization -hierarchical -hierarchical_depth 3 -file [file join $out_dir utilization_synth_hierarchical.txt]

# placement refuses an over-full design; keep the synthesis numbers in that case
set stage "routed"
if {[catch {opt_design; place_design; phys_opt_design; route_design} err]} {
    puts "implementation stopped: $err"
    set stage "synthesis only (implementation failed, see utilization_synth*.txt)"
}

report_utilization -file [file join $out_dir utilization.txt]
report_utilization -hierarchical -hierarchical_depth 3 -file [file join $out_dir utilization_hierarchical.txt]
report_timing_summary -max_paths 20 -file [file join $out_dir timing_summary.txt]

# every failing setup path, grouped by the block it starts in and the block it ends
# in (first level of hierarchy), with the worst one of each group
proc block_of {pin} {
    set name [get_property NAME $pin]
    set first [lindex [split $name /] 0]
    return [expr {[string match *_inst* $first] || [string match gen_* $first] ? $first : "(top)"}]
}
set groups [dict create]
foreach path [get_timing_paths -setup -max_paths 20000 -nworst 1 -slack_lesser_than 0] {
    set key "[block_of [get_property STARTPOINT_PIN $path]] -> [block_of [get_property ENDPOINT_PIN $path]]"
    set slack [get_property SLACK $path]
    if {![dict exists $groups $key]} {
        dict set groups $key [list 0 $slack "" "" 0]
    }
    lassign [dict get $groups $key] count worst start end levels
    incr count
    if {$slack <= $worst} {
        set worst $slack
        set start [get_property NAME [get_property STARTPOINT_PIN $path]]
        set end [get_property NAME [get_property ENDPOINT_PIN $path]]
        set levels [get_property LOGIC_LEVELS $path]
    }
    dict set groups $key [list $count $worst $start $end $levels]
}
set fh [open [file join $out_dir timing_groups.txt] w]
puts $fh "failing setup endpoints by start block -> end block (count, worst slack ns, logic levels, worst path)"
foreach key [lsort [dict keys $groups]] {
    lassign [dict get $groups $key] count worst start end levels
    puts $fh [format "%-50s %6d %9.3f %3d  %s -> %s" $key $count $worst $levels $start $end]
}
close $fh
if {$stage eq "routed"} {
    write_checkpoint -force [file join $out_dir encoder_layer_routed.dcp]
}

# headline numbers: the rows of report_utilization that decide whether it fits
set util [report_utilization -return_string]
set rows {}
foreach key {"Slice LUTs" "LUT as Memory" "Slice Registers" "Block RAM Tile" "DSPs"} {
    foreach line [split $util "\n"] {
        if {[string match "| $key*" $line]} {
            lappend rows [string trim $line]
            break
        }
    }
}
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]

set summary [join [concat \
    [list "encoder_layer out of context, $config ($generics), $part, period $period ns: $stage" \
          "| Site Type | Used | Fixed | Prohibited | Available | Util% |"] \
    $rows \
    [list "WNS $wns ns, WHS $whs ns (meaningful only when routed)" \
          "details: utilization*.txt, timing_summary.txt"]] "\n"]
set fh [open [file join $out_dir summary.txt] w]
puts $fh $summary
close $fh
puts "\n$summary\n"
