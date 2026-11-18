// ATTENTION instruction: per head h and query token i
//
//     s_j   = q_i,h . k_j,h                         (INT8 x INT8 -> INT32)
//     idx_j = min(requant(max_j s - s_j, Msm, Ssm), 255)
//     e_j   = idx_j == 255 ? 0 : exp[idx_j]        (UINT16 table, fetched once)
//     r     = floor(2^24 / sum_j e_j)               (one division per row)
//     p_j   = min((e_j * r + 2^15) >> 16, 255)
//     ctx_i,h = clamp(requant(sum_j p_j * v_j,h, Mctx, Sctx), +-127)
//
// Exactly ImageMachine._attention. Q (src), K (src2) and V are INT8 rows of
// heads * head_dim bytes; CTX likewise.
//
// LANES queries are processed together on the shared mac_array, so every K and V
// word read from the buffers feeds LANES x 16 multipliers:
//   scores     a = the LANES queries' 16 dims, b = a key word   (dot products)
//   P.V        a = each query's p_j,         b = a value word (outer product)
// and the softmax runs LANES rows at a time (LANES table lookups and dividers).
// Per head and group of LANES queries: about LANES*dw + n*dw (scores) + n (exp)
// + 42 (divide) + n*dw (P.V) + LANES*dw (write) clocks, dw = head_dim / 16.
// head_dim must be a multiple of 16 and at most MAX_HEAD_DIM.
module attention_engine
    import encoder_pkg::*;
