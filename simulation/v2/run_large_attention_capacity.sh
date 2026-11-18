#!/usr/bin/env bash
# Reuse the frozen H1024 simulation after the base regression finishes.
# No recompilation, RTL changes, synthesis or deployment.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
base="$repo/${1:-build/v2/rtl-dot4-check}"
output="$repo/${2:-build/v2/rtl-dot4-large-check}"
mkdir -p "$output"
deadline=$((SECONDS+10800))
while ! test -f "$base/boundary-1024.log" || ! grep -q 'Verilator: cpu' "$base/boundary-1024.log"; do
    if grep -Eq '^%Error|^FAIL:|Assertion failed|^Aborting' "$base"/*.log; then
        printf 'Base regression failed; large profile not run\n' >&2
        exit 1
    fi
    if (( SECONDS > deadline )); then printf 'Base regression wait timed out\n' >&2; exit 1; fi
    sleep 20
done
stage=$(cat "$base/snapshot.txt")
printf '%s\n' "$stage" > "$output/snapshot.txt"
cd "$stage/simulation/v2"
for profile in wide l12 one-word; do
    case "$profile" in
        wide) vectors="$repo/build/v2/rtl-wide-check/vectors" ;;
        l12) vectors="$repo/simulation/v2/vectors/kr260" ;;
        one-word) vectors="$repo/build/v2/rtl-batch3-check/one-word-vectors" ;;
    esac
    cp -r "$vectors/." vectors/kr260/
    stdbuf -oL ./obj_batch_boundary/kr260_encoder_tb 2>&1 | tee "$output/$profile.log"
done
