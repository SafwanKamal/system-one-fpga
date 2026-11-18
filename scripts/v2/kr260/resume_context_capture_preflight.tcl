set_param general.maxThreads 4
set repo_dir [file normalize [file join [file dirname [info script]] .. .. ..]]
set project_dir [file join $repo_dir build v2 kr260-opt-attention-context-capture-large]
foreach name {capture capture_flags pipeline_cuts operand_capture context_capture request_window_embed attention16_distance source_row_bram batch2 batch3 dot dot4 dot7} {set $name 1}
set attention_lanes 16
open_project [file join $project_dir sysone_v2_kr260.xpr]
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

close_project
