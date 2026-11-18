#!/usr/bin/env bash
# Run from the extracted, timing-checked pipeline bundle on the KR260.
# Uses the existing model/suite and saves baseline/candidate evidence together.
set -euo pipefail
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${1:-"$HOME/system-one-fpga"}
output=${2:-"$HOME/kr260-pipeline-$(date +%Y%m%d-%H%M%S)"}
python="$HOME/sysone-venv/bin/python"
model=minilm-l12-v1-kr260
suite=build/v2/eval/minilm-l12-v1-matched.json
candidate_app=sysone-v2-pipe
if test -d "$bundle/sysone-v2-bram"; then candidate_app=sysone-v2-bram; fi
if test -d "$bundle/sysone-v2-wide"; then candidate_app=sysone-v2-wide; fi
if test -d "$bundle/sysone-v2-memory"; then candidate_app=sysone-v2-memory; fi
test -x "$python"
test -f "$repo/$suite"
test -f "$bundle/$candidate_app/build.json"
test -f /lib/firmware/xilinx/sysone-v2/build.json
test ! -e "$output"
mkdir -p "$output"
cd "$repo"
if test ! -e src/sysone/v2/kr260_runtime.py.before-pipeline; then
    cp src/sysone/v2/kr260_runtime.py src/sysone/v2/kr260_runtime.py.before-pipeline
fi
cp "$bundle/kr260_runtime.py" src/sysone/v2/kr260_runtime.py
if test -f "$bundle/kr260_link.py"; then
    cp "$bundle/kr260_link.py" src/sysone/v2/kr260_link.py
fi
run_profile() {
    local label=$1 app=$2
    cp "/lib/firmware/xilinx/$app/build.json" "$output/$label-app.json" || return $?
    sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image "$model" load || return $?
    sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image "$model" check --tokens 1 2 3 4 5 12 64 128 || return $?
    sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image "$model" eval \
        --suite "$suite" --verify --report "$output/$label-eval.json"
}
sudo xmutil unloadapp
sudo xmutil loadapp sysone-v2
run_profile baseline sysone-v2 2>&1 | tee "$output/baseline.log"
sudo python3 "$bundle/deploy_app.py" "$bundle/$candidate_app" 2>&1 | tee "$output/deploy.log"
run_profile pipeline "$candidate_app" 2>&1 | tee "$output/pipeline.log"
printf '\nCompleted baseline and pipeline board checks. Reports: %s\n' "$output"
