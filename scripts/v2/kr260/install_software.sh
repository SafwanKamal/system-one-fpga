#!/usr/bin/env bash
# Update compatible host programs and verify them without changing the FPGA app.
set -euo pipefail
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${1:-"$HOME/system-one-fpga"}
output=${2:-"$HOME/kr260-software-validation-$(date +%Y%m%d-%H%M%S)"}
python="$HOME/sysone-venv/bin/python"
files=(scripts/v2/sysone_v2_client.py src/sysone/v2/kr260_runtime.py
       src/sysone/v2/kr260_link.py src/sysone/v2/timing_policy.py)
test -x "$python"
test ! -e "$output"
(cd "$bundle" && sha256sum -c files.sha256)
mkdir -p "$output/before"
for file in "${files[@]}"; do
    mkdir -p "$output/before/$(dirname "$file")"
    if test -f "$repo/$file"; then cp "$repo/$file" "$output/before/$file"; fi
done
rollback() {
    trap - ERR
    for file in "${files[@]}"; do
        if test -f "$output/before/$file"; then
            cp "$output/before/$file" "$repo/$file"
        else
            rm -f "$repo/$file"
        fi
    done
    printf 'failed; original software restored\n' > "$output/status.txt"
    exit 1
}
trap rollback ERR
for file in "${files[@]}"; do cp "$bundle/$file" "$repo/$file"; done
cd "$repo"
sha256sum -c "$bundle/files.sha256" | tee "$output/installed-hashes.txt"
cat /sys/firmware/devicetree/base/fpga-region/firmware-name > "$output/firmware-before.bin"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 check --tokens 1 | tee "$output/check.log"
sudo "$python" scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 eval --suite build/v2/eval/minilm-l12-v1-matched.json --verify --report "$output/eval.json" | tee "$output/eval.log"
cmp "$output/firmware-before.bin" /sys/firmware/devicetree/base/fpga-region/firmware-name
printf 'passed\n' > "$output/status.txt"
trap - ERR
printf 'Software verification reports: %s\n' "$output"
