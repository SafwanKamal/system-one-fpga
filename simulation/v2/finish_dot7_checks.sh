#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
bash simulation/v2/run_large_attention_capacity.sh build/v2/rtl-dot7-check build/v2/rtl-dot7-large-check
python3 simulation/v2/summarize_kr260_batch.py build/v2/rtl-dot7-check 3 1
python3 simulation/v2/summarize_large_attention_capacity.py build/v2/rtl-dot7-check build/v2/rtl-dot7-large-check
