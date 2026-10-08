// POOL instruction (heads on the FPGA): rows [first, first + count) of an INT8 source
// buffer -> one INT8 row `out` of the destination buffer
//
//     pooled[d] = (sum_r x[r][d] * recip[count] + 2^15) >> 16
//
// Exactly ImageMachine's POOL and the head pooling of IntEncoder.head_logits. recip
// (UINT32 <= 2^16) is one entry of the image's reciprocal table, read once. Per word
// of the row (16 elements): the rows are read and summed 16 elements per clock, then
// the 16 sums are scaled one per clock on one multiplier. About width / 16 *
// (count + 24) clocks; heads are a few rows, this is negligible next to the encoder.
module pool_engine
    import encoder_pkg::*;
#(
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic done,

    input logic [15:0] first_row,
    input logic [15:0] row_count,                // >= 1
    input logic [15:0] out_row,
    input logic [ADDRESS_WIDTH-1:0] recip_address,
    input logic [15:0] width,                    // multiple of 16

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic [BUFFER_ADDRESS_WIDTH-1:0] source_address,     // INT8 rows
    input logic [127:0] source_data,

    output logic destination_write,                             // INT8 row
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    typedef enum logic [2:0] {
        IDLE,
        RECIP_REQUEST,
        RECIP_RECEIVE,
        SUM,
        SUM_FLUSH,
        SCALE,
        SCALE_FLUSH,
        FINISH
    } state_t;

    state_t state_reg;
    logic [15:0] row_words_reg, first_reg, count_reg, out_reg;
    logic [15:0] word_reg, row_reg;
    logic [3:0] element_reg;
    logic [ADDRESS_WIDTH-1:0] recip_entry;
    logic [16:0] recip_reg;                      // <= 2^16
    logic signed [15:0] sum [0:15];              // |sum| <= MAX_TOKENS * 127
    logic [127:0] pooled_word;
    logic pipeline_busy;

    assign recip_entry = recip_address + ADDRESS_WIDTH'({row_count, 2'b00});

    always_comb begin
        read_request_valid = (state_reg == RECIP_REQUEST);
        read_request_address = {recip_entry[ADDRESS_WIDTH-1:4], 4'b0000};
        read_request_beats = BEATS_WIDTH'(1);
        read_ready = (state_reg == RECIP_RECEIVE);
    end

    assign source_address = BUFFER_ADDRESS_WIDTH'((first_reg + row_reg) * row_words_reg + word_reg);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            row_words_reg <= '0;
            first_reg <= '0;
            count_reg <= '0;
            out_reg <= '0;
            word_reg <= '0;
            row_reg <= '0;
            element_reg <= '0;
            recip_reg <= '0;
        end else begin
            case (state_reg)
                IDLE: begin
                    if (start) begin
                        row_words_reg <= width >> 4;
                        first_reg <= first_row;
                        count_reg <= row_count;
                        out_reg <= out_row;
                        word_reg <= '0;
                        state_reg <= RECIP_REQUEST;
                    end
                end
                RECIP_REQUEST: if (read_request_ready) state_reg <= RECIP_RECEIVE;
                RECIP_RECEIVE: begin
                    if (read_valid) begin
                        recip_reg <= read_data[32 * recip_entry[3:2] +: 17];
                        row_reg <= '0;
                        state_reg <= SUM;
                    end
                end
                SUM: begin
                    row_reg <= row_reg + 1'b1;
                    if (row_reg == count_reg - 1'b1) state_reg <= SUM_FLUSH;
                end
                SUM_FLUSH: begin
                    if (!pipeline_busy) begin
                        element_reg <= '0;
                        state_reg <= SCALE;
                    end
                end
                SCALE: begin
                    element_reg <= element_reg + 1'b1;
                    if (element_reg == 4'd15) state_reg <= SCALE_FLUSH;
                end
                SCALE_FLUSH: begin
                    if (!pipeline_busy) begin       // the word has been written
                        if (word_reg == row_words_reg - 1'b1) begin
                            state_reg <= FINISH;
                        end else begin
                            word_reg <= word_reg + 1'b1;
                            row_reg <= '0;
                            state_reg <= SUM;
                        end
                    end
                end
                FINISH: state_reg <= IDLE;
                default: state_reg <= IDLE;
            endcase
        end
    end

    assign busy = (state_reg != IDLE);
    assign done = (state_reg == FINISH);

    // sums: issue in SUM, the word arrives READ_LATENCY clocks later
    localparam int L = READ_LATENCY;
    logic [L:1] s_valid, s_first;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            s_valid <= '0;
            s_first <= '0;
        end else begin
            s_valid <= L'({s_valid, state_reg == SUM});
            s_first <= L'({s_first, row_reg == '0});
        end
    end

    always_ff @(posedge clk) begin
        if (s_valid[L]) begin
            for (int e = 0; e < 16; e++) begin
                logic signed [15:0] v;
                v = 16'($signed(source_data[8*e +: 8]));
                sum[e] <= s_first[L] ? v : sum[e] + v;
            end
        end
    end

    // scale: element e of the word per clock; product (one DSP48E1), then rounding
    logic m1_valid, m2_valid, m2_last;
    logic m1_last;
    logic [3:0] m1_element, m2_element;
    logic signed [33:0] m1_product;
    logic w_valid;
    logic [BUFFER_ADDRESS_WIDTH-1:0] w_address;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            m1_valid <= 1'b0;
            m2_valid <= 1'b0;
            w_valid <= 1'b0;
        end else begin
            m1_valid <= (state_reg == SCALE);
            m2_valid <= m1_valid;
            w_valid <= m2_valid && m2_last;
        end
    end

    always_ff @(posedge clk) begin
        logic signed [33:0] rounded;
        m1_element <= element_reg;
        m1_last <= (element_reg == 4'd15);
        m1_product <= 34'(sum[element_reg]) * 34'($signed({1'b0, recip_reg}));
        m2_element <= m1_element;
        m2_last <= m1_last;
        rounded = (m1_product + 34'sd32768) >>> 16;
`ifndef SYNTHESIS
        if (m1_valid && (rounded > 127 || rounded < -127)) $error("pool: pooled value out of INT8");
`endif
        if (m1_valid) pooled_word[8 * m1_element +: 8] <= rounded[7:0];
        w_address <= BUFFER_ADDRESS_WIDTH'(out_reg * row_words_reg + word_reg);
    end

    assign pipeline_busy = |s_valid | m1_valid | m2_valid | w_valid;

    assign destination_write = w_valid;
    assign destination_address = w_address;
    assign destination_data = pooled_word;
    assign destination_enable = 16'hFFFF;

endmodule
