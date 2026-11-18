#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/embed-row-dsp-arithmetic"
test ! -d "$output" || { echo 'Preserve arithmetic proof' >&2;exit 1; }
mkdir -p "$output"
work=$(mktemp -d /var/tmp/sysone-embed-row-dsp.XXXXXX)
cp "$repo/simulation/v2/embed_row_address_dsp.sv" "$repo/simulation/v2/embed_row_address_dsp_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
TIMEFORMAT='%R'
{ time verilator --binary --timing -j 2 -Wno-fatal --top-module embed_row_address_dsp_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1; } 2> "$output/compile-seconds.txt"
{ time ./obj/sim | tee "$output/result.log"; } 2> "$output/simulation-seconds.txt"
