# KR260 (K26 SOM on the KR260 carrier): block design with the v2 encoder as a PL block.
# The established runtime uses the separately verified 80 MHz timing profile.
# The optional pipeline candidate is isolated and must pass simulation and timing
# before packaging or deployment. Preflight checks K26 device and board support.
#
#   vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl [-tclargs build]
#   vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl -tclargs build optimized 125
#   vivado -mode batch -source scripts/v2/kr260/create_project_kr260.tcl -tclargs build optimized 125 bram
#
# Needs the KR260 board files (Vivado: Tools > Vivado Store > Boards, "Kria KR260").
#   zynq_ultra_ps_e (board preset)  M_AXI_HPM0_FPD -> smartconnect -> encoder s_axil
#                                   S_AXI_HP0_FPD (128-bit) <- smartconnect <- encoder m_axi
#                                   pl_clk0 100 MHz, pl_resetn0 -> proc_sys_reset
#                                   pl_ps_irq0 <- encoder irq
#   kr260_encoder_wrapper           rtl/v2/platform/kr260 (TILE_OUT 32, DRAIN_LANES 4)
# Address map: encoder registers at 0xA000_0000 (4 KiB); the encoder reaches DDR_LOW
# (0x0000_0000 .. 0x7FFF_FFFF). Linux must leave the image region alone: add a
# reserved-memory node (no-map) for 0x6000_0000 + 64 MiB to the device tree.
# Writes build/v2/kr260/sysone_v2_kr260.xpr; with `build`, the bitstream and an .xsa.
# `optimized MHz` writes build/v2/kr260-opt with registered MAC operands.

