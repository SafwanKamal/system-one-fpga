#!/usr/bin/env bash
# Verify full H1024 token range, then restore the validated L12 image.
set -euo pipefail
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${1:-"$HOME/system-one-fpga"}
output=${2:-"$HOME/kr260-dot7-extended-$(date +%Y%m%d-%H%M%S)"}
python="$HOME/sysone-venv/bin/python"
test ! -e "$output"
mkdir -p "$output"
cd "$repo"
rollback() {
    trap - ERR
    sudo xmutil unloadapp || true
    sudo xmutil loadapp sysone-v2-memory || true
    sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load || true
    printf 'failed; recovery attempted\n' > "$output/validation-status.txt"
    exit 1
}
trap rollback ERR
sudo "$python" "$bundle/validate_h1024.py" "$bundle/h1024-vectors" --repo "$repo" --report "$output/h1024.json" | tee "$output/h1024.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load | tee "$output/restore-l12.log"
printf 'passed\n' > "$output/validation-status.txt"
trap - ERR
