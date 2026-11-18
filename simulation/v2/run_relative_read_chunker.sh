#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/relative-read-chunker"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-relative-chunker.XXXXXX)
cp "$repo/rtl/v2/common/model_address_window.sv" "$repo/rtl/v2/common/relative_read_chunker.sv" "$repo/simulation/v2/relative_read_chunker_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
: > "$output/result.log"
for width in 16 8; do
    verilator --binary --timing -j 2 -Wno-fatal --top-module relative_read_chunker_tb \
        -GBEATS_WIDTH="$width" --Mdir "obj$width" -o sim *.sv > "$output/build-$width.log" 2>&1
    "./obj$width/sim" | tee -a "$output/result.log"
done
