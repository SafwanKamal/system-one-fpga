# usage: vitis-run --mode hls --tcl S:/experiments/attention_p4/run_p4.tcl   (S: = repository root)
open_project S:/build/v2/attention-p4-audit/p4
set_top qwen_decoder
add_files S:/experiments/attention_p4/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
add_files -tb S:/experiments/attention_p4/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf S:/build/v2/schedule-invariance-audit/meta.bin S:/build/v2/qwen-fpga-decoder-v9e/rope.bin S:/build/v2/attention-p4-audit/p4-results.json S:/build/v2/attention-p4-audit/p4-dump.bin all"
exit
