# Compare focused modules, never place/route the complete encoder.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set scope [lindex $argv 0]
set candidate [lindex $argv 1]
if {$candidate eq ""} {set candidate dot6}
if {$candidate ni {dot6 dot7}} {error "Unknown focused candidate"}
if {$scope ni {arithmetic attention}} { error "Choose arithmetic or attention" }
set output [file join $repo build v2 ${candidate}-${scope}-ooc]
if {[file exists $output]} { error "Preserve existing OOC evidence; choose a fresh candidate" }
file mkdir $output
set snapshot [file join $output rtl-snapshot]
file mkdir $snapshot
foreach item {encoder/encoder_pkg.sv encoder/add_skip_engine.sv encoder/mac_array.sv encoder/attention_engine.sv common/sequential_divider.sv} {
    file copy [file join $repo rtl v2 $item] [file join $snapshot [file tail $item]]
}
set out [open [file join $output result.json] w]
puts $out "\["
set separator ""
if {$scope eq "arithmetic"} {
    set cases {{residual-old add_skip_engine old} {residual-new add_skip_engine new} {dot-old dot16_pipeline old} {dot-new dot16_pipeline new}}
    if {$candidate eq "dot7"} {set cases {{residual-old add_skip_engine old} {residual-new add_skip_engine new}}}
} else {
    set cases {{attention-ff attention_engine 1} {attention-ram attention_engine 2}}
    if {$candidate eq "dot7"} {set cases {{attention-dual attention_engine 2} {attention-shared attention_engine 3}}}
}
foreach item $cases {
    lassign $item name top profile
    set started [clock milliseconds]
    set source $snapshot
    if {$profile eq "old"} {set source [file join $repo build v2 kr260-opt-dot5-large rtl-snapshot encoder]}
    if {$profile eq "old" && $candidate eq "dot7"} {set source [file join $repo build v2 kr260-opt-dot6-large rtl-snapshot encoder]}
    read_verilog -sv [file join $snapshot encoder_pkg.sv]
    if {$top eq "attention_engine"} {
        read_verilog -sv [file join $snapshot sequential_divider.sv]
        read_verilog -sv [file join $snapshot mac_array.sv]
        read_verilog -sv [file join $snapshot attention_engine.sv]
        # Four lanes isolate the bank inference/area question cheaply. Full
        # 32-lane physical congestion still needs a later complete-design gate.
        set generics [list LANES=4 READ_LATENCY=4 MAC_LATENCY=2 PIPELINED_DOT=1 LOCAL_QUERY_REGISTERS=1 LOCAL_ACCUMULATOR_CONTROLS=$profile EXP_TABLE_IN_BRAM=1 MAX_HEAD_DIM=64]
    } elseif {$top eq "add_skip_engine"} {
        read_verilog -sv [file join $source add_skip_engine.sv]
        set generics {READ_LATENCY=4}
    } else {
        read_verilog -sv [file join $source mac_array.sv]
        set generics {LANES=32 WIDTH=24}
    }
    synth_design -mode out_of_context -top $top -part xck26-sfvc784-2LV-c -generic $generics
    create_clock -name clk -period 3.333 [get_ports clk]
    if {[llength [get_ports -quiet reset]]} {set_false_path -from [get_ports reset]}
    report_utilization -file [file join $output ${name}-utilization.rpt]
    report_timing_summary -file [file join $output ${name}-timing.rpt]
    write_checkpoint [file join $output ${name}.dcp]
    set lut [llength [get_cells -hier -filter {REF_NAME =~ LUT*}]]
    set ff [llength [get_cells -hier -filter {REF_NAME =~ FD*}]]
    set ram [llength [get_cells -hier -filter {REF_NAME =~ RAM* && REF_NAME !~ RAMB*}]]
    set dsp [llength [get_cells -hier -filter {REF_NAME =~ DSP*}]]
    set bram [llength [get_cells -hier -filter {REF_NAME =~ RAMB*}]]
    set elapsed [expr {([clock milliseconds]-$started)/1000.0}]
    set lanes [expr {$top eq "attention_engine" ? 4 : ($top eq "dot16_pipeline" ? 32 : 0)}]
    puts $out [format {%s{"case":"%s","lanes":%d,"lut_primitives":%d,"ff":%d,"distributed_ram_primitives":%d,"dsp":%d,"bram_primitives":%d,"wall_seconds":%.3f,"routed":false}} $separator $name $lanes $lut $ff $ram $dsp $bram $elapsed]
    flush $out
    set separator ","
    close_design
    # Recreate an empty in-memory project so the next profile cannot reuse sources.
    close_project
    create_project -in_memory -part xck26-sfvc784-2LV-c
}
puts $out "\]"
close $out
puts "PASS: focused $scope comparison complete; OOC is not routed qualification"
