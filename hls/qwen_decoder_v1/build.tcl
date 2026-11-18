open_project S:/build/v2/qwen-fpga-decoder-v1/hls-project
set_top qwen_decoder
add_files S:/hls/qwen_decoder_v1/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 10 -name default
config_compile -pipeline_loops 0
csynth_design
export_design -format ip_catalog -output S:/build/v2/qwen-fpga-decoder-v1/qwen_decoder_ip.zip
exit
