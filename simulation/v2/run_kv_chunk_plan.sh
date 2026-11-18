#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/kv-chunk-plan"
test ! -e "$output" || { echo 'Preserve existing evidence' >&2; exit 1; }
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-kv-chunks.XXXXXX)
cp "$repo/rtl/v2/common/kv_cache_span.sv" "$repo/rtl/v2/common/relative_read_chunker.sv" "$repo/rtl/v2/common/model_address_window.sv" "$repo/simulation/v2/kv_chunk_plan_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/snapshot.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module kv_chunk_plan_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
