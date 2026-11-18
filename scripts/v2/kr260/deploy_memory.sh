#!/usr/bin/env bash
# Load the verified UltraRAM app, preserve client helpers and validate existing L12.
set -euo pipefail
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${1:-"$HOME/system-one-fpga"}
output=${2:-"$HOME/kr260-memory-$(date +%Y%m%d-%H%M%S)"}
python="$HOME/sysone-venv/bin/python"
test -x "$python"
test -f "$repo/build/v2/eval/minilm-l12-v1-matched.json"
test ! -e "$output"
mkdir -p "$output"
cd "$repo"
cp src/sysone/v2/kr260_runtime.py "$output/kr260_runtime.before.py"
cp src/sysone/v2/kr260_link.py "$output/kr260_link.before.py"
sudo xmutil listapps | tee "$output/apps-before.txt"
cp "$bundle/kr260_runtime.py" src/sysone/v2/kr260_runtime.py
cp "$bundle/kr260_link.py" src/sysone/v2/kr260_link.py
sudo python3 "$bundle/deploy_app.py" "$bundle/sysone-v2-memory" | tee "$output/deploy.log"
cp "$bundle/sysone-v2-memory/build.json" "$output/app.json"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load | tee "$output/load.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 check --tokens 1 2 3 4 5 12 64 128 | tee "$output/check.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 eval --suite build/v2/eval/minilm-l12-v1-matched.json --verify --report "$output/eval.json" | tee "$output/eval.log"
printf '\nUltraRAM validation reports: %s\n' "$output"
