#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/result-streamer-capture"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-streamer-capture.XXXXXX)
cp "$repo/rtl/v2/encoder/result_streamer.sv" "$repo/rtl/v2/common/sync_fifo.sv" "$repo/simulation/v2/result_streamer_capture_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module result_streamer_capture_tb \
    --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
