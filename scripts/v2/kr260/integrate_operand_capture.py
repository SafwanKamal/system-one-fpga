"""Integrate admitted prototypes with explicit default-off production parameters."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]


def replace(text, old, new, count=1):
    assert text.count(old) == count, old
    return text.replace(old, new)


def main():
    assert 'PROBABILITY_INPUT_CAPTURE' not in (ROOT / 'rtl/v2/encoder/attention_engine.sv').read_text(), 'Production integration already applied; preserve sources under test'
    for name in ('rtl-probability-input-check', 'rtl-input-embed-check'):
        review = json.loads((ROOT / f'build/v2/{name}/review.json').read_text())
        assert review['state'] == 'experimental_numerical_ready'
        assert review['numerical_cases'] == 32 and review['nexys_default_outputs_and_cycles_unchanged']
    edits = {}
    hierarchy = ['rtl/v2/encoder/encoder_layer.sv', 'rtl/v2/encoder/encoder_system.sv',
                 'rtl/v2/platform/kr260/kr260_encoder.sv',
                 'rtl/v2/platform/kr260/kr260_encoder_wrapper.v',
                 'simulation/v2/kr260_encoder_tb.sv']
    for name in hierarchy:
        text = (ROOT / name).read_text()
        text = replace(text, '    parameter integer PROBABILITY_PIPELINE = 0,',
                       '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,\n'
                       '    parameter integer LOCAL_EMBED_CONTROLS = 0,\n'
                       '    parameter integer PROBABILITY_PIPELINE = 0,')
        text = replace(text, '        .PROBABILITY_PIPELINE(PROBABILITY_PIPELINE),',
                       '        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),\n'
                       '        .PROBABILITY_PIPELINE(PROBABILITY_PIPELINE),')
        if 'encoder_layer.sv' not in name:
            text = replace(text, '        .PIPELINED_DRAIN_SELECT(PIPELINED_DRAIN_SELECT),',
                           '        .LOCAL_EMBED_CONTROLS(LOCAL_EMBED_CONTROLS),\n'
                           '        .PIPELINED_DRAIN_SELECT(PIPELINED_DRAIN_SELECT),')
        else:
            text = replace(text, '    embed_engine #(\n',
                           '    embed_engine #(\n        .LOCAL_EMBED_CONTROLS(LOCAL_EMBED_CONTROLS),\n')
        if 'kr260_encoder.sv' in name or name.endswith('kr260_encoder_tb.sv'):
            text = replace(text, "((PROBABILITY_PIPELINE!=0 || PIPELINED_DRAIN_SELECT!=0) ? 32'h53590400 : 32'h53590100)",
                           "((PROBABILITY_INPUT_CAPTURE!=0 || LOCAL_EMBED_CONTROLS!=0) ? 32'h53591000 :\n"
                           "                         ((PROBABILITY_PIPELINE!=0 || PIPELINED_DRAIN_SELECT!=0) ? 32'h53590400 : 32'h53590100))")
            text = replace(text, "| (32'(PIPELINED_DRAIN_SELECT != 0) << 9)",
                           "| (32'(PIPELINED_DRAIN_SELECT != 0) << 9)\n"
                           "                        | (32'(PROBABILITY_INPUT_CAPTURE != 0) << 10)\n"
                           "                        | (32'(LOCAL_EMBED_CONTROLS != 0) << 11)")
        edits[name] = text

    name = 'rtl/v2/encoder/attention_engine.sv'
    text = (ROOT / name).read_text()
    text = replace(text, '    parameter integer PROBABILITY_PIPELINE = 0,',
                   '    parameter integer PROBABILITY_INPUT_CAPTURE = 0,\n    parameter integer PROBABILITY_PIPELINE = 0,')
    text = replace(text, '    initial if(PROBABILITY_PIPELINE!=0 && READ_LATENCY<4)',
                   '    initial if(PROBABILITY_INPUT_CAPTURE!=0 && (PROBABILITY_PIPELINE==0 || READ_LATENCY<5))\n'
                   '        $fatal(1,"Probability input capture requires pipeline and read latency>=5");\n'
                   '    initial if(PROBABILITY_PIPELINE!=0 && READ_LATENCY<4)')
    text = replace(text, 's_key[(PROBABILITY_PIPELINE!=0) ? L-3 : L-2]',
                   's_key[(PROBABILITY_INPUT_CAPTURE!=0) ? L-4 : (PROBABILITY_PIPELINE!=0) ? L-3 : L-2]')
    text = replace(text, '    if (PROBABILITY_PIPELINE!=0) begin : gen_probability_pipeline',
                   '    if (PROBABILITY_INPUT_CAPTURE!=0) begin : gen_probability_input\n'
                   '        for(genvar c=0;c<LANES;c++) begin : gen_lane\n'
                   '            attention_probability_input probability_inst(.clk,.reset,.in_valid(1\'b1),\n'
                   '                .exponent(exponent_word[16*c +: 16]),.reciprocal(reciprocal[c]),\n'
                   '                .out_valid(),.probability(probability[c]));\n'
                   '        end\n'
                   '    end else if (PROBABILITY_PIPELINE!=0) begin : gen_probability_pipeline')
    edits[name] = text
    kernel = 'build/v2/probability-input-cut/engine-sources/attention_probability_input.sv'
    edits['rtl/v2/common/attention_probability_input.sv'] = (ROOT / kernel).read_text()

    name = 'rtl/v2/encoder/embed_engine.sv'
    text = (ROOT / name).read_text()
    prototype = (ROOT / 'build/v2/embed-controls/engine-sources/embed_engine.sv').read_text()
    text = replace(text, '    parameter integer READ_LATENCY',
                   '    parameter integer LOCAL_EMBED_CONTROLS = 0,\n    parameter integer READ_LATENCY')
    text = replace(text, '    logic signed [16:0] w_term',
                   '    localparam int TERM_WIDTH = LOCAL_EMBED_CONTROLS!=0 ? 16 : 17;\n'
                   '    localparam int SUM_WIDTH = LOCAL_EMBED_CONTROLS!=0 ? 33 : 34;\n'
                   '    logic signed [TERM_WIDTH-1:0] w_term')
    text = replace(text, '            logic signed [33:0] sum;',
                   '            logic signed [SUM_WIDTH-1:0] sum;')
    controls = prototype[prototype.index('    logic [5:0] word_shift_local'):prototype.index('    always_ff @(posedge clk) begin', prototype.index('    logic [5:0] word_shift_local'))]
    controls = controls.replace('    always_ff @(posedge clk)begin', '    if (LOCAL_EMBED_CONTROLS!=0) begin : gen_local_embed_controls\n    always_ff @(posedge clk)begin') + '    end\n'
    marker = '    always_ff @(posedge clk) begin\n        for (int e = 0; e < LANES; e++) begin'
    text = replace(text, marker, controls + marker)
    start = text.index('            // stage 3: requantised, clamped terms')
    end = text.index('\n        end\n        // R row', start)
    original = text[start:end].replace("34'(w_term[e]) + 34'(p_term[e]) + 34'(type_term[e])", "SUM_WIDTH'(w_term[e]) + SUM_WIDTH'(p_term[e]) + SUM_WIDTH'(type_term[e])")
    pstart = prototype.index('            // stage 3: requantised, clamped terms')
    pend = prototype.index('\n        end\n        // R row', pstart)
    optimized = prototype[pstart:pend].replace("33'(w_term[e]) + 33'(p_term[e]) + 33'(type_term[e])", "SUM_WIDTH'(w_term[e]) + SUM_WIDTH'(p_term[e]) + SUM_WIDTH'(type_term[e])")
    text = text[:start] + '            if (LOCAL_EMBED_CONTROLS!=0) begin\n' + optimized + '\n            end else begin\n' + original + '\n            end' + text[end:]
    edits[name] = text

    name = 'simulation/v2/Makefile'
    text = (ROOT / name).read_text()
    text = text.replace('$(V2)/common/attention_probability.sv', '$(V2)/common/attention_probability.sv $(V2)/common/attention_probability_input.sv')
    text = replace(text, 'KR260_BATCH_PROBABILITY ?= 0',
                   'KR260_BATCH_INPUT_CAPTURE ?= 0\nKR260_BATCH_EMBED_CONTROLS ?= 0\nKR260_BATCH_PROBABILITY ?= 0')
    text = replace(text, '-GPROBABILITY_PIPELINE=$(KR260_BATCH_PROBABILITY)',
                   '-GPROBABILITY_INPUT_CAPTURE=$(KR260_BATCH_INPUT_CAPTURE) -GLOCAL_EMBED_CONTROLS=$(KR260_BATCH_EMBED_CONTROLS) -GPROBABILITY_PIPELINE=$(KR260_BATCH_PROBABILITY)')
    edits[name] = text
    # Build every proposed edit in memory before modifying any production file.
    for name, text in edits.items():
        (ROOT / name).write_bytes(text.encode())
    print('Integrated default-off operand capture and local embedding controls:', len(edits), 'files')


if __name__ == '__main__':
    main()
