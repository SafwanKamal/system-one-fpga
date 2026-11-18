open_project S:/build/v2/qwen-fpga-decoder-v6/hls-project
set_top qwen_decoder
add_files S:/hls/qwen_decoder_v6/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 10 -name default
set_clock_uncertainty 1.25
config_compile -pipeline_loops 0
add_files -tb S:/hls/qwen_decoder_v6/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/build/v2/qwen-fpga-decoder-v6/block-fixture"
csynth_design
exit
