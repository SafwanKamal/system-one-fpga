#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/relative-read-request"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-relative-read.XXXXXX)
cp "$repo/rtl/v2/common/model_address_window.sv" "$work/"
cp "$repo/rtl/v2/common/relative_read_request.sv" "$work/"
cp "$repo/simulation/v2/relative_read_request_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
: > "$output/result.log"
for width in 16 8; do
    verilator --binary --timing -j 2 -Wno-fatal --top-module relative_read_request_tb \
        -GBEATS_WIDTH="$width" --Mdir "$work/obj$width" -o sim \
        model_address_window.sv relative_read_request.sv relative_read_request_tb.sv \
        > "$output/build-$width.log" 2>&1
    "$work/obj$width/sim" | tee -a "$output/result.log"
done
