#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/kv-cache-span"
test ! -e "$output/result.log" || { echo 'Preserve existing evidence' >&2; exit 1; }
work=$(mktemp -d /tmp/sysone-kv-span.XXXXXX)
cp "$repo/rtl/v2/common/kv_cache_span.sv" "$repo/simulation/v2/kv_cache_span_tb.sv" "$work/"
cp "$output/vectors.hex" "$output/count.txt" "$work/"
printf '%s\n' "$work" > "$output/snapshot.txt"
cd "$work"
sha256sum *.sv vectors.hex > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module kv_cache_span_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
