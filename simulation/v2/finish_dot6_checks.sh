#!/usr/bin/env bash
# Reuse the existing frozen base run; never launch a second compilation.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
bash simulation/v2/run_large_attention_capacity.sh build/v2/rtl-dot6-check build/v2/rtl-dot6-large-check
python3 simulation/v2/summarize_kr260_batch.py build/v2/rtl-dot6-check 2 1
python3 simulation/v2/summarize_large_attention_capacity.py build/v2/rtl-dot6-check build/v2/rtl-dot6-large-check
