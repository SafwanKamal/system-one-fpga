// ADD_SKIP instruction: r = clamp(a + clamp(requant(x, M, S), +-32767), +-32767)
// for every element of every token; a and r are INT16 rows (width / 8 words), x is
// an INT8 row (width / 16 words). Eight elements per clock: one word of a, half a
// word of x, one full word of r.
(* use_dsp = "no" *)            // eight INT8 x 17-bit products: LUTs, the DSPs go to the MAC array
module add_skip_engine
    import encoder_pkg::*;
#(
    parameter integer READ_LATENCY = encoder_pkg::READ_LATENCY,
    parameter integer MAX_TOKENS = 128,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic done,

    input logic [16:0] multiplier,               // < 2^17 (compile_image checks)
    input logic [5:0] shift,
    input logic [15:0] width,                    // multiple of 16
    input logic [7:0] token_count,

    output logic [BUFFER_ADDRESS_WIDTH-1:0] a_address,     // INT16 source (src)
    input logic [127:0] a_data,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] x_address,     // INT8 skip (src2)
    input logic [127:0] x_data,

    output logic destination_write,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    typedef enum logic [1:0] {
        IDLE,
        RUN,
        FLUSH,
        FINISH
    } state_t;

    state_t state_reg, state_next;
    logic [7:0] token_reg, token_next;
    logic [7:0] word_reg, word_next;           // INT16 word within the row
    logic [7:0] row_words_reg, row_words_next;
    logic [7:0] tokens_reg, tokens_next;
    // Retain the carry before halving even if the exported A address wraps.
    localparam integer CURSOR_WIDTH = BUFFER_ADDRESS_WIDTH < 16 ? 16 : BUFFER_ADDRESS_WIDTH + 1;
    logic [CURSOR_WIDTH-1:0] word_cursor;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            token_reg <= '0;
            word_reg <= '0;
            row_words_reg <= '0;
            tokens_reg <= '0;
        end else begin
            state_reg <= state_next;
            token_reg <= token_next;
            word_reg <= word_next;
            row_words_reg <= row_words_next;
            tokens_reg <= tokens_next;
        end
    end

    logic issue;
    logic pipeline_busy;

    always_comb begin
        state_next = state_reg;
        token_next = token_reg;
        word_next = word_reg;
        row_words_next = row_words_reg;
        tokens_next = tokens_reg;
        issue = 1'b0;
        case (state_reg)
            IDLE: begin
                if (start) begin
                    token_next = '0;
                    word_next = '0;
                    row_words_next = 8'(width >> 3);
                    tokens_next = token_count;
                    state_next = RUN;
                end
            end
            RUN: begin
                issue = 1'b1;
                word_next = word_reg + 1'b1;
                if (word_reg == row_words_reg - 1'b1) begin
                    word_next = '0;
                    token_next = token_reg + 1'b1;
                    if (token_reg == tokens_reg - 1'b1) begin
                        state_next = FLUSH;
                    end
                end
            end
            FLUSH: begin
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

    // Legal rows have an even word count (width is a multiple of 16).
    // Sequential issue makes token*row_words+word a simple cursor; the INT8
    // address is half the INT16 address. Keep row/token counters for termination.
    always_ff @(posedge clk or posedge reset) begin
        if (reset) word_cursor <= '0;
        else if (state_reg == IDLE && start) word_cursor <= '0;
        else if (issue) word_cursor <= word_cursor + 1'b1;
    end
    assign a_address = BUFFER_ADDRESS_WIDTH'(word_cursor);
    assign x_address = BUFFER_ADDRESS_WIDTH'(word_cursor >> 1);

    // c0 issue; cL (L = READ_LATENCY) data; L+1 skip product; L+2 rounded skip;
    // L+3 sum -> destination
    localparam int L = READ_LATENCY;
    localparam int D = L + 3;
    logic [D:1] s_valid;
    logic [BUFFER_ADDRESS_WIDTH-1:0] s_address [1:D];
    logic s_high [1:L];

    always_ff @(posedge clk or posedge reset) begin
        if (reset) s_valid <= '0;
        else s_valid <= {s_valid[D-1:1], issue};
    end

    always_ff @(posedge clk) begin
        s_address[1] <= a_address;
        s_high[1] <= word_reg[0];
        for (int i = 2; i <= D; i++) s_address[i] <= s_address[i-1];
        for (int i = 2; i <= L; i++) s_high[i] <= s_high[i-1];
    end

    assign pipeline_busy = |s_valid;

    logic signed [25:0] product [0:7];          // INT8 x 17-bit unsigned
    logic signed [25:0] rounded [0:7];
    logic [127:0] a_held [L+1:L+2];
    logic [127:0] out_data;

    always_ff @(posedge clk) begin
        a_held[L+1] <= a_data;
        a_held[L+2] <= a_held[L+1];
        for (int e = 0; e < 8; e++) begin
            logic signed [15:0] skip;
            logic signed [16:0] sum;
            product[e] <= 26'($signed(x_data[8 * (8 * s_high[L] + e) +: 8])) * 26'($signed({1'b0, multiplier}));
            if (shift != '0) begin
                rounded[e] <= (product[e] + (26'sd1 <<< (shift - 6'd1))) >>> shift;
            end else begin
                rounded[e] <= product[e];
            end
            // Exact widths: the first clamp is signed 26 -> 16; adding a
            // signed INT16 residual gives [-65535,65534], which fits 17 bits.
            // Preserve the existing pipeline and asymmetric saturation bounds.
            // The legal negative range excludes -32768. Classify sign
            // extension and the low-bit zero case using reductions, avoiding
            // serial signed magnitude comparisons around the residual adder.
            if (rounded[e][25])
                skip = (&rounded[e][25:15]) && (|rounded[e][14:0]) ?
                       rounded[e][15:0] : 16'h8001;
            else
                skip = (|rounded[e][25:15]) ? 16'h7fff : rounded[e][15:0];
            sum = 17'($signed(a_held[L+2][16*e +: 16])) + 17'(skip);
            if (sum[16])
                out_data[16*e +: 16] <= sum[15] && (|sum[14:0]) ? sum[15:0] : 16'h8001;
            else
                out_data[16*e +: 16] <= sum[15] ? 16'h7fff : sum[15:0];
        end
    end

    assign destination_write = s_valid[D];
    assign destination_address = s_address[D];
    assign destination_data = out_data;
    assign destination_enable = 16'hFFFF;

endmodule
