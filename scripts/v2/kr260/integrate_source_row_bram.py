"""Integrate reviewed prototypes only after the grouped numerical gate."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def change(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    review = json.loads((ROOT / 'build/v2/rtl-source-row-bram-check/review.json').read_text())
    assert review['complete'] and review['grouped_bram'] and review['numerical_cases'] == 32
    assert review['partial_cases'] == 6 and review['nexys_outputs_and_cycles_unchanged']
    prototype = ROOT / 'build/v2/linear-source-row-bram/engine-sources/linear_engine.sv'
    assert hashlib.sha256(prototype.read_bytes()).hexdigest() == review['prototype_sha256']
    assert 'INCREMENTAL_SOURCE_ROW' not in (ROOT / 'rtl/v2/encoder/linear_engine.sv').read_text(), 'Already integrated; preserve sources under test'
    baseline = json.loads((ROOT / 'build/v2/kr260-opt-operand-capture-large/regression.json').read_text())
    for name, digest in baseline['rtl_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    edits = {}
    names = ['rtl/v2/encoder/encoder_layer.sv', 'rtl/v2/encoder/encoder_system.sv',
             'rtl/v2/platform/kr260/kr260_encoder.sv', 'rtl/v2/platform/kr260/kr260_encoder_wrapper.v',
             'simulation/v2/kr260_encoder_tb.sv']
    for name in names:
        text = (ROOT / name).read_text()
        text = change(text, '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,',
                      '    parameter integer INCREMENTAL_SOURCE_ROW = 0,\n'
                      '    parameter integer LINEAR_ACCUMULATORS_IN_BRAM = 0,\n'
                      '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,')
        if name.endswith('encoder_layer.sv'):
            text = change(text, '    linear_engine #(\n',
                          '    linear_engine #(\n        .INCREMENTAL_SOURCE_ROW(INCREMENTAL_SOURCE_ROW),\n'
                          '        .LINEAR_ACCUMULATORS_IN_BRAM(LINEAR_ACCUMULATORS_IN_BRAM),\n')
        else:
            text = change(text, '        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),',
                          '        .INCREMENTAL_SOURCE_ROW(INCREMENTAL_SOURCE_ROW),\n'
                          '        .LINEAR_ACCUMULATORS_IN_BRAM(LINEAR_ACCUMULATORS_IN_BRAM),\n'
                          '        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),')
        if name.endswith('kr260_encoder.sv') or name.endswith('kr260_encoder_tb.sv'):
            old = "((PROBABILITY_INPUT_CAPTURE!=0 || LOCAL_EMBED_CONTROLS!=0) ? 32'h53591000 :\n                         ((PROBABILITY_PIPELINE!=0 || PIPELINED_DRAIN_SELECT!=0) ? 32'h53590400 : 32'h53590100))"
            text = change(text, old, "((INCREMENTAL_SOURCE_ROW!=0 || LINEAR_ACCUMULATORS_IN_BRAM!=0) ? 32'h53594000 :\n                         " + old + ')')
            text = change(text, "| (32'(LOCAL_EMBED_CONTROLS != 0) << 11)",
                          "| (32'(LOCAL_EMBED_CONTROLS != 0) << 11)\n"
                          "                        | (32'(INCREMENTAL_SOURCE_ROW != 0) << 12)\n"
                          "                        | (32'(LINEAR_ACCUMULATORS_IN_BRAM != 0) << 13)")
        edits[name] = text
    name = 'rtl/v2/encoder/linear_engine.sv'
    text = (ROOT / name).read_text()
    text = change(text, '    parameter integer PIPELINED_DRAIN_SELECT = 0,',
                  '    parameter integer INCREMENTAL_SOURCE_ROW = 0,\n'
                  '    parameter integer LINEAR_ACCUMULATORS_IN_BRAM = 0,\n'
                  '    parameter integer PIPELINED_DRAIN_SELECT = 0,')
    text = change(text, '    logic [TOKEN_WIDTH-1:0] compute_token;',
                  '    logic [TOKEN_WIDTH-1:0] compute_token;\n'
                  '    logic [BUFFER_ADDRESS_WIDTH-1:0] compute_source_row;')
    assert text.count("compute_token <= '0;") == 3
    text = text.replace("compute_token <= '0;", "compute_token <= '0;\n            compute_source_row <= '0;")
    text = change(text, "compute_token <= compute_token + 1'b1;",
                  "compute_token <= compute_token + 1'b1;\n"
                  "                    compute_source_row <= &compute_token ? '0 : compute_source_row + BUFFER_ADDRESS_WIDTH'(source_row_reg);")
    text = change(text, "assign source_address = BUFFER_ADDRESS_WIDTH'(compute_token * source_row_reg + compute_in_tile);",
                  "assign source_address = INCREMENTAL_SOURCE_ROW!=0 ? BUFFER_ADDRESS_WIDTH'(compute_source_row + compute_in_tile)\n"
                  "                                                   : BUFFER_ADDRESS_WIDTH'(compute_token * source_row_reg + compute_in_tile);")
    marker = '        if (ACCUMULATORS_IN_LUTS != 0) begin : gen_lut'
    explicit = '''        if (LINEAR_ACCUMULATORS_IN_BRAM != 0) begin : gen_forced_block
            (* ram_style = "block" *) logic [32*TO-1:0] accumulator [0:MAX_TOKENS-1];
            always_ff @(posedge clk) begin
                bank_read_data[k] <= accumulator[bank_read_address[k]];
                if (accumulator_write && accumulator_write_bank == 1'(k)) begin
                    accumulator[accumulator_write_address] <= accumulator_write_data;
                end
            end
        end else if (ACCUMULATORS_IN_LUTS != 0) begin : gen_lut'''
    text = change(text, marker, explicit)
    edits[name] = text
    name = 'simulation/v2/Makefile'
    text = (ROOT / name).read_text()
    text = change(text, 'KR260_BATCH_INPUT_CAPTURE ?= 0',
                  'KR260_BATCH_SOURCE_ROW ?= 0\nKR260_BATCH_LINEAR_BRAM ?= 0\nKR260_BATCH_INPUT_CAPTURE ?= 0')
    text = change(text, '-GPROBABILITY_INPUT_CAPTURE=$(KR260_BATCH_INPUT_CAPTURE)',
                  '-GINCREMENTAL_SOURCE_ROW=$(KR260_BATCH_SOURCE_ROW) -GLINEAR_ACCUMULATORS_IN_BRAM=$(KR260_BATCH_LINEAR_BRAM) -GPROBABILITY_INPUT_CAPTURE=$(KR260_BATCH_INPUT_CAPTURE)')
    edits[name] = text
    for name, text in edits.items():
        (ROOT / name).write_bytes(text.encode())
    print('Integrated two default-off row/BRAM options; grouped feature0x53597fff; preserve old branches')


if __name__ == '__main__':
    main()
