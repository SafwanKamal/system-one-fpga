#!/usr/bin/env bash
# Validate the integrated optional BRAM tables and preserve the default LUT path.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output=${1:-"$repo/build/v2/rtl-bram-check"}
mkdir -p "$output"
output=$(cd "$output" && pwd)
stage=$(mktemp -d /var/tmp/sysone-bram-regression.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
sed 's/-j 4/-j 2/g; s/-j 0/-j 2/g' "$repo/simulation/v2/Makefile" > "$stage/simulation/v2/Makefile"
cp -r "$repo/simulation/v2/vectors/kr260" "$repo/simulation/v2/vectors/encoder" "$stage/simulation/v2/vectors/"
printf 'Simulation snapshot: %s\n' "$stage" | tee "$output/snapshot.txt"
verilator --version | tee "$output/verilator.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
cd "$stage/simulation/v2"
for target in kr260-pipe kr260-bram encoder; do
    stdbuf -oL make "$target" 2>&1 | tee "$output/$target.log"
done
printf 'PASS: integrated KR260 LUT/BRAM profiles and default Nexys layer\n'
