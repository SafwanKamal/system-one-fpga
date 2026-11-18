#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/relative-read-retire"
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-relative-retire.XXXXXX)
cp "$repo/rtl/v2/common/model_address_window.sv" "$repo/rtl/v2/common/relative_read_request.sv" "$repo/rtl/v2/common/relative_read_retire.sv" "$repo/simulation/v2/relative_read_retire_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module relative_read_retire_tb \
    --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
