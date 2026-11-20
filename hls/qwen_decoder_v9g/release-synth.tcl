open_project S:/build/v2/core-feasibility/p4/hls
set_top qwen_decoder
add_files S:/build/v2/core-feasibility/p4/src/qwen_decoder.cpp -cflags "-std=c++14"
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
create_clock -period 8 -name default
set_clock_uncertainty 1.0
config_compile -pipeline_loops 0
csynth_design
export_design -format ip_catalog -output S:/build/v2/core-feasibility/p4/ip.zip
exit
