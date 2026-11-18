#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/attention-probability"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-probability.XXXXXX)
cp "$repo/rtl/v2/common/attention_probability.sv" "$repo/simulation/v2/attention_probability_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module attention_probability_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
