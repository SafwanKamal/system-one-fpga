#!/usr/bin/env bash
# Run after scripts/v2/kr260_vectors.py has generated the desired model's vectors.
# Stage on the Linux filesystem: GNU Make/Verilator reject Windows paths with spaces.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output=${1:-"$repo/build/v2/rtl-pipeline-check"}
mkdir -p "$output"
output=$(cd "$output" && pwd)
stage=$(mktemp -d /var/tmp/sysone-rtl-check.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo"/simulation/v2/*.sv "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
cp -r "$repo/simulation/v2/vectors/kr260" "$stage/simulation/v2/vectors/"
printf 'Simulation snapshot: %s\n' "$stage" | tee "$output/snapshot.txt"
verilator --version | tee "$output/verilator.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
cd "$stage/simulation/v2"
for target in mac-pipeline kr260 kr260-pipe; do
    stdbuf -oL make "$target" 2>&1 | tee "$output/$target.log"
done
printf 'PASS: multiplier, baseline and pipelined KR260 regressions\n'
