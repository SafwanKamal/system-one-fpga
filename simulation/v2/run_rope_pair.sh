#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rope-pair"
work=$(mktemp -d /tmp/sysone-rope.XXXXXX)
cp "$repo/rtl/v2/common/rope_pair_int8.sv" "$repo/simulation/v2/rope_pair_int8_tb.sv" "$output/vectors.txt" "$work/"
cd "$work"
sha256sum *.sv vectors.txt > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module rope_pair_int8_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
