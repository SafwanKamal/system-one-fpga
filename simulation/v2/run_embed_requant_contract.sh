#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/embed-requant-contract"
mkdir -p "$output"
# GNU Make rejects the Windows repository path because it contains spaces.
work=$(mktemp -d /tmp/sysone-embed-contract.XXXXXX)
cp "$repo/rtl/v2/encoder/encoder_pkg.sv" "$work/encoder_pkg.sv"
cp "$repo/simulation/v2/embed_requant_contract_tb.sv" "$work/embed_requant_contract_tb.sv"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum encoder_pkg.sv embed_requant_contract_tb.sv > "$output/source-sha256.txt"
verilator --binary --timing -j 2 -Wno-fatal --top-module embed_requant_contract_tb \
    --Mdir "$work/obj" -o sim encoder_pkg.sv embed_requant_contract_tb.sv \
    > "$output/build.log" 2>&1
"$work/obj/sim" | tee "$output/result.log"