set repo_dir [file normalize [file join [file dirname [info script]] .. .. ..]]
set project_dir [file join $repo_dir build v2 kr260]
set build [expr {[lsearch -exact $argv build] >= 0}]
set preflight [expr {[lsearch -exact $argv preflight] >= 0}]
set optimized [expr {[lsearch -exact $argv optimized] >= 0}]
set bram [expr {[lsearch -exact $argv bram] >= 0}]
set wide [expr {[lsearch -exact $argv wide] >= 0}]
set memory [expr {[lsearch -exact $argv memory] >= 0}]
set batch [expr {[lsearch -exact $argv batch] >= 0}]
set batch2 [expr {[lsearch -exact $argv batch2] >= 0}]
set batch3 [expr {[lsearch -exact $argv batch3] >= 0}]
set dot [expr {[lsearch -exact $argv dot] >= 0}]
set dot2 [expr {[lsearch -exact $argv dot2] >= 0}]
set dot3 [expr {[lsearch -exact $argv dot3] >= 0}]
set dot4 [expr {[lsearch -exact $argv dot4] >= 0}]
set dot5 [expr {[lsearch -exact $argv dot5] >= 0}]
set context_capture [expr {[lsearch -exact $argv context-capture] >= 0}]
set request_window_embed [expr {[lsearch -exact $argv request-window-embed] >= 0 || $context_capture}]
set attention16_distance [expr {[lsearch -exact $argv attention16-distance] >= 0 || $request_window_embed}]
set attention_lanes [expr {$attention16_distance ? 16 : 32}]
set source_row_bram [expr {[lsearch -exact $argv source-row-bram] >= 0 || $attention16_distance}]
set operand_capture [expr {[lsearch -exact $argv operand-capture] >= 0 || $source_row_bram}]
set pipeline_cuts [expr {[lsearch -exact $argv pipeline-cuts] >= 0 || $operand_capture}]
set capture_flags [expr {[lsearch -exact $argv capture-flags] >= 0 || $pipeline_cuts}]
set capture [expr {[lsearch -exact $argv capture] >= 0 || $capture_flags}]
set dot7 [expr {[lsearch -exact $argv dot7] >= 0 || $capture}]
if {$dot7} { set dot5 1 }
if {$dot5} { set dot4 1 }
set large [expr {[lsearch -exact $argv large] >= 0}]
if {$large && !$dot4} { error "large capacity currently requires isolated dot4 profile" }
if {$dot4} { set dot3 1 }
if {$dot3} { set dot2 1 }
if {$dot2} { set dot 1 }
if {$dot} { set batch3 1 }
if {$batch3} { set batch2 1 }
if {$batch2} { set batch 1 }
if {$batch && !$memory} { error "batch requires memory" }
if {$memory && !$wide} { error "memory requires wide" }
if {$wide && (!$optimized || !$bram)} { error "wide requires optimized and bram" }
if {$bram && !$optimized} { error "bram requires the optimized profile" }
set target_mhz 100
if {$optimized} {
    set project_dir [file join $repo_dir build v2 kr260-opt]
    if {$bram} { set project_dir [file join $repo_dir build v2 kr260-opt-bram] }
    if {$wide} { set project_dir [file join $repo_dir build v2 kr260-opt-wide] }
    if {$memory} { set project_dir [file join $repo_dir build v2 kr260-opt-memory] }
    if {$batch} { set project_dir [file join $repo_dir build v2 kr260-opt-batch] }
    if {$batch2} { set project_dir [file join $repo_dir build v2 kr260-opt-batch2] }
    if {$batch3} { set project_dir [file join $repo_dir build v2 kr260-opt-batch3] }
    if {$dot} { set project_dir [file join $repo_dir build v2 kr260-opt-dot] }
    if {$dot2} { set project_dir [file join $repo_dir build v2 kr260-opt-dot2] }
    if {$dot3} { set project_dir [file join $repo_dir build v2 kr260-opt-dot3] }
    if {$dot4} { set project_dir [file join $repo_dir build v2 kr260-opt-dot4] }
    if {$large} { set project_dir [file join $repo_dir build v2 kr260-opt-dot4-large] }
    if {$dot5} {
        set project_dir [file join $repo_dir build v2 kr260-opt-dot5]
        if {$large} { set project_dir [file join $repo_dir build v2 kr260-opt-dot5-large] }
    }
    if {$dot7} {
        set project_dir [file join $repo_dir build v2 kr260-opt-dot7]
        if {$large} { set project_dir [file join $repo_dir build v2 kr260-opt-dot7-large] }
    }
    if {$capture} {
        if {!$large} {error "capture requires large capacity"}
        set project_dir [file join $repo_dir build v2 kr260-opt-capture-large]
        if {$capture_flags} {set project_dir [file join $repo_dir build v2 kr260-opt-capture-flags-large]}
        if {$pipeline_cuts} {set project_dir [file join $repo_dir build v2 kr260-opt-pipeline-cuts-large]}
        if {$operand_capture} {set project_dir [file join $repo_dir build v2 kr260-opt-operand-capture-large]}
        if {$source_row_bram} {set project_dir [file join $repo_dir build v2 kr260-opt-source-row-bram-large]}
        if {$attention16_distance} {set project_dir [file join $repo_dir build v2 kr260-opt-attention16-distance-large]}
        if {$request_window_embed} {set project_dir [file join $repo_dir build v2 kr260-opt-request-window-embed-large]}
        if {$context_capture} {set project_dir [file join $repo_dir build v2 kr260-opt-attention-context-capture-large]}
    }
    if {[llength $argv] > 2} { set target_mhz [lindex $argv 2] }
    if {![string is double -strict $target_mhz] || $target_mhz <= 0} {
        error "positive target MHz required"
    }
}

# Optional local checkout of AMD's Board Store, leaving the Vivado install alone.
set board_store [file join $repo_dir build v2 board-store boards Xilinx]
if {[llength [get_board_parts -quiet *kr260_som*]] == 0 && [file isdirectory $board_store]} {
    set_param board.repoPaths [concat [get_param board.repoPaths] [list $board_store]]
}

set part xck26-sfvc784-2LV-c
if {[llength [get_parts -quiet $part]] == 0} {
    error "K26 device support missing: modify the Vivado installation to include Kria SOMs and Starter Kits device support (Zynq UltraScale+ MPSoC), then rerun"
}
set som [lindex [lsort [get_board_parts -quiet *kr260_som*]] end]
if {$som eq ""} {
    error "KR260 SOM board files missing: install Kria KR260 from Vivado Store > Boards, then rerun"
}
create_project sysone_v2_kr260 $project_dir -part $part -force
set_property board_part $som [current_project]
set carrier [lindex [lsort [get_board_parts -quiet *kr260_carrier*]] end]
if {$carrier ne ""} {
    set_property board_connections [list som240_1_connector [string map {:part0 ""} $carrier]:som240_1_connector:1.0] [current_project]
}

