# Inspect the frozen LayerNorm arithmetic candidate after synthesis finishes.
# This script never places, routes, exports or changes RTL.
set_param general.maxThreads 4
set repo [file normalize [file join [file dirname [info script]] .. .. ..]]
set build [file join $repo build v2 kr260-opt-dot3]
set checkpoint [file join $build sysone_v2_kr260.runs synth_1 system_wrapper.dcp]
if {![file exists $checkpoint]} { error "Completed dot3 synthesis checkpoint required" }
# The top synthesis DCP contains out-of-context IP black boxes. open_run loads
# their referenced checkpoints; opening that DCP alone gives incomplete reports.
open_project [file join $build sysone_v2_kr260.xpr]
open_run synth_1
report_timing -delay_type max -max_paths 30 -nworst 1 -input_pins -file [file join $build preflight-critical.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $build preflight-hierarchy.rpt]
set output [open [file join $build preflight-affine-registers.json] w]
puts $output "\["
set separator ""
foreach unit {scale_inst gamma_inst} {
    set registers [get_cells -hier -filter "NAME =~ *${unit}* && IS_SEQUENTIAL == 1"]
    if {[llength $registers] == 0} { error "Missing split-product pipeline $unit" }
    foreach cell $registers {
        set ref [get_property REF_NAME $cell]
        set settings ""
        if {[string match DSP48* $ref]} {
            foreach property {AREG BREG MREG PREG} {
                append settings "$property=[get_property $property $cell];"
            }
        }
        puts $output [format {%s{"unit":"%s","cell":"%s","primitive":"%s","dsp_registers":"%s"}} $separator $unit $cell $ref $settings]
        set separator ","
    }
}
puts $output "\]"
close $output
close_design
