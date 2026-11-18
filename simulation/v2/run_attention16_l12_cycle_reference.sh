#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/attention16-l12-cycle-reference"
test ! -e "$output" || { echo 'Preserve existing cycle reference' >&2; exit 1; }
mkdir -p "$output"
work=$(mktemp -d /var/tmp/sysone-attention16-l12-reference.XXXXXX)
mkdir -p "$work/vectors/kr260"
stage=$(cat "$repo/build/v2/rtl-attention16-check/snapshot.txt")
cp "$stage/simulation/v2/obj_attention16/kr260_encoder_tb" "$work/sim"
cp -r "$repo/simulation/v2/vectors/kr260/." "$work/vectors/kr260/"
printf '%s\n' "$work" > "$output/snapshot.txt"
cd "$work"
sha256sum sim vectors/kr260/* > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
./sim | tee "$output/l12.log"
