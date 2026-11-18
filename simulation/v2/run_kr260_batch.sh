#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output=${1:-"$repo/build/v2/rtl-batch-check"}
accumulators=${2:-0}
dot=${3:-0}
mkdir -p "$output"
output=$(cd "$output" && pwd)
if test "$dot" = 1; then
    cp -r "$repo/build/v2/rtl-batch3-check/one-word-vectors" "$output/"
    cp -r "$repo/build/v2/rtl-batch-check/boundary-vectors" "$output/"
fi
stage=$(mktemp -d /var/tmp/sysone-batch-regression.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
cp "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
cp -r "$repo/build/v2/rtl-wide-check/vectors" "$stage/simulation/v2/vectors/kr260"
cp -r "$repo/simulation/v2/vectors/encoder" "$stage/simulation/v2/vectors/"
printf '%s\n' "$stage" | tee "$output/snapshot.txt"
verilator --version | tee "$output/verilator.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
cd "$stage/simulation/v2"
sed -i 's/--timing -j 0 -O3/--timing -j 2 -O3/g' Makefile
stdbuf -oL make result-streamer 2>&1 | tee "$output/result-streamer.log"
stdbuf -oL make kr260-batch KR260_BATCH_ACCUMULATORS="$accumulators" KR260_BATCH_DOT="$dot" 2>&1 | tee "$output/batch-wide.log"
cp -r "$repo/simulation/v2/vectors/kr260/." "$stage/simulation/v2/vectors/kr260/"
stdbuf -oL ./obj_kr260_batch/kr260_encoder_tb 2>&1 | tee "$output/batch-l12.log"
if test "$accumulators" != 0; then
    cp -r "$repo/build/v2/rtl-batch3-check/one-word-vectors/." "$stage/simulation/v2/vectors/kr260/"
    stdbuf -oL ./obj_kr260_batch/kr260_encoder_tb 2>&1 | tee "$output/one-word-head.log"
    cp -r "$repo/simulation/v2/vectors/kr260/." "$stage/simulation/v2/vectors/kr260/"
fi
# Same current RTL and profiling overhead, but with both datapath options off.
stdbuf -oL make kr260-batch KR260_BATCH_DIR=obj_batch_control KR260_BATCH_STREAM=0 KR260_BATCH_LOCAL=0 \
    2>&1 | tee "$output/control-l12.log"
stdbuf -oL make encoder 2>&1 | tee "$output/nexys-default.log"
cp -r "$repo/build/v2/rtl-batch-check/boundary-vectors/." "$stage/simulation/v2/vectors/kr260/"
stdbuf -oL make kr260-batch KR260_BATCH_DIR=obj_batch_boundary KR260_BATCH_HIDDEN=1024 KR260_BATCH_ACCUMULATORS="$accumulators" KR260_BATCH_DOT="$dot" \
    2>&1 | tee "$output/boundary-1024.log"
