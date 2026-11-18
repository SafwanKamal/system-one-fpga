#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output="$repo/build/v2/${1:-typed200-stage-clamp-integration-v1}"
test ! -e "$output" || { echo 'Preserve existing attempt' >&2; exit 1; }
mkdir -p "$output"
stage=$(mktemp -d /var/tmp/sysone-typed200.XXXXXX)
mkdir -p "$stage/rtl" "$stage/simulation/v2/vectors"
cp -r "$repo/rtl/v2/candidates/typed200_stage_clamp" "$stage/rtl/v2"
cp "$repo/simulation/v2/Makefile" "$repo/simulation/v2/axi_slave_model.sv" "$repo/simulation/v2/kr260_encoder_tb.sv" "$repo/simulation/v2/typed200_scenarios.svh" "$stage/simulation/v2/"
cp -r "$repo/simulation/v2/vectors/kr260" "$stage/simulation/v2/vectors/"
cp "$repo/build/v2/kr260-opt-attention-context-capture-large/rtl-snapshot/platform/kr260/axi_memory_port.sv" "$stage/simulation/v2/reference_axi_memory_port.sv"
python3 - "$stage" "$repo" <<'PY'
from pathlib import Path
import re,sys
stage=Path(sys.argv[1]);repo=Path(sys.argv[2]);sim=stage/'simulation/v2'
p=sim/'reference_axi_memory_port.sv';p.write_text(p.read_text().replace('module axi_memory_port #(','module reference_axi_memory_port #(',1))
s=(repo/'rtl/v2/candidates/typed200/platform/kr260/typed200_encoder.sv').read_text()
s=s.replace('module typed200_encoder #(','module reference_typed200_core #(',1)
s=s.replace('    input logic deployment_ready,','    input logic reference_start,\n    input logic [15:0] reference_tokens,')
a=s.index('    logic reset;');b=s.index('    // ------------------------------------------------------------- encoder',a)
s=s[:a]+'''    wire reset=!reset_n,run_start=reference_start,run_done,busy;
    wire [31:0] program_reg=PROGRAM_ADDRESS,ids_reg=IDS_ADDRESS,result_reg=RESULT_ADDRESS;
    wire [31:0] shape_reg={16'd384,reference_tokens};
    wire [127:0] run_result;
    wire [3:0] perf_events;
    assign irq=run_done;
'''+s[b:]
s=s.replace('axi_memory_port #(','reference_axi_memory_port #(').replace(', .drained(memory_drained)','')
s=s.replace('encoder_system #(','reference_encoder_system #(',1)
(sim/'reference_typed200_core.sv').write_text(s)
# Reference must use the sealed parent streamer, not the modified candidate.
r=(repo/'rtl/v2/candidates/typed200/encoder/encoder_system.sv').read_text()
r=re.sub(r'\bmodule\s+encoder_system\b','module reference_encoder_system',r,count=1)
r=r.replace('result_streamer #(','reference_result_streamer #(',1)
r=r.replace('encoder_layer #(','reference_encoder_layer #(',1)
(sim/'reference_encoder_system.sv').write_text(r)
r=(repo/'rtl/v2/candidates/typed200/encoder/result_streamer.sv').read_text()
(sim/'reference_result_streamer.sv').write_text(r.replace('module result_streamer #(','module reference_result_streamer #(',1))
# Independent arithmetic/control reference: do not share changed ADD_SKIP.
r=(repo/'rtl/v2/candidates/typed200_profile_cache/encoder/encoder_layer.sv').read_text()
r=re.sub(r'\bmodule\s+encoder_layer\b','module reference_encoder_layer',r,count=1)
r=r.replace('add_skip_engine #(','reference_add_skip_engine #(',1)
(sim/'reference_encoder_layer.sv').write_text(r)
r=(repo/'rtl/v2/candidates/typed200_profile_cache/encoder/add_skip_engine.sv').read_text()
r=re.sub(r'\bmodule\s+add_skip_engine\b','module reference_add_skip_engine',r,count=1)
(sim/'reference_add_skip_engine.sv').write_text(r)
p=sim/'kr260_encoder_tb.sv';s=p.read_text()
a=s.index('    initial begin\n        int cases,');b=s.index('    initial begin',a+10)
s=s[:a]+(sim/'typed200_scenarios.svh').read_text()+'\n'+s[b:]
s=s.replace('module kr260_encoder_tb #(','module typed200_encoder_tb #(',1)
s=s.replace('kr260_encoder #(','typed200_encoder #(',1).replace('.clk(clk), .reset_n(reset_n),','.deployment_ready(1\'b1), .clk(clk), .reset_n(reset_n),',1)
a=s.index('    typed200_encoder #(');b=s.index('\n    );',a)+len('\n    );')
instance=s[a:b]
ref=instance.replace('typed200_encoder #(','reference_typed200_core #(').replace(') dut (',') reference_inst (')
ref=ref.replace('.deployment_ready(1\'b1),','.reference_start(dut.run_start), .reference_tokens(dut.admission_tokens),')
ref=re.sub(r'\bm_([a-z]+)\b',r'ref_m_\1',ref).replace('.irq(irq), .memory_error(memory_error)', '.irq(), .memory_error()')
decl=s[s.index('    logic [AW-1:0] m_araddr'):s.index('    logic irq, memory_error;')]
decl=re.sub(r'\bm_([a-z]+)\b',r'ref_m_\1',decl)
ties='\n'.join(f'    assign ref_m_{n}=m_{n};' for n in ['arready','rdata','rresp','rlast','rvalid','awready','wready','bresp','bvalid'])
s=s[:b]+'\n'+decl+ref+'\n'+ties+'\n'+s[b:]
# Separate the model B handshake from a deliberate external response stall.
s=s.replace('    longint image_base;', '    logic model_bvalid,model_bready;\n    wire [1:0] model_bresp,model_rresp;\n    assign m_bvalid=model_bvalid && !hold_b;\n    assign model_bready=m_bready && !hold_b;\n    assign m_bresp=inject_b_error ? 2\'b10 : model_bresp;\n    assign m_rresp=inject_r_error ? 2\'b10 : model_rresp;\n    longint image_base;')
# Only modify the memory model instance, not DUT/reference input wiring.
a=s.index('    axi_slave_model #(');b=s.index('\n    );',a)+len('\n    );');model=s[a:b]
model=model.replace('.bresp(m_bresp)', '.bresp(model_bresp)').replace('.rresp(m_rresp)', '.rresp(model_rresp)').replace('.bvalid(m_bvalid)', '.bvalid(model_bvalid)').replace('.bready(m_bready)', '.bready(model_bready)')
s=s[:a]+model+s[b:]
monitor='\n    always @(posedge clk) if(reset_n) begin\n        assert(dut.encoder_system_inst.encoder_clocks_reg===reference_inst.encoder_system_inst.encoder_clocks_reg)\n            else $fatal(1,"Encoder observation count differs before completion");\n        assert(dut.encoder_system_inst.total_clocks_reg===reference_inst.encoder_system_inst.total_clocks_reg)\n            else $fatal(1,"Request observation count differs before completion");\n    end\n'
index=s.rindex("endmodule");s=s[:index]+monitor+s[index:]
(sim/'typed200_encoder_tb.sv').write_text(s)
PY
printf '%s\n' "$stage" > "$output/stage.txt"
(cd "$stage" && find rtl simulation/v2 -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/source-sha256.txt"
finish() { code=$?; printf '{"exit_code":%d,"complete":%s}\n' "$code" "$([ "$code" = 0 ] && echo true || echo false)" > "$output/completion-status.json"; }
trap finish EXIT
cd "$stage/simulation/v2"
# Exact qualified arithmetic parameters; new service fixes H=384, accepts T<=128.
params=(-GMAX_HIDDEN=1024 -GATTENTION_LANES=16 -GMAC_INPUT_REGISTERS=1 -GPIPELINED_DOT=1
 -GEXP_TABLE_IN_BRAM=1 -GPIPELINED_URAM=1 -GLOCAL_READ_CAPTURE=1 -GINCREMENTAL_SOURCE_ROW=1
 -GLINEAR_ACCUMULATORS_IN_BRAM=1 -GFABRIC_CONTEXT_CAPTURE=1 -GFABRIC_SCORE_DISTANCE=1
 -GCACHED_REQUEST_WINDOW=1 -GDSP_EMBED_ROW_ADDRESS=1 -GPROBABILITY_INPUT_CAPTURE=1
 -GLOCAL_EMBED_CONTROLS=1 -GPROBABILITY_PIPELINE=1 -GPIPELINED_DRAIN_SELECT=1
 -GREGISTERED_FIFO_FLAGS=1 -GSTREAM_RESULTS=1 -GLOCAL_QUERY_REGISTERS=1 -GLOCAL_ACCUMULATOR_CONTROLS=3)
verilator --assert --binary --timing -j 2 -Wno-fatal --Mdir obj --top-module typed200_encoder_tb \
 "${params[@]}" typed200_encoder_tb.sv axi_slave_model.sv reference_axi_memory_port.sv reference_typed200_core.sv reference_encoder_system.sv reference_result_streamer.sv reference_encoder_layer.sv reference_add_skip_engine.sv \
 ../../rtl/v2/common/*.sv ../../rtl/v2/encoder/*.sv ../../rtl/v2/contracts/*.sv \
 ../../rtl/v2/platform/kr260/axi_memory_port.sv ../../rtl/v2/platform/kr260/typed200_encoder.sv \
 -o typed200_encoder_tb > "$output/build.log" 2>&1
stdbuf -oL ./obj/typed200_encoder_tb | tee "$output/run.log"
