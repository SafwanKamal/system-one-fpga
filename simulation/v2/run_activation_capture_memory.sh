#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/activation-capture-memory"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-activation-memory.XXXXXX)
cp "$repo/rtl/v2/common/activation_read_capture.sv" "$repo/rtl/v2/common/activation_capture_probe.sv" "$repo/rtl/v2/encoder/activation_buffer.sv" "$repo/simulation/v2/activation_capture_memory_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module activation_capture_memory_tb \
    --Mdir "$work/obj" -o sim activation_buffer.sv activation_read_capture.sv activation_capture_probe.sv activation_capture_memory_tb.sv \
    > "$output/build.log" 2>&1
"$work/obj/sim" | tee "$output/result.log"