set rtl [file join $repo_dir rtl v2]
set source_files [concat \
    [list [file join $rtl encoder encoder_pkg.sv]] \
    [lsearch -all -inline -not -exact [glob -directory [file join $rtl encoder] *.sv] [file join $rtl encoder encoder_pkg.sv]] \
    [list [file join $rtl common sequential_divider.sv] [file join $rtl common sync_fifo.sv] \
          [file join $rtl platform kr260 axi_memory_port.sv] [file join $rtl platform kr260 kr260_encoder.sv] \
          [file join $rtl platform kr260 kr260_encoder_wrapper.v]]]
if {$capture} {lappend source_files [file join $rtl common activation_read_capture.sv]}
if {$capture_flags} {lappend source_files [file join $rtl common sync_fifo_registered_flags.sv]}
if {$pipeline_cuts} {lappend source_files [file join $rtl common attention_probability.sv] [file join $rtl common linear_drain_select.sv]}
if {$operand_capture} {lappend source_files [file join $rtl common attention_probability_input.sv]}
if {$request_window_embed} {lappend source_files [file join $rtl common embed_row_address_dsp.sv]}
if {$optimized} {
    # Freeze each candidate's inputs so later RTL edits cannot invalidate its
    # measurements or affect synthesis processes that have not read files yet.
    set snapshot [file join $project_dir rtl-snapshot]
    set frozen_files {}
    foreach source $source_files {
        set relative [string range $source [expr {[string length $rtl] + 1}] end]
        set frozen [file join $snapshot $relative]
        file mkdir [file dirname $frozen]
        file copy -force $source $frozen
        lappend frozen_files $frozen
    }
    set source_files $frozen_files
}
add_files -norecurse $source_files
set_property file_type SystemVerilog [get_files *.sv]
update_compile_order -fileset sources_1
if {$optimized} {
    set thread_hook [file join $project_dir implementation_threads.tcl]
    file copy -force [file join $repo_dir scripts v2 kr260 implementation_threads.tcl] $thread_hook
    set_property STEPS.OPT_DESIGN.TCL.PRE $thread_hook [get_runs impl_1]
}

create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ultra_ps_e_0]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list \
    CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} \
    CONFIG.PSU__USE__S_AXI_GP2 {1} CONFIG.PSU__SAXIGP2__DATA_WIDTH {128} \
    CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $target_mhz \
    CONFIG.PSU__USE__IRQ0 {1}] $ps

