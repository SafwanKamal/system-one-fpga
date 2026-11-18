#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/pipeline-cuts-partial-check"
test ! -d "$output" || { echo 'Preserve evidence' >&2;exit 1; }
mkdir -p "$output"
work=$(mktemp -d /var/tmp/sysone-drain-partial.XXXXXX)
printf '%s\n' "$work" > "$output/work-directory.txt"
for profile in baseline grouped;do
 if test "$profile" = baseline;then original=$(cat "$repo/build/v2/rtl-capture-flags-check/snapshot.txt");binary="$original/simulation/v2/obj_capture/kr260_encoder_tb";
 else original=$(cat "$repo/build/v2/rtl-pipeline-cuts-check/snapshot.txt");binary="$original/simulation/v2/obj_cuts/kr260_encoder_tb";fi
 mkdir -p "$work/$profile/vectors/kr260"
 cp "$binary" "$work/$profile/sim"
 cp "$repo/build/v2/drain-partial-vectors/"* "$work/$profile/vectors/kr260/"
 sha256sum "$binary" > "$output/binary-$profile.sha256"
 (cd "$work/$profile" && ./sim) | tee "$output/$profile.log"
done
printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
