#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-memory-check"
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-memory-regression.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
cp "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
cp -r "$repo/build/v2/rtl-wide-check/vectors" "$stage/simulation/v2/vectors/kr260"
printf '%s\n' "$stage" | tee "$output/snapshot.txt"
verilator --version | tee "$output/verilator.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
cd "$stage/simulation/v2"
stdbuf -oL make activation-memory 2>&1 | tee "$output/activation-memory.log"
stdbuf -oL make kr260-memory 2>&1 | tee "$output/kr260-memory-wide.log"
cp -r "$repo/simulation/v2/vectors/kr260/." "$stage/simulation/v2/vectors/kr260/"
stdbuf -oL ./obj_kr260_memory/kr260_encoder_tb 2>&1 | tee "$output/kr260-memory-l12.log"