#(
    parameter integer READ_LATENCY = encoder_pkg::READ_LATENCY,
    parameter integer LANES = 12,
    parameter integer MAC_LATENCY = 1,
    parameter integer PIPELINED_DOT = 0,
    parameter integer FABRIC_CONTEXT_CAPTURE = 0,
    parameter integer FABRIC_SCORE_DISTANCE = 0,
    parameter integer PROBABILITY_INPUT_CAPTURE = 0,
    parameter integer PROBABILITY_PIPELINE = 0,
    parameter integer LOCAL_QUERY_REGISTERS = 0,
    // 0 legacy, 1 local FF banks, 2 dual-read LUTRAM, 3 shared-read LUTRAM.
    parameter integer LOCAL_ACCUMULATOR_CONTROLS = 0,
    // KR260 has spare BRAM; preserve LUT memory for the BRAM-constrained Nexys.
    parameter integer EXP_TABLE_IN_BRAM = 0,
    parameter integer MAX_TOKENS = 128,
    parameter integer MAX_HEAD_DIM = 64,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic mac_issue,
    output logic done,

    input logic [15:0] heads,
    input logic [15:0] head_dim,
    input logic [16:0] softmax_multiplier,
    input logic [5:0] softmax_shift,
    input logic [16:0] context_multiplier,
    input logic [5:0] context_shift,
    input logic [ADDRESS_WIDTH-1:0] exp_address,
    input logic [7:0] token_count,

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic [BUFFER_ADDRESS_WIDTH-1:0] q_address,
    input logic [127:0] q_data,
    input logic [127:0] query_group_data [0:(LANES+3)/4-1],
    output logic [BUFFER_ADDRESS_WIDTH-1:0] k_address,
    input logic [127:0] k_data,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] v_address,
    input logic [127:0] v_data,

    // shared multiplier array
    output logic signed [8:0] mac_a [0:LANES-1][0:15],
    output logic signed [7:0] mac_b [0:15],
    input logic signed [16:0] mac_product [0:LANES-1][0:15],
    input logic signed [23:0] mac_dot [0:LANES-1],

    output logic destination_write,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    localparam integer MAX_WORDS = MAX_HEAD_DIM / 16;
    localparam integer EXP_STEPS = 256;
    localparam integer LANE_WIDTH = $clog2(LANES + 1);
    // widths from the value ranges (INT8 codes are within +-127, p_j <= 255):
    // |s_j| <= head_dim * 127^2, so scores and max - s fit SCORE_WIDTH bits;
    // |sum_j p_j v_j| <= n * 255 * 127; sum_j e_j <= n * 65535; r = 2^24 / sum <= 256
    // because the row maximum contributes exp[0] = 65535.
    localparam integer SCORE_WIDTH = $clog2(MAX_HEAD_DIM * 127 * 127) + 2;
    localparam integer ACCUMULATOR_WIDTH = $clog2(MAX_TOKENS * 255 * 127) + 1;
    localparam integer DIVIDER_WIDTH = 25;          // 2^24 / (<= MAX_TOKENS * 65535)
    localparam integer CONTEXT_LANES = 4;           // requantisers in the write-out

    typedef enum logic [4:0] {
        IDLE,
        TABLE_REQUEST,
        TABLE_RECEIVE,
        TABLE_WRITE,
        LOAD_Q,
        LOAD_Q_DRAIN,
        SCORE,
        SCORE_FLUSH,
        EXPONENT,
        EXPONENT_FLUSH,
        DIVIDE,
        DIVIDE_WAIT,
        WEIGHTED_SUM,
        WEIGHTED_FLUSH,
        WRITE,
        WRITE_FLUSH,
        FINISH
    } state_t;

    state_t state_reg, state_next;
    logic [127:0] table_beat;                       // exp table beat being written
    logic table_last;
    logic [7:0] tokens_reg, tokens_next;
    logic [15:0] heads_reg, heads_next;
    logic [7:0] head_words_reg, head_words_next;    // head_dim / 16
    logic [7:0] row_words_reg, row_words_next;      // heads * head_dim / 16
    logic [15:0] head_reg, head_next;
    logic [7:0] base_reg, base_next;                // first query of the group
    logic [LANE_WIDTH-1:0] lanes_reg, lanes_next;   // queries in the group
    logic [LANE_WIDTH-1:0] lane_reg, lane_next;
    logic [7:0] key_reg, key_next;
    logic [7:0] word_reg, word_next;
    logic [15:0] beat_reg, beat_next;
    logic [1:0] part_reg, part_next;                // CONTEXT_LANES-element part of a word

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            tokens_reg <= '0;
            heads_reg <= '0;
            head_words_reg <= '0;
            row_words_reg <= '0;
            head_reg <= '0;
            base_reg <= '0;
            lanes_reg <= '0;
            lane_reg <= '0;
            key_reg <= '0;
            word_reg <= '0;
            beat_reg <= '0;
            part_reg <= '0;
        end else begin
            state_reg <= state_next;
            tokens_reg <= tokens_next;
            heads_reg <= heads_next;
            head_words_reg <= head_words_next;
            row_words_reg <= row_words_next;
            head_reg <= head_next;
            base_reg <= base_next;
            lanes_reg <= lanes_next;
            lane_reg <= lane_next;
            key_reg <= key_next;
            word_reg <= word_next;
            beat_reg <= beat_next;
            part_reg <= part_next;
        end
    end

    logic issue_q, issue_k, issue_e, issue_v;
    logic pipeline_busy;
    logic dividers_done;
    logic [7:0] next_base;
    logic [7:0] left;
    assign next_base = base_reg + 8'(LANES);

    always_comb begin
        state_next = state_reg;
        tokens_next = tokens_reg;
        heads_next = heads_reg;
        head_words_next = head_words_reg;
        row_words_next = row_words_reg;
        head_next = head_reg;
        base_next = base_reg;
        lanes_next = lanes_reg;
        lane_next = lane_reg;
        key_next = key_reg;
        word_next = word_reg;
        beat_next = beat_reg;
        part_next = part_reg;

        read_request_valid = 1'b0;
        read_request_address = exp_address;
        read_request_beats = BEATS_WIDTH'(EXP_STEPS * 2 / 16);
        read_ready = 1'b0;
        issue_q = 1'b0;
        issue_k = 1'b0;
        issue_e = 1'b0;
        issue_v = 1'b0;
        left = '0;

        case (state_reg)
            IDLE: begin
                if (start) begin
                    tokens_next = token_count;
                    heads_next = heads;
                    head_words_next = 8'(head_dim >> 4);
                    row_words_next = 8'((heads * head_dim) >> 4);
                    beat_next = '0;
                    state_next = TABLE_REQUEST;
                end
            end

            TABLE_REQUEST: begin
                read_request_valid = 1'b1;
                if (read_request_ready) begin
                    state_next = TABLE_RECEIVE;
                end
            end

            // the exp table arrives 8 entries per beat and is written one entry per clock,
            // so every lane's copy is a plain single-write-port distributed RAM
            TABLE_RECEIVE: begin
                read_ready = 1'b1;
                if (read_valid) begin
                    word_next = '0;
                    state_next = TABLE_WRITE;
                end
            end

            TABLE_WRITE: begin
                word_next = word_reg + 1'b1;
                if (word_reg == 8'd7) begin
                    beat_next = beat_reg + 1'b1;
                    state_next = TABLE_RECEIVE;
                    if (table_last) begin
                        head_next = '0;
                        base_next = '0;
                        lanes_next = (tokens_reg >= 8'(LANES)) ? LANE_WIDTH'(LANES) : LANE_WIDTH'(tokens_reg);
                        lane_next = '0;
                        word_next = '0;
                        state_next = LOAD_Q;
                    end
                end
            end

            LOAD_Q: begin
                issue_q = 1'b1;
                word_next = word_reg + 1'b1;
                if (word_reg == head_words_reg - 1'b1) begin
                    word_next = '0;
                    lane_next = lane_reg + 1'b1;
                    if (lane_reg == lanes_reg - 1'b1) begin
                        key_next = '0;
                        state_next = LOCAL_QUERY_REGISTERS != 0 ? LOAD_Q_DRAIN : SCORE;
                    end
                end
            end

            LOAD_Q_DRAIN: state_next = SCORE; // one extra query distribution stage

            SCORE: begin
                issue_k = 1'b1;
                word_next = word_reg + 1'b1;
                if (word_reg == head_words_reg - 1'b1) begin
                    word_next = '0;
                    key_next = key_reg + 1'b1;
                    if (key_reg == tokens_reg - 1'b1) begin
                        state_next = SCORE_FLUSH;
                    end
                end
            end

            SCORE_FLUSH: begin
                if (!pipeline_busy) begin
                    key_next = '0;
                    state_next = EXPONENT;
                end
            end

            EXPONENT: begin
                issue_e = 1'b1;
                key_next = key_reg + 1'b1;
                if (key_reg == tokens_reg - 1'b1) begin
                    state_next = EXPONENT_FLUSH;
                end
            end

            EXPONENT_FLUSH: begin
                if (!pipeline_busy) begin
                    state_next = DIVIDE;
                end
            end

            DIVIDE: begin
                state_next = DIVIDE_WAIT;
            end

            DIVIDE_WAIT: begin
                if (dividers_done) begin
                    key_next = '0;
                    word_next = '0;
                    state_next = WEIGHTED_SUM;
                end
            end

            WEIGHTED_SUM: begin
                issue_v = 1'b1;
                word_next = word_reg + 1'b1;
                if (word_reg == head_words_reg - 1'b1) begin
                    word_next = '0;
                    key_next = key_reg + 1'b1;
                    if (key_reg == tokens_reg - 1'b1) begin
                        state_next = WEIGHTED_FLUSH;
                    end
                end
            end

            WEIGHTED_FLUSH: begin
                if (!pipeline_busy) begin
                    lane_next = '0;
                    word_next = '0;
                    part_next = '0;
                    state_next = WRITE;
                end
            end

            WRITE: begin
                part_next = part_reg + 1'b1;
                if (part_reg == 2'd3) begin
                word_next = word_reg + 1'b1;
                if (word_reg == head_words_reg - 1'b1) begin
                    word_next = '0;
                    lane_next = lane_reg + 1'b1;
                    if (lane_reg == lanes_reg - 1'b1) begin
                        lane_next = '0;
                        if (next_base >= tokens_reg) begin
                            base_next = '0;
                            left = tokens_reg;
                            if (head_reg == heads_reg - 1'b1) begin
                                state_next = WRITE_FLUSH;
                            end else begin
                                head_next = head_reg + 1'b1;
                                state_next = LOAD_Q;
                            end
                        end else begin
                            base_next = next_base;
                            left = tokens_reg - next_base;
                            state_next = LOAD_Q;
                        end
                        lanes_next = (left >= 8'(LANES)) ? LANE_WIDTH'(LANES) : LANE_WIDTH'(left);
                    end
                end
                end
            end

            WRITE_FLUSH: begin
                if (!pipeline_busy) begin
                    state_next = FINISH;
                end
            end

            FINISH: state_next = IDLE;
            default: state_next = IDLE;
        endcase
    end

    assign busy = (state_reg != IDLE);
    assign done = (state_reg == FINISH);

    // ---------------------------------------------------------------- buffers

    logic [BUFFER_ADDRESS_WIDTH-1:0] head_word;
    if (PIPELINED_DOT != 0) begin : gen_address_cursors
        // Loop-carried offsets replace runtime products on each buffer request.
        // Advance at the same FSM edges as their indices; no extra read latency.
        logic [BUFFER_ADDRESS_WIDTH-1:0] head_offset_reg;
        logic [BUFFER_ADDRESS_WIDTH-1:0] group_row_reg, query_row_reg, key_row_reg;
        logic [BUFFER_ADDRESS_WIDTH-1:0] next_group_row;
        assign next_group_row = group_row_reg + BUFFER_ADDRESS_WIDTH'(LANES * row_words_reg);
        always_ff @(posedge clk or posedge reset) begin
            if (reset) begin
                head_offset_reg <= '0;
                group_row_reg <= '0;
                query_row_reg <= '0;
                key_row_reg <= '0;
            end else if (state_reg == IDLE && start) begin
                head_offset_reg <= '0;
                group_row_reg <= '0;
                query_row_reg <= '0;
                key_row_reg <= '0;
            end else begin
                if (head_next != head_reg)
                    head_offset_reg <= head_next == '0 ? '0 : head_offset_reg + BUFFER_ADDRESS_WIDTH'(head_words_reg);
                if (base_next != base_reg)
                    group_row_reg <= base_next == '0 ? '0 : next_group_row;
                if (key_next != key_reg)
                    key_row_reg <= key_next == '0 ? '0 : key_row_reg + BUFFER_ADDRESS_WIDTH'(row_words_reg);
                if (state_reg == LOAD_Q && word_reg == head_words_reg - 1'b1)
                    query_row_reg <= query_row_reg + BUFFER_ADDRESS_WIDTH'(row_words_reg);
                // Q loading advances one row beyond the group. Context output
                // restarts at its first row after the weighted-sum pipeline drains.
                if (state_reg == WEIGHTED_FLUSH && !pipeline_busy)
                    query_row_reg <= group_row_reg;
                if (state_reg == WRITE && part_reg == 2'd3 && word_reg == head_words_reg - 1'b1) begin
                    if (lane_reg == lanes_reg - 1'b1)
                        query_row_reg <= next_base >= tokens_reg ? '0 : next_group_row;
                    else
                        query_row_reg <= query_row_reg + BUFFER_ADDRESS_WIDTH'(row_words_reg);
                end
            end
        end
        assign head_word = head_offset_reg + BUFFER_ADDRESS_WIDTH'(word_reg);
        assign q_address = query_row_reg + head_word;
        assign k_address = key_row_reg + head_word;
        assign v_address = key_row_reg + head_word;
`ifndef SYNTHESIS
        always_ff @(posedge clk) if (!reset) begin
            if (issue_q || state_reg == WRITE)
                assert(q_address == BUFFER_ADDRESS_WIDTH'((base_reg + 8'(lane_reg)) * row_words_reg)
                                    + BUFFER_ADDRESS_WIDTH'(head_reg * head_words_reg + word_reg))
                    else $fatal(1,"attention query cursor/index mismatch");
            if (issue_k || issue_v)
                assert(k_address == BUFFER_ADDRESS_WIDTH'(key_reg * row_words_reg)
                                    + BUFFER_ADDRESS_WIDTH'(head_reg * head_words_reg + word_reg))
                    else $fatal(1,"attention key cursor/index mismatch");
        end
`endif
    end else begin : gen_address_legacy
        assign head_word = BUFFER_ADDRESS_WIDTH'(head_reg * head_words_reg + word_reg);
        assign q_address = BUFFER_ADDRESS_WIDTH'((base_reg + 8'(lane_reg)) * row_words_reg) + head_word;
        assign k_address = BUFFER_ADDRESS_WIDTH'(key_reg * row_words_reg) + head_word;
        assign v_address = BUFFER_ADDRESS_WIDTH'(key_reg * row_words_reg) + head_word;
    end

    // ---------------------------------------------------------- storage

    // The exponential lookup storage below supplies one independent read per lane.
    logic signed [7:0] query [0:LANES-1][0:MAX_WORDS-1][0:15];
    // score and exponential rows: one word per key, all lanes (block RAM)
    logic [SCORE_WIDTH*LANES-1:0] score_ram [0:MAX_TOKENS-1];
    logic [16*LANES-1:0] exponent_ram [0:MAX_TOKENS-1];
    logic [SCORE_WIDTH*LANES-1:0] score_word, score_write_word;
    logic [16*LANES-1:0] exponent_word, exponent_write_word;
    logic score_write, exponent_write;
    logic signed [SCORE_WIDTH-1:0] maximum [0:LANES-1];
    logic [DIVIDER_WIDTH-1:0] total [0:LANES-1];
    logic [8:0] reciprocal [0:LANES-1];
    logic signed [SCORE_WIDTH-1:0] partial [0:LANES-1];
    // P.V sums: one RAM word per head word (16 dims), holding all lanes' 16 sums;
    // read-modify-write one word per clock, the first key overwrites
    localparam integer WORD_BITS = (MAX_WORDS > 1) ? $clog2(MAX_WORDS) : 1;
    localparam integer ROW_BITS = ACCUMULATOR_WIDTH * 16 * LANES;
    logic [ROW_BITS-1:0] accumulator_out;

    // pipelines (L = READ_LATENCY):
    //   buffer reads   c0 issue; cL Q/K/V word (mac_array operands); L+1 products;
    //                  L+2 score dot products (accumulated over the head's words there)
    //   P.V            exponent row read at L-2, probabilities at L-1, operands at L,
    //                  accumulator read-modify-write at L+1
    //   exponentials   e1 score row; e2 max - s; e3 product; e4 rounded index;
    //                  e5 table value -> exponent row, row total
    //   context out    w1 sums selected; w2 products; w3 rounded; w4 clamped -> word
    localparam int L = READ_LATENCY;
`ifndef SYNTHESIS
    initial if(PROBABILITY_INPUT_CAPTURE!=0 && (PROBABILITY_PIPELINE==0 || READ_LATENCY<5))
        $fatal(1,"Probability input capture requires pipeline and read latency>=5");
    initial if(PROBABILITY_PIPELINE!=0 && READ_LATENCY<4)
        $fatal(1,"Probability pipeline requires read latency>=4");
`endif
    localparam int P = L + MAC_LATENCY;
    localparam int D = P + (PIPELINED_DOT != 0 ? 4 : 1);
    localparam int EXP_DEPTH = 5;
    localparam int WRITE_DEPTH = 4;
    logic [D:1] s_q, s_k, s_v;
    logic [7:0] s_word [1:D];
    logic [7:0] s_key [1:D];
    logic [LANE_WIDTH-1:0] s_lane [1:D];
    logic s_last [1:D];
    logic [EXP_DEPTH:1] e_valid;
    logic [7:0] e_key [1:EXP_DEPTH];
    logic [WRITE_DEPTH:1] w_stage;

    always_ff @(posedge clk) begin
        score_word <= score_ram[key_reg];
        exponent_word <= exponent_ram[s_key[(PROBABILITY_INPUT_CAPTURE!=0) ? L-4 : (PROBABILITY_PIPELINE!=0) ? L-3 : L-2]];
        if (score_write) score_ram[s_key[D]] <= score_write_word;
        if (exponent_write) exponent_ram[e_key[EXP_DEPTH]] <= exponent_write_word;
    end

    // ------------------------------------------------------- read pipeline

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            s_q <= '0;
            s_k <= '0;
            s_v <= '0;
            e_valid <= '0;
        end else begin
            s_q <= D'({s_q, issue_q});
            s_k <= D'({s_k, issue_k});
            s_v <= D'({s_v, issue_v});
            e_valid <= EXP_DEPTH'({e_valid, issue_e});
        end
    end

    always_ff @(posedge clk) begin
        s_word[1] <= word_reg;
        s_key[1] <= key_reg;
        s_lane[1] <= lane_reg;
        s_last[1] <= (word_reg == head_words_reg - 1'b1);
        for (int i = 2; i <= D; i++) begin
            s_word[i] <= s_word[i-1];
            s_key[i] <= s_key[i-1];
            s_lane[i] <= s_lane[i-1];
            s_last[i] <= s_last[i-1];
        end
        e_key[1] <= key_reg;
        for (int i = 2; i <= EXP_DEPTH; i++) e_key[i] <= e_key[i-1];
    end

    assign mac_issue = s_k[L] || s_v[L];
    assign pipeline_busy = |{s_q, s_k, s_v, e_valid, w_stage};

    // probabilities of key s_key[L] for every lane (P.V operands), from the exponent
    // row read a clock earlier
    logic [8:0] probability [0:LANES-1];
    if (PROBABILITY_INPUT_CAPTURE!=0) begin : gen_probability_input
        for(genvar c=0;c<LANES;c++) begin : gen_lane
            attention_probability_input probability_inst(.clk,.reset,.in_valid(1'b1),
                .exponent(exponent_word[16*c +: 16]),.reciprocal(reciprocal[c]),
                .out_valid(),.probability(probability[c]));
        end
    end else if (PROBABILITY_PIPELINE!=0) begin : gen_probability_pipeline
        for(genvar c=0;c<LANES;c++) begin : gen_lane
            attention_probability probability_inst(.clk,.reset,.in_valid(1'b1),
                .exponent(exponent_word[16*c +: 16]),.reciprocal(reciprocal[c]),
                .out_valid(),.probability(probability[c]));
        end
    end else begin : gen_probability_default
        always_ff @(posedge clk) for(int c=0;c<LANES;c++)begin
            logic [24:0] value;
            value=(25'(exponent_word[16*c +: 16])*25'(reciprocal[c])+25'd32768)>>16;
            probability[c]<=value>255 ? 9'd255 : {1'b0,value[7:0]};
        end
    end

    always_comb begin
        for (int r = 0; r < 16; r++) begin
            mac_b[r] = s_v[L] ? $signed(v_data[8*r +: 8]) : $signed(k_data[8*r +: 8]);
            for (int c = 0; c < LANES; c++) begin
                mac_a[c][r] = s_v[L] ? $signed(probability[c]) : 9'(query[c][s_word[L]][r]);
            end
        end
    end

    // scores: sum the 16 products of each lane (L+1 -> L+2), accumulate over the
    // head's words at L+2
    logic signed [SCORE_WIDTH-1:0] dot [0:LANES-1];
    logic signed [SCORE_WIDTH-1:0] partial_next [0:LANES-1];
    if (PIPELINED_DOT != 0) begin : gen_dot_pipeline
        // Truncation commutes with modular addition; use the shared 24-bit sum.
        for (genvar c=0;c<LANES;c++) assign dot[c] = SCORE_WIDTH'(mac_dot[c]);
    end else begin : gen_dot_legacy
        always_ff @(posedge clk) begin
            for (int c = 0; c < LANES; c++) begin
                logic signed [SCORE_WIDTH-1:0] sum;
                sum = '0;
                for (int r = 0; r < 16; r++) sum = sum + SCORE_WIDTH'(mac_product[c][r]);
                dot[c] <= sum;
            end
        end
    end
    always_comb begin
        for (int c = 0; c < LANES; c++) begin
            partial_next[c] = (s_word[D] == '0) ? dot[c] : partial[c] + dot[c];
        end
    end

    // exponentials of key e_key (score row arrived at e1), every lane
    (* keep = (FABRIC_SCORE_DISTANCE!=0 ? "true" : "false"), dont_touch = (FABRIC_SCORE_DISTANCE!=0 ? "true" : "false") *)
    logic [SCORE_WIDTH-1:0] e_distance [0:LANES-1];
    logic [SCORE_WIDTH+17-1:0] e_product [0:LANES-1];      // one DSP48E1 per lane
    logic [SCORE_WIDTH+17-1:0] e_index [0:LANES-1];
    logic [15:0] exponent_value [0:LANES-1];
    if (EXP_TABLE_IN_BRAM != 0) begin : gen_exp_bram
        for (genvar c = 0; c < LANES; c++) begin : gen_lane
            (* ram_style = "block" *) logic [15:0] exp_table [0:EXP_STEPS-1];
            logic [15:0] table_value;
            logic zero;
            // Keep the saturation flag parallel to the synchronous RAM read.
            // Both reach e5; no change to EXP_DEPTH, row tags or total updates.
            always_ff @(posedge clk) begin
                if (state_reg == TABLE_WRITE)
                    exp_table[{beat_reg[4:0], word_reg[2:0]}] <= table_beat[16 * word_reg[2:0] +: 16];
                table_value <= exp_table[e_index[c][7:0]];
                zero <= e_index[c] >= EXP_STEPS - 1;
            end
            assign exponent_value[c] = zero ? 16'd0 : table_value;
        end
    end else begin : gen_exp_lut
        (* ram_style = "distributed" *) logic [15:0] exp_table [0:LANES-1][0:EXP_STEPS-1];
        always_ff @(posedge clk) begin
            for (int c = 0; c < LANES; c++) begin
                if (state_reg == TABLE_WRITE)
                    exp_table[c][{beat_reg[4:0], word_reg[2:0]}] <= table_beat[16 * word_reg[2:0] +: 16];
                exponent_value[c] <= (e_index[c] >= EXP_STEPS - 1) ? 16'd0 : exp_table[c][e_index[c][7:0]];
            end
        end
    end
    always_ff @(posedge clk) begin
        for (int c = 0; c < LANES; c++) begin
            logic [SCORE_WIDTH+17-1:0] index;
            e_distance[c] <= SCORE_WIDTH'(maximum[c] - $signed(score_word[SCORE_WIDTH*c +: SCORE_WIDTH]));
            e_product[c] <= e_distance[c] * softmax_multiplier;
            index = e_product[c];
            if (softmax_shift != '0) begin           // (p + 2^(S-1)) >> S, rounding in the fabric
                index = ((index >> (softmax_shift - 6'd1)) + 1) >> 1;
            end
            e_index[c] <= index;
        end
    end

    if (LOCAL_QUERY_REGISTERS != 0) begin : gen_query_distribution
        // Register decoded write enables beside the data. A global delayed word
        // index feeding thousands of query FF clock enables was the routed
        // bottleneck; each static lane/word now has a local registered enable.
        for (genvar g = 0; g < (LANES + 3) / 4; g++) begin : gen_group
            (* keep = "true", max_fanout = 8 *) logic [127:0] data_reg;
            always_ff @(posedge clk)
                if (s_q[L] && int'(s_lane[L]) / 4 == g) data_reg <= query_group_data[g];
            for (genvar c = g*4; c < (g+1)*4 && c < LANES; c++) begin : gen_lane
                for (genvar w = 0; w < MAX_WORDS; w++) begin : gen_word
                    (* keep = "true", max_fanout = 16 *) logic [7:0] write_enable_reg;
                    for (genvar part = 0; part < 8; part++) begin : gen_control
                        always_ff @(posedge clk) begin
                            if (reset) write_enable_reg[part] <= 1'b0;
                            else write_enable_reg[part] <= s_q[L] &&
                                s_lane[L] == LANE_WIDTH'(c) && s_word[L] == 8'(w);
                        end
                        always_ff @(posedge clk)
                            if (write_enable_reg[part])
                                for (int r = part*2; r < part*2+2; r++)
                                    query[c][w][r] <= $signed(data_reg[8*r +: 8]);
                    end
                end
            end
        end
    end else begin : gen_query_default
        always_ff @(posedge clk)
            if (s_q[L]) for (int r = 0; r < 16; r++)
                query[s_lane[L]][s_word[L]][r] <= $signed(q_data[8*r +: 8]);
    end

    always_ff @(posedge clk) begin
        if (state_reg == TABLE_RECEIVE && read_valid) begin
            table_beat <= read_data;
            table_last <= read_last;
        end

        if (s_k[D]) begin
            for (int c = 0; c < LANES; c++) begin
                partial[c] <= partial_next[c];
                if (s_last[D]) begin
                    if (s_key[D] == '0 || partial_next[c] > maximum[c]) begin
                        maximum[c] <= partial_next[c];
                    end
                end
            end
        end
        if (state_reg == SCORE_FLUSH) begin
            for (int c = 0; c < LANES; c++) total[c] <= '0;
        end
        if (e_valid[EXP_DEPTH]) begin
            for (int c = 0; c < LANES; c++) begin
                total[c] <= total[c] + DIVIDER_WIDTH'(exponent_value[c]);
            end
        end
    end

    if (LOCAL_ACCUMULATOR_CONTROLS != 0) begin : gen_local_accumulators
        // Two dimensions per bank: local address/first-key/write controls replace
        // the shared word-index and valid nets that had tens of thousands of loads.
        // Capture from P-1 in parallel with the existing P tags; no added MAC or
        // read-modify-write latency, including consecutive updates to one-word heads.
        for (genvar c = 0; c < LANES; c++) begin : gen_lane
            for (genvar b = 0; b < 8; b++) begin : gen_bank
                localparam integer BANK_BITS = 2 * ACCUMULATOR_WIDTH;
                (* keep = "true", max_fanout = 256 *) logic [WORD_BITS-1:0] read_word_reg, output_word_reg;
                (* keep = "true", max_fanout = 64 *) logic first_key_reg;
                logic [BANK_BITS-1:0] old_value, new_value;
                always_ff @(posedge clk) begin
                    // Shared-read RAM changes its registered address only after
                    // all weighted updates drain. Capture word_next on entry
                    // to WRITE, so its first context read keeps existing timing.
                    if (LOCAL_ACCUMULATOR_CONTROLS == 3 &&
                        (state_next == WRITE || state_reg == WRITE_FLUSH))
                        read_word_reg <= word_next[WORD_BITS-1:0];
                    else read_word_reg <= s_word[P-1][WORD_BITS-1:0];
                    first_key_reg <= s_key[P-1] == '0;
                    // Same next value and edge as word_reg; output reads keep
                    // their existing latency without a global wide-mux selector.
                    output_word_reg <= reset ? '0 : word_next[WORD_BITS-1:0];
                end
                for (genvar r = 0; r < 2; r++) begin : gen_dimension
                    assign new_value[r*ACCUMULATOR_WIDTH +: ACCUMULATOR_WIDTH] =
                        (first_key_reg ? ACCUMULATOR_WIDTH'(0) : old_value[r*ACCUMULATOR_WIDTH +: ACCUMULATOR_WIDTH])
                        + ACCUMULATOR_WIDTH'(mac_product[c][2*b+r]);
                end
                if (LOCAL_ACCUMULATOR_CONTROLS == 2 || LOCAL_ACCUMULATOR_CONTROLS == 3) begin : gen_lutram
                    // Two asynchronous reads, one synchronous dynamic write.
                    // No data reset: first-key clears each consumed accumulator.
                    // Tags are captured at P-1 as in mode 1; consecutive writes
                    // to a one-word head still see the prior edge's updated sum.
                    (* ram_style = "distributed" *) logic [BANK_BITS-1:0] memory [0:MAX_WORDS-1];
                    (* keep = "true", max_fanout = 64 *) logic write_valid_reg;
                    always_ff @(posedge clk) begin
                        write_valid_reg <= !reset && s_v[P-1];
                        if (write_valid_reg) memory[read_word_reg] <= new_value;
                    end
                    assign old_value = memory[read_word_reg];
                    if (LOCAL_ACCUMULATOR_CONTROLS == 3) begin : gen_shared_read
                        assign accumulator_out[BANK_BITS * (8*c+b) +: BANK_BITS] = old_value;
`ifndef SYNTHESIS
                        always @(posedge clk)
                            if (!reset && write_valid_reg &&
                                (state_reg == WRITE || state_reg == WRITE_FLUSH))
                                $fatal(1,"Shared accumulator read switched before writes drained");
`endif
                    end else begin : gen_dual_read
                        assign accumulator_out[BANK_BITS * (8*c+b) +: BANK_BITS] = memory[output_word_reg];
                    end
                end else begin : gen_registers
                    logic [BANK_BITS-1:0] memory [0:MAX_WORDS-1];
                    (* keep = "true", max_fanout = 64 *) logic [MAX_WORDS-1:0] write_enable_reg;
                    always_ff @(posedge clk)
                        for (int w = 0; w < MAX_WORDS; w++)
                            write_enable_reg[w] <= !reset && s_v[P-1] && s_word[P-1] == 8'(w);
                    assign old_value = memory[read_word_reg];
                    for (genvar w = 0; w < MAX_WORDS; w++) begin : gen_word
                        always_ff @(posedge clk)
                            if (write_enable_reg[w]) memory[w] <= new_value;
                    end
                    assign accumulator_out[BANK_BITS * (8*c+b) +: BANK_BITS] = memory[output_word_reg];
                end
            end
        end
    end else begin : gen_default_accumulators
        logic [ROW_BITS-1:0] memory [0:MAX_WORDS-1];
        logic [ROW_BITS-1:0] old_value, new_value;
        assign old_value = memory[s_word[P][WORD_BITS-1:0]];
        assign accumulator_out = memory[word_reg[WORD_BITS-1:0]];
        always_comb begin
            for (int c = 0; c < LANES; c++) begin
                for (int r = 0; r < 16; r++) begin
                    new_value[ACCUMULATOR_WIDTH * (16 * c + r) +: ACCUMULATOR_WIDTH] =
                        ((s_key[P] == '0) ? ACCUMULATOR_WIDTH'(0)
                                        : old_value[ACCUMULATOR_WIDTH * (16 * c + r) +: ACCUMULATOR_WIDTH])
                        + ACCUMULATOR_WIDTH'(mac_product[c][r]);
                end
            end
        end
        always_ff @(posedge clk)
            if (s_v[P]) memory[s_word[P][WORD_BITS-1:0]] <= new_value;
    end

    // one divider per lane: r = 2^24 / total
    logic [LANES-1:0] divider_done;
    for (genvar c = 0; c < LANES; c++) begin : gen_divider
        logic divider_busy;
        logic [DIVIDER_WIDTH-1:0] quotient;
        sequential_divider #(.WIDTH(DIVIDER_WIDTH)) divider_inst (
            .clk(clk),
            .reset(reset),
            .start(state_reg == DIVIDE),
            .dividend(DIVIDER_WIDTH'(1) << 24),
            .divisor(total[c]),
            .busy(divider_busy),
            .done(divider_done[c]),
            .quotient(quotient)
        );
        always_ff @(posedge clk) begin
            if (divider_done[c]) reciprocal[c] <= 9'(quotient);   // <= 256 for a real row
        end
    end
    assign dividers_done = divider_done[0];      // all lanes finish together

    always_comb begin
        score_write = s_k[D] && s_last[D];
        exponent_write = e_valid[EXP_DEPTH];
        for (int c = 0; c < LANES; c++) begin
            score_write_word[SCORE_WIDTH*c +: SCORE_WIDTH] = partial_next[c];
            exponent_write_word[16*c +: 16] = exponent_value[c];
        end
    end

    // context rows out: one word (16 elements) of one lane every 4 clocks,
    // CONTEXT_LANES requantisers (ACCUMULATOR_WIDTH x 17 bits, one DSP48E1 each)
    logic w_valid;
    logic [BUFFER_ADDRESS_WIDTH-1:0] w_address;
    logic [127:0] w_data;
    logic [1:0] w_part [1:WRITE_DEPTH];
    logic [BUFFER_ADDRESS_WIDTH-1:0] w_word_address [1:WRITE_DEPTH];
    (* keep = (FABRIC_CONTEXT_CAPTURE!=0 ? "true" : "false"), dont_touch = (FABRIC_CONTEXT_CAPTURE!=0 ? "true" : "false") *)
    logic signed [ACCUMULATOR_WIDTH-1:0] w_sum [0:CONTEXT_LANES-1];
    logic signed [ACCUMULATOR_WIDTH+18-1:0] w_product [0:CONTEXT_LANES-1];
    logic signed [ACCUMULATOR_WIDTH+18-1:0] w_rounded [0:CONTEXT_LANES-1];

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            w_stage <= '0;
            w_valid <= 1'b0;
        end else begin
            w_stage <= WRITE_DEPTH'({w_stage, state_reg == WRITE});
            w_valid <= w_stage[WRITE_DEPTH - 1] && (w_part[WRITE_DEPTH - 1] == 2'd3);
        end
    end

    always_ff @(posedge clk) begin
        w_part[1] <= part_reg;
        w_word_address[1] <= q_address;
        for (int i = 2; i <= WRITE_DEPTH; i++) begin
            w_part[i] <= w_part[i-1];
            w_word_address[i] <= w_word_address[i-1];
        end
        for (int e = 0; e < CONTEXT_LANES; e++) begin
            // natural-width operands so the product is one DSP48E1; the rounding
            // (p + 2^(S-1)) >>> S is done as ((p >>> (S-1)) + 1) >>> 1 in the fabric
            logic signed [ACCUMULATOR_WIDTH+18-1:0] product;
            logic signed [63:0] y;
            w_sum[e] <= $signed(accumulator_out[ACCUMULATOR_WIDTH * (16 * lane_reg + 4 * part_reg + e)
                                                +: ACCUMULATOR_WIDTH]);
            w_product[e] <= w_sum[e] * $signed({1'b0, context_multiplier});
            product = w_product[e];
            if (context_shift != '0) begin
                product = ((product >>> (context_shift - 6'd1)) + 1) >>> 1;
            end
            w_rounded[e] <= product;
            y = clamp(64'(w_rounded[e]), -64'sd127, 64'sd127);
            if (w_stage[WRITE_DEPTH - 1]) begin
                w_data[8 * (4 * w_part[WRITE_DEPTH - 1] + e) +: 8] <= y[7:0];
            end
        end
        w_address <= w_word_address[WRITE_DEPTH - 1];
    end

    assign destination_write = w_valid;
    assign destination_address = w_address;
    assign destination_data = w_data;
    assign destination_enable = 16'hFFFF;

endmodule
