#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/kv-command-axi"
test ! -e "$output" || { echo "Preserve existing evidence" >&2; exit 1; }
mkdir -p "$output"
work=$(mktemp -d /tmp/sysone-relative-axi.XXXXXX)
cp "$repo/rtl/v2/common/kv_read_command.sv" "$work/"
cp "$repo/rtl/v2/common/kv_cache_span.sv" "$work/"
cp "$repo/rtl/v2/common/model_address_window.sv" "$work/"
cp "$repo/rtl/v2/common/relative_read_request.sv" "$work/"
cp "$repo/rtl/v2/common/relative_read_retire.sv" "$work/"
cp "$repo/rtl/v2/common/relative_read_chunker.sv" "$work/"
cp "$repo/build/v2/kr260-opt-capture-flags-large/rtl-snapshot/platform/kr260/axi_memory_port.sv" "$work/"
cp "$repo/build/v2/kr260-opt-capture-flags-large/rtl-snapshot/common/sync_fifo.sv" "$work/"
cp "$repo/build/v2/kr260-opt-capture-flags-large/rtl-snapshot/common/sync_fifo_registered_flags.sv" "$work/"
cp "$repo/simulation/v2/kv_command_axi_tb.sv" "$work/"
printf '%s\n' "$work" > "$output/work-directory.txt"
cd "$work"
sha256sum *.sv > "$output/source-sha256.txt"
: > "$output/result.log"
for registered in 0 1; do
    verilator --binary --timing -j 2 -Wno-fatal --top-module kv_command_axi_tb \
        -GREGISTERED_REQUESTS="$registered" -GREGISTERED_FIFO_FLAGS=1 --Mdir "$work/obj$registered" -o sim \
        kv_read_command.sv kv_cache_span.sv model_address_window.sv relative_read_request.sv relative_read_retire.sv relative_read_chunker.sv sync_fifo.sv sync_fifo_registered_flags.sv axi_memory_port.sv kv_command_axi_tb.sv \
        > "$output/build-$registered.log" 2>&1
    "$work/obj$registered/sim" | tee -a "$output/result.log"
done

printf '{"complete":true,"exit_code":0}\n' > "$output/completion-status.json"
