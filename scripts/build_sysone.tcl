# Vivado non-project build for the System One classifier.
#
# From the repository root, in a Vivado 2025.x shell:
#   vivado -mode batch -source scripts/build_sysone.tcl                 (board: sysone_top, 50 MHz, bitstream)
#   vivado -mode batch -source scripts/build_sysone.tcl -tclargs core   (sysone_core alone, out of context, 100 MHz)
#
# Reports land in build/<target>/. The ones that answer the open questions:
#   utilization_*.rpt       block RAM (target: about 130 of 135 RAMB36), DSP, LUT, FF
#   ram_utilization.rpt     whether W1 went to LUTRAM (ROM_STYLE = "distributed")
#   timing_summary.rpt      WNS; core at 100 MHz, board at 50 MHz

set repo_dir [file normalize [file join [file dirname [info script]] ..]]
set part xc7a100tcsg324-1
set target [expr {[llength $argv] > 0 ? [lindex $argv 0] : "top"}]
set build_dir [file join $repo_dir build $target]
file mkdir $build_dir

set core_files {
    feature_hash_pipeline.sv
    feature_generator.sv
    embedding_bag.sv
    dense_engine.sv
    channel_requantizer.sv
    logit_argmax.sv
    classifier_head.sv
    sysone_core.sv
}

set ethernet_files {
    ethernet_CRC32.sv
    rmii_RX.sv
    ethernet_RX.sv
    ethernet_RX_buffer.sv
    sysone_request_parser.sv
    sysone_result_packet.sv
    rmii_TX.sv
    ethernet_TX.sv
    ethernet_TX_buffer.sv
    sysone_ethernet_core.sv
    sysone_top.sv
}

set rtl_dir [file join $repo_dir rtl]
set sources {}
foreach f $core_files { lappend sources [file join $rtl_dir $f] }

if {$target eq "top"} {
    foreach f $ethernet_files { lappend sources [file join $rtl_dir $f] }
}

read_verilog -sv $sources

# $readmemh in the RTL uses bare file names; read_mem makes them visible to synthesis
read_mem [glob [file join $repo_dir memory *.mem]]

if {$target eq "top"} {
    read_xdc [list [file join $repo_dir constraints sysone_top.xdc]]
    synth_design -top sysone_top -part $part -include_dirs [list $rtl_dir]
} elseif {$target eq "core"} {
    synth_design -top sysone_core -part $part -include_dirs [list $rtl_dir] -mode out_of_context
    create_clock -name clk -period 10.000 [get_ports clk]
} else {
    error "unknown target '$target': use top or core"
}

write_checkpoint -force [file join $build_dir post_synth.dcp]
report_utilization -file [file join $build_dir utilization_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 4 -file [file join $build_dir utilization_hierarchy.rpt]
report_ram_utilization -file [file join $build_dir ram_utilization.rpt]

opt_design
place_design
phys_opt_design
route_design

write_checkpoint -force [file join $build_dir post_route.dcp]
report_utilization -file [file join $build_dir utilization_route.rpt]
report_timing_summary -max_paths 20 -file [file join $build_dir timing_summary.rpt]

if {$target eq "top"} {
    write_bitstream -force [file join $build_dir sysone_top.bit]
}

puts "Reports in $build_dir"
