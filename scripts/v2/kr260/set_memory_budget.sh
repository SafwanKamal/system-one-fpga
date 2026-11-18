#!/usr/bin/env bash
# Validate source FIT, install persistent hooks, regenerate FIT, verify; no reboot.
set -euo pipefail
bytes=${1:?usage: set_memory_budget.sh BYTES [BASE]}
base=${2:-0x60000000}
bundle=$(cd "$(dirname "$0")" && pwd)
repo=${SYSONE_REPO:-"$HOME/system-one-fpga"}
output="$HOME/sysone-boot/memory-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$output"
# Verify the existing FIT and exact reservation-only candidate before mutations.
python3 "$bundle/prepare_reserved_fit.py" --auto-patch --base "$base" --bytes "$bytes" \
    --out "$output/image-memory.fit"
sudo python3 "$bundle/configure_memory.py" --base "$base" --bytes "$bytes"
sudo sh "$bundle/install_memory_hooks.sh"
sudo update-initramfs -u -k "$(uname -r)"
# This independently checks the regenerated FIT's hashes and exact DTB region.
python3 "$bundle/prepare_reserved_fit.py" --auto-patch --base "$base" --bytes "$bytes" \
    --out "$output/image-regenerated-verified.fit"
python3 - "$bundle" "$base" "$bytes" <<'PY'
import sys, struct
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from prepare_reserved_fit import child, parse, TARGET
tree, _, _ = parse(Path('/boot/firmware/image.fit').read_bytes())
dt, _, _ = parse(child(child(tree, 'images'), TARGET)['props']['data'])
base, size = int(sys.argv[2], 0), int(sys.argv[3], 0)
node = child(child(dt, 'reserved-memory'), f'sysone@{base:x}')
assert node['props'] == {'reg': struct.pack('>QQ', base, size), 'no-map': b''}
print('Regenerated boot FIT contains the configured no-map reservation')
PY
test -d "$repo/src/sysone/v2"
cp "$bundle/kr260_runtime.py" "$repo/src/sysone/v2/kr260_runtime.py"
cp "$bundle/sysone_v2_client.py" "$repo/scripts/v2/sysone_v2_client.py"
printf '\nVerified boot FIT. Reboot to activate the allocation, then reload the FPGA app. Evidence: %s\n' "$output"
