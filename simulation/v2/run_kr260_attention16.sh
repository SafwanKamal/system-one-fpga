#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-attention16-check"
test ! -d "$output" || { echo 'Preserve existing regression evidence' >&2; exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-capture-regression.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo/build/v2/attention16-prototype/engine-sources/kr260_encoder.sv" "$stage/rtl/v2/platform/kr260/kr260_encoder.sv"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
cp "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
cp -r "$repo/build/v2/rtl-wide-check/vectors" "$stage/simulation/v2/vectors/kr260"
cp -r "$repo/simulation/v2/vectors/encoder" "$stage/simulation/v2/vectors/"
printf '%s\n' "$stage" > "$output/snapshot.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage/simulation/v2"
sed -i 's/--timing -j 0 -O3/--timing -j 2 -O3/g' Makefile
stdbuf -oL make kr260-batch KR260_BATCH_DIR=obj_attention16 KR260_BATCH_HIDDEN=1024 \
    KR260_BATCH_ACCUMULATORS=3 KR260_BATCH_DOT=1 KR260_BATCH_CAPTURE=1 KR260_BATCH_FIFO_FLAGS=1 KR260_BATCH_PROBABILITY=1 KR260_BATCH_DRAIN_SELECT=1 KR260_BATCH_SOURCE_ROW=1 KR260_BATCH_LINEAR_BRAM=1 KR260_BATCH_INPUT_CAPTURE=1 KR260_BATCH_EMBED_CONTROLS=1 \
    2>&1 | tee "$output/wide.log"
for profile in l12 one-word boundary h1024; do
    case "$profile" in
        l12) vectors="$repo/simulation/v2/vectors/kr260" ;;
        one-word) vectors="$repo/build/v2/rtl-batch3-check/one-word-vectors" ;;
        boundary) vectors="$repo/build/v2/rtl-batch-check/boundary-vectors" ;;
        h1024) vectors="$repo/build/v2/kr260-dot7-h1024-eight-vectors" ;;
    esac
    cp -r "$vectors/." vectors/kr260/
    stdbuf -oL ./obj_attention16/kr260_encoder_tb 2>&1 | tee "$output/$profile.log"
done
cp -r "$repo/build/v2/drain-partial-vectors/." vectors/kr260/
stdbuf -oL ./obj_attention16/kr260_encoder_tb 2>&1 | tee "$output/partial.log"
stdbuf -oL make encoder 2>&1 | tee "$output/nexys-default.log"
