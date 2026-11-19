# usage: vitis-run --mode hls --tcl S:/experiments/batched_head/run.tcl   (S: = repository root)
open_project S:/build/v2/batched-head-audit/hls-csim
set_top qwen_decoder
add_files S:/hls/qwen_decoder_v9f/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
add_files -tb S:/experiments/batched_head/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf S:/build/v2/schedule-invariance-audit/meta.bin S:/build/v2/qwen-fpga-decoder-v9e/rope.bin S:/build/v2/schedule-invariance-audit/results.json S:/build/v2/batched-head-audit/results.json"
exit
