#!/usr/bin/env bash
cd "$(dirname "$0")"
for t in rules core bridge loop bridge100; do echo "== $t"; bash run_gate_sims.sh $t 2>&1 | grep -E "gate_|MDIO|mismatch|rror|STATUS 4[0-7]|BMCR" | head -12; done
