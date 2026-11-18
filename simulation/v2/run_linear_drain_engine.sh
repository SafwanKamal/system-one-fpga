#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/rtl-linear-drain-engine-check"
test ! -d "$output" || { echo 'Preserve existing evidence' >&2;exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-drain-engine.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2" "$stage/rtl/"
cp "$repo/build/v2/linear-drain-engine-sources/linear_engine.sv" "$stage/rtl/v2/encoder/"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
cp "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
cp -r "$repo/simulation/v2/vectors/encoder" "$stage/simulation/v2/vectors/"
sed -i 's@$(V2)/common/activation_read_capture.sv@$(V2)/common/activation_read_capture.sv $(V2)/common/linear_drain_select.sv@' "$stage/simulation/v2/Makefile"
sed -i 's/--timing -j 0 -O3/--timing -j 2 -O3/g' "$stage/simulation/v2/Makefile"
printf '%s\n' "$stage" > "$output/snapshot.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
finish(){ code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage/simulation/v2"
stdbuf -oL make encoder 2>&1 | tee "$output/result.log"
