open_project S:/build/v2/attention-p4-audit/p4-fixtures
set_top qwen_decoder
add_files S:/experiments/attention_p4/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
config_compile -pipeline_loops 0
add_files -tb S:/hls/qwen_decoder_v9f/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/build/v2/qwen-fpga-decoder-v9e/block-fixture S:/build/v2/qwen-fpga-decoder-v9e/long-fixture"
exit
