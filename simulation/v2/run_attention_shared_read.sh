#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-dot7-attention-equivalence"
if test -f "$output/result.log"; then echo 'Preserve prior focused evidence' >&2; exit 1; fi
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-shared-read.XXXXXX)
printf '%s\n' "$stage" > "$output/snapshot.txt"
cp "$repo/rtl/v2/encoder/"{encoder_pkg,attention_engine,mac_array}.sv "$stage/"
cp "$repo/rtl/v2/common/sequential_divider.sv" "$stage/"
sed 's/module attention_engine/module attention_legacy/' "$repo/build/v2/kr260-opt-dot6-large/rtl-snapshot/encoder/attention_engine.sv" > "$stage/attention_legacy.sv"
cp "$repo/simulation/v2/attention_shared_read_tb.sv" "$stage/"
(cd "$stage" && sha256sum *.sv) > "$output/source-sha256.txt"
cd "$stage"
verilator --binary --timing -j 2 -Wno-fatal --top-module attention_shared_read_tb encoder_pkg.sv sequential_divider.sv mac_array.sv attention_engine.sv attention_legacy.sv attention_shared_read_tb.sv > "$output/build.log" 2>&1
./obj_dir/Vattention_shared_read_tb | tee "$output/result.log"
