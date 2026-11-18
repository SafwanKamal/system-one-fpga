#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/${1:-build/v2/rtl-dot6-arithmetic}"
if test -f "$output/residual.log"; then echo 'Preserve existing arithmetic evidence' >&2; exit 1; fi
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-width-regression.XXXXXX)
printf '%s\n' "$stage" > "$output/snapshot.txt"
cp "$repo/rtl/v2/encoder/"{encoder_pkg,add_skip_engine,mac_array}.sv "$stage/"
sed 's/module add_skip_engine/module add_skip_legacy/' "$repo/build/v2/kr260-opt-dot5-large/rtl-snapshot/encoder/add_skip_engine.sv" > "$stage/add_skip_legacy.sv"
cp "$repo/simulation/v2/"{arithmetic_width_tb,dot_widths_tb}.sv "$stage/"
(cd "$stage" && sha256sum *.sv) > "$output/source-sha256.txt"
cd "$stage"
verilator --binary --timing -j 2 -Wno-fatal --top-module arithmetic_width_tb encoder_pkg.sv add_skip_engine.sv add_skip_legacy.sv arithmetic_width_tb.sv > "$output/residual-build.log" 2>&1
./obj_dir/Varithmetic_width_tb | tee "$output/residual.log"
verilator --binary --timing -j 2 -Wno-fatal --Mdir obj_dot --top-module dot_widths_tb mac_array.sv dot_widths_tb.sv > "$output/dot-build.log" 2>&1
./obj_dot/Vdot_widths_tb | tee "$output/dot.log"
