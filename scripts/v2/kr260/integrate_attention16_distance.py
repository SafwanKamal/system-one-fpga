"""Integrate admitted query-width/register mapping prototypes exactly once."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def change(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    assert 'FABRIC_SCORE_DISTANCE' not in (ROOT / 'rtl/v2/encoder/attention_engine.sv').read_text(encoding='utf-8'), 'Already integrated; preserve tested sources'
    review = json.loads((ROOT / 'build/v2/rtl-attention16-check/review.json').read_text())
    assert review['complete'] and review['all_outputs_bit_exact'] and review['numerical_cases'] == 32 and review['partial_cases'] == 6
    assert review['nexys_reused_cases'] == 2 and review['query_group_fixture_heads'] == 32
    evidence = json.loads((ROOT / 'build/v2/attention16-distance-ooc/summary.json').read_text())
    assert evidence['complete'] and evidence['lut_reduction'] > 10000
    assert evidence['results'][1]['external_distance_ff'] == 352 and evidence['results'][1]['distance_dsps'] == 16
    assert json.loads((ROOT / 'build/v2/score-distance-engine/review.json').read_text())['complete']
    baseline = json.loads((ROOT / 'build/v2/kr260-opt-source-row-bram-large/regression.json').read_text())
    for name, digest in baseline['rtl_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    for name, digest in evidence['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    edits = {}
    names = ['rtl/v2/encoder/encoder_layer.sv', 'rtl/v2/encoder/encoder_system.sv',
             'rtl/v2/platform/kr260/kr260_encoder.sv', 'rtl/v2/platform/kr260/kr260_encoder_wrapper.v',
             'simulation/v2/kr260_encoder_tb.sv']
    for name in names:
        text = (ROOT / name).read_text(encoding='utf-8')
        text = change(text, '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,',
                      '    parameter integer FABRIC_SCORE_DISTANCE = 0,\n    parameter integer PROBABILITY_INPUT_CAPTURE = 0,')
        if name.endswith('encoder_layer.sv'):
            text = change(text, '    attention_engine #(\n', '    attention_engine #(\n        .FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),\n')
        else:
            text = change(text, '        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),',
                          '        .FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),\n        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),')
        if name.endswith('kr260_encoder_tb.sv'):
            text = change(text, '    parameter integer MAC_INPUT_REGISTERS = 0,',
                          '    parameter integer ATTENTION_LANES = 32,\n    parameter integer MAC_INPUT_REGISTERS = 0,')
            text = change(text, '    localparam integer AW = 40;',
                          '    localparam integer TILE_OUT = 32;\n    localparam integer AW = 40;')
            text = change(text, '.TILE_OUT(32),', '.TILE_OUT(TILE_OUT), .ATTENTION_LANES(ATTENTION_LANES),')
        elif name not in names[:2]:
            import re
            match = re.search(r'    parameter integer TILE_OUT = \d+,', text)
            assert match, name
            text = change(text, match[0], match[0] + '\n    parameter integer ATTENTION_LANES = TILE_OUT,')
            text = change(text, '        .TILE_OUT(TILE_OUT),',
                          '        .TILE_OUT(TILE_OUT),\n        .ATTENTION_LANES(ATTENTION_LANES),')
        if name.endswith('kr260_encoder.sv') or name.endswith('kr260_encoder_tb.sv'):
            old = "((INCREMENTAL_SOURCE_ROW!=0 || LINEAR_ACCUMULATORS_IN_BRAM!=0) ? 32'h53594000 :"
            text = change(text, old,
                          "((FABRIC_SCORE_DISTANCE!=0 || ATTENTION_LANES!=TILE_OUT) ? 32'h535a0000 :\n                         " + old)
            # Close the new outer conditional before the first feature OR.
            old = "32'h53590100)))"
            text = change(text, old, "32'h53590100))))")
            text = change(text, "| (32'(LINEAR_ACCUMULATORS_IN_BRAM != 0) << 13)",
                          "| (32'(LINEAR_ACCUMULATORS_IN_BRAM != 0) << 13)\n"
                          "                        | (32'(ATTENTION_LANES != TILE_OUT) << 14)\n"
                          "                        | (32'(FABRIC_SCORE_DISTANCE != 0) << 15)")
        edits[name] = text
    name = 'rtl/v2/encoder/attention_engine.sv'
    text = (ROOT / name).read_text(encoding='utf-8')
    text = change(text, '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,',
                  '    parameter integer FABRIC_SCORE_DISTANCE = 0,\n    parameter integer PROBABILITY_INPUT_CAPTURE = 0,')
    text = change(text, '    logic [SCORE_WIDTH-1:0] e_distance [0:LANES-1];',
                  '    (* keep = (FABRIC_SCORE_DISTANCE!=0 ? "true" : "false"), dont_touch = (FABRIC_SCORE_DISTANCE!=0 ? "true" : "false") *)\n'
                  '    logic [SCORE_WIDTH-1:0] e_distance [0:LANES-1];')
    edits[name] = text
    name = 'simulation/v2/Makefile'
    text = (ROOT / name).read_text(encoding='utf-8')
    text = change(text, 'KR260_BATCH_SOURCE_ROW ?= 0',
                  'KR260_BATCH_ATTENTION_LANES ?= 32\nKR260_BATCH_FABRIC_DISTANCE ?= 0\nKR260_BATCH_SOURCE_ROW ?= 0')
    text = change(text, '-GINCREMENTAL_SOURCE_ROW=$(KR260_BATCH_SOURCE_ROW)',
                  '-GATTENTION_LANES=$(KR260_BATCH_ATTENTION_LANES) -GFABRIC_SCORE_DISTANCE=$(KR260_BATCH_FABRIC_DISTANCE) -GINCREMENTAL_SOURCE_ROW=$(KR260_BATCH_SOURCE_ROW)')
    edits[name] = text
    for name, text in edits.items():
        (ROOT / name).write_bytes(text.encode())
    print('Integrated default-off fabric distance and query-width forwarding; grouped feature0x535affff')


if __name__ == '__main__':
    main()
