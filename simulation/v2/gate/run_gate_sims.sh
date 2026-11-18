#!/usr/bin/env bash
# Build and run the agent-gate Verilator testbenches (run inside WSL/Linux).
# GNU make cannot build in paths with spaces, so objects go to a /tmp directory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RTL="$HERE/../../../rtl/v2/gate"
OBJ="${GATE_SIM_OBJ:-/tmp/sysone_gate_sim}"
mkdir -p "$OBJ"
cp "$RTL"/*.sv "$RTL"/bridge/*.sv "$HERE"/*_tb.sv "$OBJ"/
cd "$OBJ"
which="${1:-all}"
if [[ "$which" == all || "$which" == rules ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_rules \
    --top-module gate_rules_tb gate_rules.sv gate_rules_tb.sv 2>&1 | grep -E "%Error" -A4 | head -30 || true
  ./obj_rules/Vgate_rules_tb +vectors="$HERE/vectors/gate_rules_vectors.txt" | tail -12
fi
if [[ "$which" == all || "$which" == core ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_core \
    --top-module gate_core_tb gate_rules.sv gate_core.sv gate_core_tb.sv 2>&1 | grep -E "%Error" -A4 | head -30 || true
  ./obj_core/Vgate_core_tb +frames="$HERE/vectors/gate_frames.txt" | tail -12
fi
if [[ "$which" == all || "$which" == corev3 ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_corev3     --top-module gate_core_v3_tb gate_rules.sv gate_csum.sv gate_core_v3.sv gate_core_v3_tb.sv 2>&1 | grep -E "%Error" -A4 | head -40 || true
  for part in rec fuzz probe; do echo "[corev3 $part]"; ./obj_corev3/Vgate_core_v3_tb +frames="$HERE/vectors/gate_v3_frames_$part.txt" | tail -14; done
fi
if [[ "$which" == all || "$which" == bridgev3 ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_bridgev3 --top-module gate_bridge_core_v3_tb gate_bridge_prims.sv gate_rules.sv gate_csum.sv gate_core_v3.sv gate_async_fifo.sv gate_eth_rx.sv gate_bridge_core_v3.sv gate_bridge_core_v3_tb.sv 2>&1 | grep -E "%Error" -A4 | head -40 || true
  for part in rec fuzz; do echo "[bridgev3 $part]"; ./obj_bridgev3/Vgate_bridge_core_v3_tb +frames="$HERE/vectors/gate_v3_bridge_$part.txt" | tail -14; done
fi
if [[ "$which" == all || "$which" == bridge ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_bridge \
    --top-module gate_bridge_tb gate_bridge_prims.sv gate_rules.sv gate_core.sv gate_async_fifo.sv \
    gate_eth_rx.sv gate_rgmii.sv gate_mdio.sv gate_test_injector.sv gate_bridge_core.sv gate_bridge_io.sv gate_bridge_tb.sv 2>&1 | grep -E "%Error" -A4 | head -30 || true
  ./obj_bridge/Vgate_bridge_tb +frames="$HERE/vectors/gate_bridge_frames.txt" | tail -30
fi
if [[ "$which" == all || "$which" == loop ]]; then
  cp "$HERE/mdio_phy_model.sv" "$OBJ"/
  cp "$HERE/../../../build/v2/agent-gate-bridge/inject/gate_inject_rom.hex" "$OBJ"/
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_loop \
    --top-module gate_loop_tb gate_bridge_prims.sv gate_rules.sv gate_core.sv gate_async_fifo.sv \
    gate_eth_rx.sv gate_rgmii.sv gate_mdio.sv gate_test_injector.sv gate_bridge_core.sv gate_bridge_io.sv \
    mdio_phy_model.sv gate_loop_tb.sv 2>&1 | grep -E "%Error" -A4 | head -30 || true
  ./obj_loop/Vgate_loop_tb | tee "$OBJ/loop_out.txt" | tail -60
fi
if [[ "$which" == all || "$which" == bridge100 ]]; then
  verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style --Mdir obj_bridge100 -DSPEED100     --top-module gate_bridge_tb gate_bridge_prims.sv gate_rules.sv gate_core.sv gate_async_fifo.sv     gate_eth_rx.sv gate_rgmii.sv gate_mdio.sv gate_test_injector.sv gate_bridge_core.sv gate_bridge_io.sv gate_bridge_tb.sv 2>&1 | grep -E "%Error" -A4 | head -30 || true
  ./obj_bridge100/Vgate_bridge_tb +frames="$HERE/vectors/gate_bridge_frames_100.txt" | tail -30
fi
