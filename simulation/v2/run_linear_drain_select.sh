#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/linear-drain-select"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-drain-select.XXXXXX)
cp "$repo/rtl/v2/common/linear_drain_select.sv" "$work/"
cp "$repo/simulation/v2/linear_drain_select_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
: > "$output/result.log"
for channels in 12 32; do
    for lanes in 1 2 4; do
        verilator --binary --timing -j 2 -Wno-fatal --top-module linear_drain_select_tb \
            -GROW_CHANNELS="$channels" -GLANES="$lanes" --Mdir "$work/obj-$channels-$lanes" -o sim \
            linear_drain_select.sv linear_drain_select_tb.sv > "$output/build-$channels-$lanes.log" 2>&1
        "$work/obj-$channels-$lanes/sim" | tee -a "$output/result.log"
    done
done
