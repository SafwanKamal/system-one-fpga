# usage: vitis-run --mode hls --tcl S:/experiments/dual_port/run_s1_csim.tcl   (S: = repository root)
open_project S:/build/v2/dual-port-study/s1-audit/csim
set_top qwen_decoder
add_files S:/build/v2/dual-port-study/src-s1/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
add_files -tb S:/experiments/dual_port/testbench_s1.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf S:/build/v2/schedule-invariance-audit/meta.bin S:/build/v2/qwen-fpga-decoder-v9e/rope.bin S:/build/v2/dual-port-study/s1-audit/s1-results.json S:/build/v2/dual-port-study/s1-audit/s1-dump.bin decode"
exit
