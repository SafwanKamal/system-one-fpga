open_project S:/build/v2/qwen-fpga-decoder-v3/hls-project
open_solution solution
add_files -tb S:/hls/qwen_decoder_v3/testbench.cpp -cflags "-std=c++14"
csim_design -clean -O -argv "S:/build/v2/qwen-fpga-decoder-v2/block-fixture"
exit
