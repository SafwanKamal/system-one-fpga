#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/int4-dot16"
work=$(mktemp -d /tmp/sysone-int4-dot.XXXXXX)
cp "$repo/rtl/v2/common/int4_dot16.sv" "$work/"
cp "$repo/simulation/v2/int4_dot16_tb.sv" "$work/"
cp "$output/vectors.mem" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv vectors.mem > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module int4_dot16_tb \
    --Mdir "$work/obj" -o sim int4_dot16.sv int4_dot16_tb.sv > "$output/build.log" 2>&1
"$work/obj/sim" +VECTORS="$work/vectors.mem" +COUNT=6145 | tee "$output/result.log"
