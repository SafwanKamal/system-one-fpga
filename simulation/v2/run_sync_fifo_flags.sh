#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/sync-fifo-flags"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-fifo-flags.XXXXXX)
cp "$repo/rtl/v2/common/sync_fifo_registered_flags.sv" "$repo/build/v2/kr260-opt-capture-large/rtl-snapshot/common/sync_fifo.sv" "$repo/simulation/v2/sync_fifo_flags_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module sync_fifo_flags_tb \
    --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
