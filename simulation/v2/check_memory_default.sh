#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-memory-check"
stage=$(cat "$output/snapshot.txt")
test -d "$stage/rtl/v2"
cp -r "$repo/simulation/v2/vectors/encoder" "$stage/simulation/v2/vectors/"
cd "$stage/simulation/v2"
# Limit compiler parallelism on the laptop, independently of the Vivado job.
sed -i 's/--timing -j 0 -O3/--timing -j 2 -O3/g' Makefile
stdbuf -oL make encoder 2>&1 | tee "$output/nexys-default.log"
