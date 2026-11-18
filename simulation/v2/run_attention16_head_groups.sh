#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/attention16-head-groups"
test ! -e "$output" || { echo 'Preserve existing head-group evidence' >&2; exit 1; }
mkdir -p "$output"
work=$(mktemp -d /var/tmp/sysone-attention16-headgroups.XXXXXX)
mkdir -p "$work/vectors/kr260"
stage=$(cat "$repo/build/v2/rtl-attention16-check/snapshot.txt")
baseline=$(cat "$repo/build/v2/rtl-source-row-bram-parameter-check/snapshot.txt")
cp "$stage/simulation/v2/obj_attention16/kr260_encoder_tb" "$work/new-sim"
cp "$baseline/simulation/v2/obj_source_row_bram_parameter/kr260_encoder_tb" "$work/baseline-sim"
cp -r "$repo/build/v2/attention16-head32-vectors/." "$work/vectors/kr260/"
printf '%s\n' "$work" > "$output/snapshot.txt"
cd "$work"
sha256sum new-sim baseline-sim vectors/kr260/* > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
./baseline-sim | tee "$output/baseline.log"
./new-sim | tee "$output/attention16.log"
