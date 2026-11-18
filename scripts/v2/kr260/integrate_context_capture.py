"""Integrate reviewed existing-context-register placement option once."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
def replace(t,a,b):
 assert t.count(a)==1,a
 return t.replace(a,b)
def main():
 assert 'FABRIC_CONTEXT_CAPTURE' not in (ROOT/'rtl/v2/encoder/attention_engine.sv').read_text()
 review=json.loads((ROOT/'build/v2/attention-context-capture-ooc/review.json').read_text())
 assert review['accepted_for_parameterized_integration']
 numerical=json.loads((ROOT/'build/v2/rtl-attention-context-capture-check/review.json').read_text())
 assert numerical['exact_outputs_encoder_request_cycles'] and numerical['production_23_sources_unchanged']
 previous=json.loads((ROOT/'build/v2/kr260-opt-request-window-embed-large/regression.json').read_text())
 for n,h in previous['rtl_sha256'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 edits={}
 for name in ['rtl/v2/encoder/encoder_layer.sv','rtl/v2/encoder/encoder_system.sv','rtl/v2/platform/kr260/kr260_encoder.sv','rtl/v2/platform/kr260/kr260_encoder_wrapper.v','simulation/v2/kr260_encoder_tb.sv']:
  t=(ROOT/name).read_text()
  t=replace(t,'    parameter integer FABRIC_SCORE_DISTANCE = 0,','    parameter integer FABRIC_CONTEXT_CAPTURE = 0,\n    parameter integer FABRIC_SCORE_DISTANCE = 0,')
  t=replace(t,'        .FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),','        .FABRIC_CONTEXT_CAPTURE(FABRIC_CONTEXT_CAPTURE),\n        .FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),')
  if name.endswith('kr260_encoder.sv') or name.endswith('kr260_encoder_tb.sv'):
   t=replace(t,"((CACHED_REQUEST_WINDOW!=0 || DSP_EMBED_ROW_ADDRESS!=0) ? 32'h53600000 :","((FABRIC_CONTEXT_CAPTURE!=0) ? 32'h53700000 :\n                         ((CACHED_REQUEST_WINDOW!=0 || DSP_EMBED_ROW_ADDRESS!=0) ? 32'h53600000 :")
   t=replace(t,"32'h53590100)))))","32'h53590100))))))")
   t=replace(t,"| (32'(DSP_EMBED_ROW_ADDRESS != 0) << 17)","| (32'(DSP_EMBED_ROW_ADDRESS != 0) << 17)\n                        | (32'(FABRIC_CONTEXT_CAPTURE != 0) << 18)")
  edits[name]=t
 n='rtl/v2/encoder/attention_engine.sv';t=(ROOT/n).read_text()
 t=replace(t,'    parameter integer FABRIC_SCORE_DISTANCE = 0,','    parameter integer FABRIC_CONTEXT_CAPTURE = 0,\n    parameter integer FABRIC_SCORE_DISTANCE = 0,')
 t=replace(t,'    logic signed [ACCUMULATOR_WIDTH-1:0] w_sum [0:CONTEXT_LANES-1];','    (* keep = (FABRIC_CONTEXT_CAPTURE!=0 ? "true" : "false"), dont_touch = (FABRIC_CONTEXT_CAPTURE!=0 ? "true" : "false") *)\n    logic signed [ACCUMULATOR_WIDTH-1:0] w_sum [0:CONTEXT_LANES-1];')
 edits[n]=t
 n='simulation/v2/Makefile';t=(ROOT/n).read_text()
 t=replace(t,'KR260_BATCH_FABRIC_DISTANCE ?= 0','KR260_BATCH_CONTEXT_CAPTURE ?= 0\nKR260_BATCH_FABRIC_DISTANCE ?= 0')
 t=replace(t,'-GFABRIC_SCORE_DISTANCE=$(KR260_BATCH_FABRIC_DISTANCE)','-GFABRIC_CONTEXT_CAPTURE=$(KR260_BATCH_CONTEXT_CAPTURE) -GFABRIC_SCORE_DISTANCE=$(KR260_BATCH_FABRIC_DISTANCE)')
 edits[n]=t
 for n,t in edits.items():(ROOT/n).write_bytes(t.encode())
 print('Integrated default-off FABRIC_CONTEXT_CAPTURE once; family53700000/full5377ffff')
if __name__=='__main__':main()
