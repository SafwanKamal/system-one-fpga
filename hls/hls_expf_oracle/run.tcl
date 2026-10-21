# usage: vitis-run --mode hls --tcl run.tcl, with env ORACLE_IN / ORACLE_OUT
open_project S:/build/v2/hls-expf-oracle
set_top hls_expf_top
add_files S:/hls/hls_expf_oracle/oracle.cpp
add_files -tb S:/hls/hls_expf_oracle/main.cpp
open_solution solution -flow_target vivado
set_part {xck26-sfvc784-2LV-c}
csim_design -O -argv "$::env(ORACLE_IN) $::env(ORACLE_OUT)"
exit
