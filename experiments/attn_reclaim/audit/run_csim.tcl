# Reference/template Vitis HLS Tcl script for exactness C-sim audit.
# Must be run via `vitis-run --mode hls --tcl ...` with S: subst'd to the
# source checkout root (the OneDrive path with spaces breaks C-sim makefiles).
#
# In normal usage, audit.py generates a per-run Tcl script under
# S:/build/v2/attn-reclaim/gemini/runs/<run_id>/run_csim.tcl using this layout.
open_project S:/build/v2/attn-reclaim/gemini/runs/manual/csim
set_top qwen_decoder
add_files S:/build/v2/dual-port-study/src-s2/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
add_files -tb S:/build/v2/attn-reclaim/gemini/runs/manual/tb/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf S:/build/v2/schedule-invariance-audit/meta.bin S:/build/v2/qwen-fpga-decoder-v9e/rope.bin S:/build/v2/attn-reclaim/gemini/runs/manual/results.json S:/build/v2/attn-reclaim/gemini/runs/manual/dump.bin prefill 1"
exit
