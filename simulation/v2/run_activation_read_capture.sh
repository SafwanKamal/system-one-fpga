#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/activation-read-capture"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-activation-capture.XXXXXX)
cp "$repo/rtl/v2/common/activation_read_capture.sv" "$work/"
cp "$repo/simulation/v2/activation_read_capture_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module activation_read_capture_tb \
    --Mdir "$work/obj" -o sim activation_read_capture.sv activation_read_capture_tb.sv \
    > "$output/build.log" 2>&1
"$work/obj/sim" | tee "$output/result.log"
