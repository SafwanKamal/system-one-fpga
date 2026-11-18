#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/${1:-typed200-c-transport-v2}"
test ! -e "$output" || { echo 'Preserve attempt' >&2; exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-typed200-endpoint.XXXXXX)
cp "$repo/rtl/v2/candidates/typed200/contracts/"*.sv "$stage/"
cp "$repo/simulation/v2/typed_intent_axil_tb.sv" "$stage/"
python3 - "$stage/typed_intent_axil_tb.sv" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
s=s.replace('    typed_intent_axil dut(.*);','''    logic environment_ready=1;
    logic [31:0] encoder_clocks=123,request_clocks=456;
    wire terminal_valid,terminal_quarantined,retired;
    wire [15:0] admission_tokens,admission_first,admission_count,owned_tokens,owned_first,owned_count;
    typed_intent_axil dut(.*);''')
s=s.replace('request_frame(input int id=1','request_frame(input int id=1')
s=s.replace('        if(!partial)put', "        put(8'h1c,1);put(8'h78,1);\n        if(!partial)put")
s=s.replace('        $display("PASS typed intent AXI-Lite:', '''        provision();
        // Old driver CSR writes and START/ACK command values cannot bypass the new ABI.
        put(8'h20,32'h60000400);put(8'h24,32'h01800001);
        put(8'h28,32'h62100400);put(8'h2c,32'h62101400);
        put(0,1,15,0,1);put(0,2,15,0,1);assert(!dut.active);
        provision();request_frame();environment_ready=0;
        put(0,2,15,0,1);assert(!dut.active);environment_ready=1;
        put(8'h1c,32'h00010003);put(8'h78,2);put(0,2);
        get(8'hc4,data);assert(data==32'h00010003);get(8'hc8,data);assert(data==2);
        put(8'h1c,128);put(8'h78,128);
        get(8'hc4,data);assert(data==32'h00010003);get(8'hc8,data);assert(data==2);
        proposal_frame();put(0,4);check_result(1,17,0);put(0,8);
        for(int bad=0;bad<5;bad++)begin
            provision();request_frame();
            case(bad)
                0:put(8'h1c,0);
                1:put(8'h1c,129);
                2:put(8'h78,0);
                3:begin put(8'h1c,32'hffff0001);put(8'h78,1);end
                4:put(8'h78,32'h00010001);
            endcase
            put(0,2);check_result(6,0,0);
        end
        $display("PASS typed200 AXI-Lite:''')
s=s.replace('    typed_intent_axil dut(.*);','    logic [31:0] c_wire[0:26];\n    initial $readmemh("wire-frames.hex",c_wire);\n    typed_intent_axil dut(.*);')
s=s.replace('        $display("PASS typed200 AXI-Lite:','        provision();core_request_id=9;\n        put(8\'h10,c_wire[0]);put(8\'h14,c_wire[1]);put(8\'h18,c_wire[2]);\n        put(8\'h1c,c_wire[3]);put(8\'h78,c_wire[4]);\n        for(int i=0;i<8;i++)put(8\'(32+4*i),c_wire[5+i]);\n        put(0,2);assert(dut.active && dut.result_id==9);\n        for(int i=0;i<14;i++)put(8\'(64+4*i),c_wire[13+i]);\n        put(0,4);check_result(1,17,0);\n        for(int i=0;i<8;i++)begin get(8\'(144+4*i),data);assert(data==CONTRACT[32*i+:32]);end\n        $display("PASS actual C-generated request/proposal SHA frames accepted by RTL; numeric digest readback matches");\n        $display("PASS typed200 AXI-Lite:')
p.write_text(s)
PY
cp "$repo/build/v2/typed200-transport-v4/wire-frames.hex" "$stage/wire-frames.hex"
printf '%s\n' "$stage" > "$output/stage.txt"
(cd "$stage" && sha256sum *.sv wire-frames.hex) > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage"
verilator --assert --binary --timing -j 2 -Wno-fatal --Mdir obj --top-module typed_intent_axil_tb \
 typed_publication_gate.sv typed_intent_guard.sv typed_intent_axil.sv typed_intent_axil_tb.sv \
 -o typed200_endpoint_tb > "$output/build.log" 2>&1
./obj/typed200_endpoint_tb | tee "$output/run.log"
