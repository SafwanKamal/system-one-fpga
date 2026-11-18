#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/probability-input-engine"
if test -f "$output/result.log"; then echo 'Preserve prior focused evidence' >&2; exit 1; fi
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-shared-read.XXXXXX)
printf '%s\n' "$stage" > "$output/snapshot.txt"
cp "$repo/rtl/v2/encoder/"{encoder_pkg,mac_array}.sv "$stage/"
cp "$repo/build/v2/probability-input-cut/engine-sources/attention_engine.sv" "$stage/"
cp "$repo/build/v2/probability-input-cut/engine-sources/attention_probability_input.sv" "$stage/"
cp "$repo/rtl/v2/common/sequential_divider.sv" "$stage/"
sed 's/module attention_engine/module attention_legacy/' "$repo/build/v2/kr260-opt-capture-flags-large/rtl-snapshot/encoder/attention_engine.sv" > "$stage/attention_legacy.sv"
cp "$repo/simulation/v2/attention_probability_input_engine_tb.sv" "$stage/"
(cd "$stage" && sha256sum *.sv) > "$output/source-sha256.txt"
cd "$stage"
verilator --binary --timing -j 2 -Wno-fatal --top-module attention_probability_input_engine_tb encoder_pkg.sv attention_probability_input.sv sequential_divider.sv mac_array.sv attention_engine.sv attention_legacy.sv attention_probability_input_engine_tb.sv > "$output/build.log" 2>&1
./obj_dir/Vattention_probability_input_engine_tb | tee "$output/result.log"
