#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/embed-dsp-engine"
test ! -f "$output/result.log" || { echo 'Preserve evidence' >&2;exit 1; }
work=$(mktemp -d /var/tmp/sysone-embed-dsp.XXXXXX)
printf '%s\n' "$work" > "$output/snapshot.txt"
cp "$repo/build/v2/request-window-embed-dsp/engine-sources/embed_engine.sv" "$repo/rtl/v2/encoder/encoder_pkg.sv" "$output/embed_controls_tb.sv" "$work/"
sed 's/module embed_engine/module embed_legacy/' "$repo/build/v2/kr260-opt-attention16-distance-large/rtl-snapshot/encoder/embed_engine.sv" > "$work/embed_legacy.sv"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
TIMEFORMAT='%R'
{ time verilator --binary --timing -j 2 -Wno-fatal --top-module embed_controls_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1; } 2> "$output/compile-seconds.txt"
{ time ./obj/sim | tee "$output/result.log"; } 2> "$output/simulation-seconds.txt"
