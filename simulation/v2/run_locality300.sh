#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
mode=${1:-full}
case "$mode" in
    full) output="$repo/build/v2/locality300-regression"; capacities="1024 384" ;;
    assert384) output="$repo/build/v2/locality300-assertions"; capacities="384" ;;
    *) echo 'Expected full or assert384' >&2; exit 1 ;;
esac
test ! -e "$output" || { echo 'Preserve existing locality300 evidence' >&2; exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-locality300.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2/candidates/locality300" "$stage/rtl/v2"
cp "$repo"/simulation/v2/*.sv "$stage/simulation/v2/"
cp "$repo/simulation/v2/Makefile" "$stage/simulation/v2/"
printf '\nENCODER_RTL += $(V2)/common/deadline_supervisor.sv\n' >> "$stage/simulation/v2/Makefile"
if [ "$mode" = assert384 ]; then
    sed -i 's/verilator --binary/verilator --assert --binary/g' "$stage/simulation/v2/Makefile"
fi
sed -i "s/32'h53700000/32'h53800000/g" "$stage/simulation/v2/kr260_encoder_tb.sv"
# Verify the new register outcome channel and quarantine on the real AXI wrapper.
python3 - "$stage/simulation/v2/kr260_encoder_tb.sv" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();anchor='        if (memory_error) begin'
assert s.count(anchor)==1
s=s.replace(anchor,'''        axil_write(8'h68, 32'd1);
        axil_write(8'h00, 32'd1);
        repeat(8) @(negedge clk);
        axil_read(8'h60, value);
        if (!value[0] || !value[2] || value[10:8] != 3'd2 || !irq)
            $fatal(1,"Independent deadline/quarantine/IRQ failed");
        axil_read(8'h64, value);
        if (value != 1) $fatal(1,"Supervisor missed exact deadline edge");
        axil_write(8'h00, 32'd2);
        axil_read(8'h60, value);
        if (!value[0] || value[3]) $fatal(1,"Timeout acknowledgement escaped quarantine");
        $display("PASS independent deadline outcome and quarantine at wrapper");
''' + anchor)
p.write_text(s)
PY
printf '%s\n' "$stage" > "$output/stage.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage/simulation/v2"
verilator --binary --timing -j 2 -Wno-fatal --Mdir obj_supervisor \
    --top-module deadline_supervisor_tb "$repo/simulation/v2/deadline_supervisor_tb.sv" \
    "$repo/rtl/contracts/deadline_supervisor.sv" -o deadline_supervisor_tb > "$output/supervisor-build.log" 2>&1
./obj_supervisor/deadline_supervisor_tb | tee "$output/supervisor.log"
for capacity in $capacities; do
    cp -r "$repo/simulation/v2/vectors/kr260" vectors/
    stdbuf -oL make kr260-batch KR260_BATCH_DIR="obj_locality$capacity" KR260_BATCH_HIDDEN="$capacity" \
        KR260_BATCH_ACCUMULATORS=3 KR260_BATCH_DOT=1 KR260_BATCH_CAPTURE=1 \
        KR260_BATCH_FIFO_FLAGS=1 KR260_BATCH_PROBABILITY=1 KR260_BATCH_DRAIN_SELECT=1 \
        KR260_BATCH_ATTENTION_LANES=16 KR260_BATCH_CONTEXT_CAPTURE=1 KR260_BATCH_FABRIC_DISTANCE=1 \
        KR260_BATCH_REQUEST_WINDOW=1 KR260_BATCH_EMBED_ADDRESS_DSP=1 KR260_BATCH_SOURCE_ROW=1 \
        KR260_BATCH_LINEAR_BRAM=1 KR260_BATCH_INPUT_CAPTURE=1 KR260_BATCH_EMBED_CONTROLS=1 \
        > "$output/build-l12-h$capacity.log" 2>&1
    # The make log includes the first numerical run; save a compact copy too.
    grep -E 'FEATURES|case [0-9]+:|PASS' "$output/build-l12-h$capacity.log" > "$output/l12-h$capacity.log"
    if [ "$capacity" = 1024 ]; then
        for profile in wide one-word boundary h1024 head32 partial; do
            case "$profile" in
                wide) vectors="$repo/build/v2/rtl-wide-check/vectors" ;;
                one-word) vectors="$repo/build/v2/rtl-batch3-check/one-word-vectors" ;;
                boundary) vectors="$repo/build/v2/rtl-batch-check/boundary-vectors" ;;
                h1024) vectors="$repo/build/v2/kr260-dot7-h1024-eight-vectors" ;;
                head32) vectors="$repo/build/v2/attention16-head32-vectors" ;;
                partial) vectors="$repo/build/v2/drain-partial-vectors" ;;
            esac
            cp -r "$vectors/." vectors/kr260/
            stdbuf -oL ./obj_locality1024/kr260_encoder_tb > "$output/$profile.log" 2>&1
        done
    fi
done
echo "PASS locality300 $mode; random-stall AXI and deadline outcome"
