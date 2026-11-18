"""Apply the reviewed independent default-off request-window and DSP address cuts once."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]


def main():
    baseline = json.loads((ROOT / 'build/v2/kr260-opt-attention16-distance-large/regression.json').read_text())
    for name, expected in baseline['rtl_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, 'Production changed: ' + name
    proof = json.loads((ROOT / 'build/v2/rtl-request-window-embed-dsp-check/review.json').read_text())
    assert proof['numerical_cases'] == 36 and proof['partial_tile_cases'] == 6 and proof['nexys_default_cases'] == 2
    ooc = json.loads((ROOT / 'build/v2/embed-dsp-ooc/review.json').read_text())
    assert ooc['accepted_for_parameterized_integration'] and ooc['estimated_slack_gain_ns'] > 0
    kernel = ROOT / 'rtl/v2/common/embed_row_address_dsp.sv'
    assert not kernel.exists(), 'Never replay integration'
    edits = {}
    linear = ROOT / 'rtl/v2/encoder/linear_engine.sv'
    text = linear.read_text()
    text = text.replace('    parameter integer INCREMENTAL_SOURCE_ROW = 0,',
                        '    parameter integer CACHED_REQUEST_WINDOW = 0,\n    parameter integer INCREMENTAL_SOURCE_ROW = 0,', 1)
    text = text.replace('    logic [16:0] load_tile_reg;',
                        '    (* keep=(CACHED_REQUEST_WINDOW!=0 ? "true":"false"), dont_touch=(CACHED_REQUEST_WINDOW!=0 ? "true":"false") *) logic [16:0] request_window_limit_reg;\n    logic [16:0] load_tile_reg;', 1)
    text = text.replace("request_tile_reg < load_tile_reg + 17'd2",
                        "request_tile_reg < (CACHED_REQUEST_WINDOW!=0 ? request_window_limit_reg : load_tile_reg + 17'd2)")
    assert text.count("load_tile_reg <= '0;") == 2
    text = text.replace("load_tile_reg <= '0;", "load_tile_reg <= '0;\n            request_window_limit_reg <= 17'd2;")
    text = text.replace("load_tile_reg <= load_tile_reg + 1'b1;", "load_tile_reg <= load_tile_reg + 1'b1;\n                            request_window_limit_reg <= request_window_limit_reg + 1'b1;")
    edits[linear] = text
    embed = ROOT / 'rtl/v2/encoder/embed_engine.sv'
    text = embed.read_text().replace('    parameter integer LOCAL_EMBED_CONTROLS = 0,',
                                    '    parameter integer DSP_EMBED_ROW_ADDRESS = 0,\n    parameter integer LOCAL_EMBED_CONTROLS = 0,', 1)
    prototype = (ROOT / 'build/v2/request-window-embed-dsp/engine-sources/embed_engine.sv').read_text()
    kernels = prototype.split('    embed_row_address_dsp #', 1)[1].split('    // fetched once', 1)[0]
    text = text.replace('    logic pipeline_busy;', '    logic pipeline_busy;\n    if(DSP_EMBED_ROW_ADDRESS!=0) begin:gen_dsp_row_address\n    embed_row_address_dsp #' + kernels + '    end\n', 1)
    old = "            word_row_address <= '0;\n            position_row_address <= '0;"
    assert old in text
    text = text.replace(old, '            if(DSP_EMBED_ROW_ADDRESS==0) begin\n' + old + '\n            end', 1)
    old = "                    word_row_address <= word_address + ADDRESS_WIDTH'(id_reg * word_stride);\n                    position_row_address <= position_address + ADDRESS_WIDTH'(token_reg * position_stride);"
    assert old in text
    text = text.replace(old, '                    if(DSP_EMBED_ROW_ADDRESS==0) begin\n' + old + '\n                    end', 1)
    edits[embed] = text
    hierarchy = ['rtl/v2/encoder/encoder_layer.sv', 'rtl/v2/encoder/encoder_system.sv',
                 'rtl/v2/platform/kr260/kr260_encoder.sv', 'rtl/v2/platform/kr260/kr260_encoder_wrapper.v',
                 'simulation/v2/kr260_encoder_tb.sv']
    for name in hierarchy:
        path = ROOT / name
        text = path.read_text()
        marker = '    parameter integer FABRIC_SCORE_DISTANCE = 0,'
        assert marker in text, name
        text = text.replace(marker, marker + '\n    parameter integer CACHED_REQUEST_WINDOW = 0,\n    parameter integer DSP_EMBED_ROW_ADDRESS = 0,', 1)
        if 'encoder_layer' in name:
            text = text.replace('.INCREMENTAL_SOURCE_ROW(INCREMENTAL_SOURCE_ROW),',
                                '.CACHED_REQUEST_WINDOW(CACHED_REQUEST_WINDOW),\n        .INCREMENTAL_SOURCE_ROW(INCREMENTAL_SOURCE_ROW),', 1)
            text = text.replace('.LOCAL_EMBED_CONTROLS(LOCAL_EMBED_CONTROLS),',
                                '.DSP_EMBED_ROW_ADDRESS(DSP_EMBED_ROW_ADDRESS),\n        .LOCAL_EMBED_CONTROLS(LOCAL_EMBED_CONTROLS),', 1)
        else:
            marker = '.FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),'
            assert marker in text, name
            text = text.replace(marker, marker + '\n        .CACHED_REQUEST_WINDOW(CACHED_REQUEST_WINDOW),\n        .DSP_EMBED_ROW_ADDRESS(DSP_EMBED_ROW_ADDRESS),', 1)
        if name.endswith('kr260_encoder.sv') or name.endswith('kr260_encoder_tb.sv'):
            text = text.replace("((FABRIC_SCORE_DISTANCE!=0 || ATTENTION_LANES!=TILE_OUT) ? 32'h535a0000 :",
                                "((CACHED_REQUEST_WINDOW!=0 || DSP_EMBED_ROW_ADDRESS!=0) ? 32'h53600000 :\n                         ((FABRIC_SCORE_DISTANCE!=0 || ATTENTION_LANES!=TILE_OUT) ? 32'h535a0000 :", 1)
            text = text.replace("32'h53590100))))", "32'h53590100)))))", 1)
            text = text.replace("(32'(FABRIC_SCORE_DISTANCE != 0) << 15)",
                                "(32'(FABRIC_SCORE_DISTANCE != 0) << 15)\n                        | (32'(CACHED_REQUEST_WINDOW != 0) << 16)\n                        | (32'(DSP_EMBED_ROW_ADDRESS != 0) << 17)", 1)
        edits[path] = text
    path = ROOT / 'simulation/v2/Makefile'
    text = path.read_text()
    text = text.replace('ENCODER_RTL :=', 'ENCODER_RTL := $(V2)/common/embed_row_address_dsp.sv \\\n               ', 1)
    text = text.replace('KR260_BATCH_FABRIC_DISTANCE ?= 0', 'KR260_BATCH_FABRIC_DISTANCE ?= 0\nKR260_BATCH_REQUEST_WINDOW ?= 0\nKR260_BATCH_EMBED_ADDRESS_DSP ?= 0', 1)
    text = text.replace('-GFABRIC_SCORE_DISTANCE=$(KR260_BATCH_FABRIC_DISTANCE)',
                        '-GFABRIC_SCORE_DISTANCE=$(KR260_BATCH_FABRIC_DISTANCE) -GCACHED_REQUEST_WINDOW=$(KR260_BATCH_REQUEST_WINDOW) -GDSP_EMBED_ROW_ADDRESS=$(KR260_BATCH_EMBED_ADDRESS_DSP)', 1)
    edits[path] = text
    for path, text in edits.items():
        path.write_bytes(text.encode())
    kernel.write_bytes((ROOT / 'simulation/v2/embed_row_address_dsp.sv').read_bytes())
    print('Applied independent default-off cuts once; family53600000/full5363ffff; 23-source public candidate, fresh regression required')


if __name__ == '__main__':
    main()
