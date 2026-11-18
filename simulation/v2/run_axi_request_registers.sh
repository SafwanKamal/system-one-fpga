#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/eval/axi-request-registers"
stage=/var/tmp/sysone-request-registers
mkdir -p "$output"
cd "$stage"
cp queue-compile.log queue-result.log "$output/"
for profile in direct-low registered-low registered-high; do
    flags=(-GREGISTERED_REQUESTS=0)
    if test "$profile" != direct-low; then flags=(-GREGISTERED_REQUESTS=1); fi
    if test "$profile" = registered-high; then flags+=("-GBASE_ADDRESS=40'h800000ff0"); fi
    verilator --binary --timing --assert -Wno-fatal --top-module axi_selftest_tb -j 1 \
        --Mdir "obj-$profile" "${flags[@]}" sync_fifo.sv axi_memory_port.sv ddr_selftest.sv \
        axi_slave_model.sv axi_selftest_tb.sv > "$output/$profile-compile.log" 2>&1
    "./obj-$profile/Vaxi_selftest_tb" > "$output/$profile.log" 2>&1
    tail -n 8 "$output/$profile.log"
done
