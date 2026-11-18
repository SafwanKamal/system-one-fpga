#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/linear-source-row-probe"
test ! -e "$output" || { echo 'Preserve existing evidence' >&2; exit 1; }
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-source-row.XXXXXX)
cp "$repo/simulation/v2/linear_source_row_probe.sv" "$repo/simulation/v2/linear_source_row_tb.sv" "$work/"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module linear_source_row_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