set enc [create_bd_cell -type module -reference kr260_encoder_wrapper encoder]
set_property CONFIG.ATTENTION_LANES $attention_lanes $enc
if {$attention16_distance} {set_property CONFIG.FABRIC_SCORE_DISTANCE 1 $enc}
if {$context_capture} {set_property CONFIG.FABRIC_CONTEXT_CAPTURE 1 $enc}
if {$request_window_embed} {set_property CONFIG.CACHED_REQUEST_WINDOW 1 $enc;set_property CONFIG.DSP_EMBED_ROW_ADDRESS 1 $enc}
if {$optimized} { set_property CONFIG.MAC_INPUT_REGISTERS 1 $enc }
if {$bram} { set_property CONFIG.EXP_TABLE_IN_BRAM 1 $enc }
if {$wide} { set_property CONFIG.MAX_HIDDEN 768 $enc }
if {$large} { set_property CONFIG.MAX_HIDDEN 1024 $enc }
if {$memory} { set_property CONFIG.PIPELINED_URAM 1 $enc }
if {$batch} {
    set_property -dict [list CONFIG.STREAM_RESULTS 1 CONFIG.LOCAL_QUERY_REGISTERS 1 CONFIG.PERF_COUNTERS 1] $enc
}
if {$batch3} { set_property CONFIG.LOCAL_ACCUMULATOR_CONTROLS 1 $enc }
if {$dot7} { set_property CONFIG.LOCAL_ACCUMULATOR_CONTROLS 3 $enc }
if {$capture} {set_property CONFIG.LOCAL_READ_CAPTURE 1 $enc}
if {$capture_flags} {set_property CONFIG.REGISTERED_FIFO_FLAGS 1 $enc}
if {$pipeline_cuts} {set_property CONFIG.PROBABILITY_PIPELINE 1 $enc;set_property CONFIG.PIPELINED_DRAIN_SELECT 1 $enc}
if {$operand_capture} {set_property CONFIG.PROBABILITY_INPUT_CAPTURE 1 $enc;set_property CONFIG.LOCAL_EMBED_CONTROLS 1 $enc}
if {$source_row_bram} {set_property CONFIG.INCREMENTAL_SOURCE_ROW 1 $enc;set_property CONFIG.LINEAR_ACCUMULATORS_IN_BRAM 1 $enc}
if {$dot} { set_property CONFIG.PIPELINED_DOT 1 $enc }
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset reset_pl0]
set sc_ctl [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect control_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $sc_ctl
set sc_mem [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect memory_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $sc_mem

set clk [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
connect_bd_net $clk [get_bd_pins encoder/clk] [get_bd_pins reset_pl0/slowest_sync_clk] \
    [get_bd_pins control_interconnect/aclk] [get_bd_pins memory_interconnect/aclk] \
    [get_bd_pins zynq_ultra_ps_e_0/maxihpm0_fpd_aclk] [get_bd_pins zynq_ultra_ps_e_0/saxihp0_fpd_aclk]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins reset_pl0/ext_reset_in]
connect_bd_net [get_bd_pins reset_pl0/peripheral_aresetn] [get_bd_pins encoder/reset_n] \
    [get_bd_pins control_interconnect/aresetn] [get_bd_pins memory_interconnect/aresetn]
connect_bd_intf_net [get_bd_intf_pins zynq_ultra_ps_e_0/M_AXI_HPM0_FPD] [get_bd_intf_pins control_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_interconnect/M00_AXI] [get_bd_intf_pins encoder/s_axil]
connect_bd_intf_net [get_bd_intf_pins encoder/m_axi] [get_bd_intf_pins memory_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins memory_interconnect/M00_AXI] [get_bd_intf_pins zynq_ultra_ps_e_0/S_AXI_HP0_FPD]
connect_bd_net [get_bd_pins encoder/irq] [get_bd_pins zynq_ultra_ps_e_0/pl_ps_irq0]

assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs encoder/s_axil/reg0]
assign_bd_address [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]
validate_bd_design
save_bd_design
make_wrapper -files [get_files system.bd] -top -import
set_property top system_wrapper [current_fileset]
puts "created [file join $project_dir sysone_v2_kr260.xpr]"

if {$preflight} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Preflight synthesis failed" }
    open_run synth_1
    report_utilization -file [file join $project_dir preflight-utilization.rpt]
    if {$capture} {
        set capture_regs [get_cells -hier -filter {NAME =~ *capture_inst*gen_capture*local_data_reg* && IS_SEQUENTIAL == 1}]
        set out [open [file join $project_dir preflight-local-capture.json] w]
        puts $out [format {{"registers":%d}} [llength $capture_regs]]
        close $out
        if {[llength $capture_regs] != 896} {error "Seven local physical capture stages not preserved"}
    }
    if {$capture_flags} {
        set flags [get_cells -hier -filter {NAME =~ *gen_registered_length_flags* && IS_SEQUENTIAL == 1 && (NAME =~ *full_reg* || NAME =~ *empty_reg*)}]
        set out [open [file join $project_dir preflight-length-flags.json] w]
        puts $out [format {{"registers":%d}} [llength $flags]]
        close $out
        if {[llength $flags] != 2} {error "Length FIFO status registers not preserved"}
    }
    if {$pipeline_cuts} {
        set probability_scope gen_probability_pipeline
        if {$operand_capture} {set probability_scope gen_probability_input}
        set dsp [get_cells -hier -filter "REF_NAME == DSP48E2 && NAME =~ *${probability_scope}*"]
        set registered 0
        foreach cell $dsp {if {[get_property PREG $cell] == 1} {incr registered}}
        set captures [get_cells -hier -filter {NAME =~ *gen_pipelined_drain*selector*bank?_selected* && IS_SEQUENTIAL == 1}]
        set out [open [file join $project_dir preflight-pipeline-cuts.json] w]
        puts $out [format {{"probability_dsps":%d,"registered_probability_dsps":%d,"drain_bank_capture_ff":%d}} [llength $dsp] $registered [llength $captures]]
        close $out
        if {[llength $dsp]!=$attention_lanes || $registered!=$attention_lanes || [llength $captures]<256} {error "Probability or per-bank drain register inference missing"}
        if {$operand_capture} {
            set inputs_registered 0
            set inventory [open [file join $project_dir preflight-probability-input.txt] w]
            foreach cell $dsp {
                set a [get_property AREG $cell]
                set b [get_property BREG $cell]
                set p [get_property PREG $cell]
                puts $inventory "$cell AREG=$a BREG=$b PREG=$p"
                if {$a==1 && $b==2 && $p==1} {incr inputs_registered}
            }
            close $inventory
            set embed_controls [get_cells -hier -filter {NAME =~ *embed_inst*gen_local_embed_controls* && IS_SEQUENTIAL == 1}]
            # Inferred register names may retain the declaration scope instead
            # of the procedural generate scope; accept that exact local netlist.
            if {[llength $embed_controls]==0} {
                set embed_controls [get_cells -hier -filter {IS_SEQUENTIAL == 1 && (NAME =~ *embed_inst*word_shift_local* || NAME =~ *embed_inst*position_shift_local* || NAME =~ *embed_inst*word_bias* || NAME =~ *embed_inst*position_bias*)}]
            }
            set out [open [file join $project_dir preflight-operand-capture.json] w]
            puts $out [format {{"probability_input_registered_dsps":%d,"local_embed_control_ff":%d}} $inputs_registered [llength $embed_controls]]
            close $out
            if {$inputs_registered!=$attention_lanes || [llength $embed_controls]==0} {error "Operand input or embedding local registers missing"}
        }
    }
    if {$context_capture} {
        set context_ff [get_cells -hier -filter {NAME =~ *attention_inst*w_sum_reg* && REF_NAME =~ FD*}]
        set context_dsp [get_cells -hier -filter {NAME =~ *attention_inst*w_product_reg* && REF_NAME == DSP48E2}]
        set passed 0
        set out [open [file join $project_dir preflight-context-dsp.txt] w]
        foreach cell $context_dsp {
            set a [get_property AREG $cell];set b [get_property BREG $cell];set m [get_property MREG $cell];set p [get_property PREG $cell]
            puts $out "$cell AREG=$a BREG=$b MREG=$m PREG=$p"
            if {$a==0 && $b==1 && $m==0 && $p==1} {incr passed}
        }
        close $out
        set out [open [file join $project_dir preflight-context-capture.json] w]
        puts $out [format {{"fabric_context_ff":%d,"context_dsps":%d,"mapping_passed":%d}} [llength $context_ff] [llength $context_dsp] $passed]
        close $out
        if {[llength $context_ff]<92 || [llength $context_dsp]!=4 || $passed!=4} {error "Fabric context capture or context DSP mapping missing"}
    }
    if {$request_window_embed} {
        set window [get_cells -hier -filter {NAME =~ *linear_inst*request_window_limit_reg* && REF_NAME =~ FD*}]
        set dsps [get_cells -hier -filter {NAME =~ *embed_inst*gen_dsp_row_address*address_reg* && REF_NAME == DSP48E2}]
        set passed 0
        set out [open [file join $project_dir preflight-embed-address-dsp.txt] w]
        foreach cell $dsps {
            set a [get_property AREG $cell];set b [get_property BREG $cell];set c [get_property CREG $cell]
            set m [get_property MREG $cell];set p [get_property PREG $cell]
            puts $out "$cell AREG=$a BREG=$b CREG=$c MREG=$m PREG=$p"
            if {$a==1 && $b==1 && $c==1 && $m==0 && $p==1} {incr passed}
        }
        close $out
        set out [open [file join $project_dir preflight-window-embed.json] w]
        puts $out [format {{"request_window_registers":%d,"embed_address_dsps":%d,"embed_address_mapping_passed":%d}} [llength $window] [llength $dsps] $passed]
        close $out
        if {[llength $window]<17 || [llength $dsps]!=2 || $passed!=2} {error "Cached request window or registered embedding DSP cut missing"}
    }
    if {$attention16_distance} {
        set distance_ff [get_cells -hier -filter {NAME =~ *attention_inst*e_distance_reg* && REF_NAME =~ FD*}]
        set distance_dsp [get_cells -hier -filter {NAME =~ *attention_inst*e_product_reg* && REF_NAME == DSP48E2}]
        set count 0
        set out [open [file join $project_dir preflight-distance-dsp.txt] w]
        foreach cell $distance_dsp {
            set a [get_property AREG $cell]
            set p [get_property PREG $cell]
            puts $out "$cell AREG=$a PREG=$p"
            if {$a==0 && $p==1} {incr count}
        }
        close $out
        set out [open [file join $project_dir preflight-attention-width-distance.json] w]
        puts $out [format {{"query_lanes":16,"external_distance_ff":%d,"distance_dsps":%d,"distance_dsp_mapping_passed":%d}} [llength $distance_ff] [llength $distance_dsp] $count]
        close $out
        if {[llength $distance_ff]!=352 || [llength $distance_dsp]!=16 || $count!=16} {error "Fabric score-distance or narrowed query pipeline missing"}
    }
    if {$source_row_bram} {
        set banks [get_cells -hier -filter {NAME =~ *linear_inst*gen_forced_block* && REF_NAME =~ RAMB*}]
        set rows [get_cells -hier -filter {NAME =~ *linear_inst*compute_source_row_reg* && IS_SEQUENTIAL == 1}]
        set lutbanks [get_cells -hier -filter {NAME =~ *linear_inst*gen_lut*accumulator* && REF_NAME =~ RAM* && REF_NAME !~ RAMB*}]
        if {[llength $banks]==0 || [llength $rows]==0 || [llength $lutbanks]!=0} {error "Source row or LINEAR block bank inference failed"}
        set out [open [file join $project_dir preflight-linear-bram.json] w]
        puts $out "\["
        set sep ""
        foreach cell $banks {
            set a [get_property WRITE_MODE_A $cell]
            set b [get_property WRITE_MODE_B $cell]
            set da [get_property DOA_REG $cell]
            set db [get_property DOB_REG $cell]
            puts $out [format {%s{"cell":"%s","primitive":"%s","write_mode_a":"%s","write_mode_b":"%s","doa_reg":%d,"dob_reg":%d}} $sep $cell [get_property REF_NAME $cell] $a $b $da $db]
            set sep ","
            if {$a ne "READ_FIRST" || $b ne "READ_FIRST" || $da!=0 || $db!=0} {error "LINEAR block bank read-first/latency contract changed"}
        }
        puts $out "\]"
        close $out
        set out [open [file join $project_dir preflight-source-row.json] w]
        puts $out [format {{"row_registers":%d,"linear_lutram_cells":%d}} [llength $rows] [llength $lutbanks]]
        close $out
    }
    if {$dot} {
        set out [open [file join $project_dir preflight-dot-stages.json] w]
        puts $out "\["
        set separator ""
        foreach stage {pairs quads octets} {
            set registers [get_cells -hier -filter "NAME =~ *dot_inst*${stage}* && IS_SEQUENTIAL == 1"]
            if {[llength $registers] == 0} { error "Registered dot stage $stage missing" }
            puts $out [format {%s{"stage":"%s","registers":%d}} $separator $stage [llength $registers]]
            set separator ","
        }
        puts $out "\]"
        close $out
    }
    set out [open [file join $project_dir preflight-memory.json] w]
    puts $out "\["
    set separator ""
    foreach cell [get_cells -hier -filter {REF_NAME == URAM288}] {
        set values {}
        foreach prop [list_property $cell] {
            if {[string match *OREG* $prop]} { lappend values "$prop=[get_property $prop $cell]" }
        }
        puts $out [format {%s{"cell":"%s","output_registers":"%s"}} $separator $cell [join $values {;}]]
        set separator ","
    }
    puts $out "\]"
    close $out
    if {$batch2} {
        report_high_fanout_nets -timing -load_types -max_nets 40 -file [file join $project_dir preflight-fanout.rpt]
        set enables [get_cells -hier -filter {NAME =~ *gen_query_distribution*write_enable_reg* && IS_SEQUENTIAL == 1}]
        if {[llength $enables] == 0} { error "Local query enable registers missing after synthesis" }
        set out [open [file join $project_dir preflight-query-controls.json] w]
        puts $out "\["
        set separator ""
        foreach cell $enables {
            set pin [get_pins -of_objects $cell -filter {DIRECTION == OUT}]
            set nets [get_nets -segments -of_objects $pin]
            set loads [get_pins -leaf -of_objects $nets -filter {DIRECTION == IN}]
            puts $out [format {%s{"cell":"%s","loads":%d}} $separator $cell [llength $loads]]
            set separator ","
        }
        puts $out "\]"
        close $out
        if {$batch3} {
            set controls [get_cells -hier -filter {NAME =~ *gen_local_accumulators* && IS_SEQUENTIAL == 1 && (NAME =~ *read_word_reg* || NAME =~ *output_word_reg* || NAME =~ *write_enable_reg* || NAME =~ *write_valid_reg* || NAME =~ *first_key_reg*)}]
            # Shared-read mode has no consumed output_word_reg address: its
            # single read_word_reg is checked instead. Preserve legacy gates.
            if {$dot7} {set controls [filter $controls {NAME !~ *output_word_reg*}]}
            if {[llength $controls] == 0} { error "Local accumulator controls missing after synthesis" }
            set out [open [file join $project_dir preflight-accumulator-controls.json] w]
            puts $out "\["
            set separator ""
            foreach cell $controls {
                set pin [get_pins -of_objects $cell -filter {DIRECTION == OUT}]
                set nets [get_nets -segments -of_objects $pin]
                set loads [get_pins -leaf -of_objects $nets -filter {DIRECTION == IN}]
                puts $out [format {%s{"cell":"%s","loads":%d}} $separator $cell [llength $loads]]
                set separator ","
            }
            puts $out "\]"
            close $out
            if {$dot7} {
                set rams [get_cells -hier -filter {NAME =~ *gen_local_accumulators*gen_lutram* && REF_NAME =~ RAM* && REF_NAME !~ RAMB*}]
                if {[llength $rams] == 0} {error "Shared accumulator distributed RAM inference failed"}
                set out [open [file join $project_dir preflight-accumulator-ram.json] w]
                puts $out "\["
                set separator ""
                foreach cell $rams {
                    puts $out [format {%s{"cell":"%s","primitive":"%s"}} $separator $cell [get_property REF_NAME $cell]]
                    set separator ","
                }
                puts $out "\]"
                close $out
            }
        }
        report_timing_summary -file [file join $project_dir preflight-timing.rpt]
    }
    if {$dot4} {
        # Reuse the loaded design for detailed review rather than paying for
        # another Vivado startup and OOC checkpoint load after synthesis.
        report_timing -delay_type max -max_paths 30 -nworst 1 -input_pins -file [file join $project_dir preflight-critical.rpt]
        report_utilization -hierarchical -hierarchical_depth 6 -file [file join $project_dir preflight-hierarchy.rpt]
        set out [open [file join $project_dir preflight-affine-registers.json] w]
        puts $out "\["
        set separator ""
        foreach unit {scale_inst gamma_inst} {
            set registers [get_cells -hier -filter "NAME =~ *${unit}* && IS_SEQUENTIAL == 1"]
            if {[llength $registers] == 0} { error "Missing arithmetic pipeline $unit" }
            foreach cell $registers {
                set ref [get_property REF_NAME $cell]
                set settings ""
                if {[string match DSP* $ref]} {
                    foreach property [list_property $cell] {
                        if {[regexp {(^|\.)(AREG|BREG|MREG|PREG)$} $property]} {
                            append settings "$property=[get_property $property $cell];"
                        }
                    }
                }
                puts $out [format {%s{"unit":"%s","cell":"%s","primitive":"%s","dsp_registers":"%s"}} $separator $unit $cell $ref $settings]
                set separator ","
            }
        }
        puts $out "\]"
        close $out
    }
    puts "Preflight synthesis and UltraRAM register report ready; no routing launched"
}

if {$build} {
    launch_runs impl_1 -to_step write_bitstream -jobs [expr {$optimized ? 2 : 4}]
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
        error "implementation failed: see the impl_1 run log"
    }
    open_run impl_1
    report_utilization -file [file join $project_dir utilization.rpt]
    report_timing_summary -warn_on_violation -file [file join $project_dir timing.rpt]
    foreach delay {max min} {
        set path [get_timing_paths -quiet -delay_type $delay -max_paths 1]
        if {[llength $path] == 0 || [get_property SLACK $path] < 0} {
            error "implementation does not meet $delay timing: see timing.rpt"
        }
    }
    write_hw_platform -fixed -include_bit -force [file join $project_dir sysone_v2_kr260.xsa]
    set profile [open [file join $project_dir runtime-clock.json] w]
    set target_hz [expr {int($target_mhz * 1000000)}]
    puts $profile "{\"clock_requested_hz\": $target_hz, \"clock_timing_max_hz\": $target_hz}"
    close $profile
    puts "bitstream and [file join $project_dir sysone_v2_kr260.xsa] written"
}
