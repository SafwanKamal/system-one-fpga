#!/usr/bin/env bash
# Install a routed package, verify real H1024 capacity and frozen L12 behavior.
set -euo pipefail
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${1:-"$HOME/system-one-fpga"}
output=${2:-"$HOME/kr260-frontier-$(date +%Y%m%d-%H%M%S)"}
python="$HOME/sysone-venv/bin/python"
test -x "$python"
test -f "$repo/build/v2/eval/minilm-l12-v1-matched.json"
test ! -e "$output"
mkdir -p "$output"
candidate_app=sysone-v2-frontier
if test -d "$bundle/sysone-v2-capture"; then candidate_app=sysone-v2-capture; fi
if test -d "$bundle/sysone-v2-capture-flags"; then candidate_app=sysone-v2-capture-flags; fi
if test -d "$bundle/sysone-v2-pipeline-cuts"; then candidate_app=sysone-v2-pipeline-cuts; fi

if test -d "$bundle/sysone-v2-operand-capture"; then candidate_app=sysone-v2-operand-capture; fi
if test -d "$bundle/sysone-v2-source-row-bram"; then candidate_app=sysone-v2-source-row-bram; fi
if test -d "$bundle/sysone-v2-attention16-distance"; then candidate_app=sysone-v2-attention16-distance; fi
if test -d "$bundle/sysone-v2-request-window-embed"; then candidate_app=sysone-v2-request-window-embed; fi
if test -d "$bundle/sysone-v2-attention-context-capture"; then candidate_app=sysone-v2-attention-context-capture; fi

test -f "$bundle/$candidate_app/build.json"
cd "$repo"
previous_app=$(python3 -c 'from pathlib import Path; print(Path("/sys/firmware/devicetree/base/fpga-region/firmware-name").read_bytes().rstrip(b"\0").decode().removesuffix(".bit.bin"))')
case "$previous_app" in sysone-v2|sysone-v2-pipe|sysone-v2-bram|sysone-v2-wide|sysone-v2-memory|sysone-v2-frontier|sysone-v2-capture|sysone-v2-capture-flags|sysone-v2-pipeline-cuts|sysone-v2-operand-capture|sysone-v2-source-row-bram|sysone-v2-attention16-distance|sysone-v2-request-window-embed|sysone-v2-attention-context-capture) ;; *) echo 'Unexpected recovery app'; exit 1;; esac
printf '%s\n' "$previous_app" > "$output/recovery-app.txt"
cp src/sysone/v2/kr260_runtime.py "$output/kr260_runtime.before.py"
cp src/sysone/v2/kr260_link.py "$output/kr260_link.before.py"
cp scripts/v2/sysone_v2_client.py "$output/sysone_v2_client.before.py"
if test -f src/sysone/v2/timing_policy.py; then
    cp src/sysone/v2/timing_policy.py "$output/timing_policy.before.py"
fi
rollback() {
    trap - ERR
    printf 'Frontier validation failed; restoring %s\n' "$previous_app" >&2
    sudo xmutil unloadapp || true
    sudo xmutil loadapp "$previous_app" || true
    cp "$output/kr260_runtime.before.py" src/sysone/v2/kr260_runtime.py
    cp "$output/kr260_link.before.py" src/sysone/v2/kr260_link.py
    cp "$output/sysone_v2_client.before.py" scripts/v2/sysone_v2_client.py
    if test -f "$output/timing_policy.before.py"; then
        cp "$output/timing_policy.before.py" src/sysone/v2/timing_policy.py
    else
        rm -f src/sysone/v2/timing_policy.py
    fi
    sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load || true
    printf 'failed; recovery attempted\n' > "$output/validation-status.txt"
    exit 1
}
trap rollback ERR
sudo xmutil listapps | tee "$output/apps-before.txt"
cp "$bundle/kr260_runtime.py" src/sysone/v2/kr260_runtime.py
cp "$bundle/kr260_link.py" src/sysone/v2/kr260_link.py
cp "$bundle/sysone_v2_client.py" scripts/v2/sysone_v2_client.py
cp "$bundle/timing_policy.py" src/sysone/v2/timing_policy.py
sudo python3 "$bundle/deploy_app.py" "$bundle/$candidate_app" | tee "$output/deploy.log"
cp "$bundle/$candidate_app/build.json" "$output/app.json"
sudo "$python" "$bundle/validate_h1024.py" "$bundle/h1024-vectors" --repo "$repo" --report "$output/h1024.json" | tee "$output/h1024.log"
if test "$candidate_app" = sysone-v2-attention16-distance || test "$candidate_app" = sysone-v2-request-window-embed || test "$candidate_app" = sysone-v2-attention-context-capture; then
    sudo "$python" "$bundle/validate_h1024.py" "$bundle/query-group-vectors" --repo "$repo" --report "$output/query-group.json" | tee "$output/query-group.log"
fi
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load | tee "$output/load.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 check --tokens 1 2 3 4 5 12 64 128 | tee "$output/check.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 eval --suite build/v2/eval/minilm-l12-v1-matched.json --verify --report "$output/eval.json" | tee "$output/eval.log"
printf 'passed\n' > "$output/validation-status.txt"
trap - ERR
printf '\nFrontier validation reports: %s\n' "$output"
