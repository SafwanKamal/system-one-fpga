#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/embed-controls-integrated"
mkdir -p "$output"
test ! -f "$output/result.log" || { echo 'Preserve evidence' >&2;exit 1; }
work=$(mktemp -d /tmp/sysone-embed-controls.XXXXXX)
cp "$repo/rtl/v2/encoder/embed_engine.sv" "$repo/rtl/v2/encoder/encoder_pkg.sv" "$repo/simulation/v2/embed_controls_tb.sv" "$work/"
sed 's/module embed_engine/module embed_legacy/' "$repo/build/v2/kr260-opt-pipeline-cuts-large/rtl-snapshot/encoder/embed_engine.sv" > "$work/embed_legacy.sv"
sed -i "s/embed_engine #(/embed_engine #(.LOCAL_EMBED_CONTROLS(1),/" "$work/embed_controls_tb.sv"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module embed_controls_tb --Mdir obj -o sim *.sv > "$output/build.log" 2>&1
./obj/sim | tee "$output/result.log"
printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
