#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/probability-input-cut"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-probability.XXXXXX)
cp "$repo/build/v2/probability-input-cut/engine-sources/attention_probability_input.sv" "$repo/simulation/v2/attention_probability_input_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module attention_probability_input_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
