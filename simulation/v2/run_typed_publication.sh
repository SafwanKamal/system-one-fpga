#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/typed-publication-prototype-v2"
test ! -e "$output" || { echo 'Preserve existing typed-publication evidence' >&2; exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-typed-publication.XXXXXX)
cp "$repo/rtl/contracts/typed_publication_gate.sv" "$stage/"
cp "$repo/simulation/v2/typed_publication_gate_tb.sv" "$stage/"
(cd "$stage" && sha256sum *.sv) > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage"
verilator --assert --binary --timing -j 2 -Wno-fatal --Mdir obj --top-module typed_publication_gate_tb \
    typed_publication_gate.sv typed_publication_gate_tb.sv -o typed_publication_gate_tb > "$output/build.log" 2>&1
./obj/typed_publication_gate_tb | tee "$output/run.log"
