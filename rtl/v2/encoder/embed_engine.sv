// EMBED instruction: token ids -> INT16 residual rows (R), per token t and element d
//
//     r = clamp(clamp(requant(word[id_t][d], Mw[d], Sw), +-32767)
//               + clamp(requant(pos[t][d], Mp[d], Sp), +-32767) + type[d], +-32767)
//
// Exactly ImageMachine's EMBED. The token ids are INT16 elements of the source buffer
// (X, written by the host before the run: id t is element t mod 8 of word t / 8). The
// per-dimension vectors type (INT32), Mw and Mp (< 2^17, compile_image checks) are
// fetched once; then for every token the word row (one request at word + id * stride)
// and the position row (pos + t * stride) are fetched, H / 16 beats each, and
// LANES elements per clock go out to R. Memory-bound by design: about
// 2 * (latency + H / 16) + H / LANES clocks per token, a few percent of one layer.
(* use_dsp = "no" *)            // memory-bound; the DSP48E1s are for the MAC array
module embed_engine
    import encoder_pkg::*;
#(
    parameter integer MAX_WIDTH = 384,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic done,

    input logic [ADDRESS_WIDTH-1:0] word_address,
    input logic [15:0] word_stride,
    input logic [ADDRESS_WIDTH-1:0] position_address,
    input logic [15:0] position_stride,
    input logic [ADDRESS_WIDTH-1:0] type_address,
    input logic [ADDRESS_WIDTH-1:0] word_multiplier_address,
    input logic [5:0] word_shift,
    input logic [ADDRESS_WIDTH-1:0] position_multiplier_address,
    input logic [5:0] position_shift,
    input logic [15:0] width,                    // H, multiple of 16
    input logic [7:0] token_count,

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic [BUFFER_ADDRESS_WIDTH-1:0] source_address,     // token ids (INT16)
    input logic [127:0] source_data,

    output logic destination_write,                             // INT16 rows
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    localparam integer LANES = 2;                // elements per clock (4 products, LUTs)
    localparam integer ROW_WORDS = MAX_WIDTH / 16;
    localparam integer VECTOR_WORDS = MAX_WIDTH / 4;

    typedef enum logic [3:0] {
        IDLE,
        VECTOR_REQUEST,
        VECTOR_RECEIVE,
        ID_READ,
        ID_WAIT,
        ROW_ADDRESS,
        WORD_REQUEST,
        WORD_RECEIVE,
        POSITION_REQUEST,
        POSITION_RECEIVE,
        COMPUTE,
        FLUSH,
        FINISH
    } state_t;

    state_t state_reg;
    logic [15:0] width_reg;
    logic [7:0] tokens_reg, token_reg;
    logic [1:0] vector_reg;                      // 0 type, 1 Mw, 2 Mp
    logic [15:0] beat_reg;
    logic [15:0] group_reg;                      // LANES-element group within the row
    logic [3:0] wait_reg;
    logic [15:0] id_reg;
    logic [ADDRESS_WIDTH-1:0] word_row_address, position_row_address;
    logic pipeline_busy;

    // fetched once per instruction, and per token
    (* ram_style = "distributed" *) logic [127:0] type_ram [0:VECTOR_WORDS-1];
    (* ram_style = "distributed" *) logic [127:0] word_multiplier_ram [0:VECTOR_WORDS-1];
    (* ram_style = "distributed" *) logic [127:0] position_multiplier_ram [0:VECTOR_WORDS-1];
    (* ram_style = "distributed" *) logic [127:0] word_row [0:ROW_WORDS-1];
    (* ram_style = "distributed" *) logic [127:0] position_row [0:ROW_WORDS-1];

    always_comb begin
        read_request_valid = 1'b0;
        read_request_address = '0;
        read_request_beats = BEATS_WIDTH'(width_reg >> 4);
        read_ready = 1'b0;
        case (state_reg)
            VECTOR_REQUEST: begin
                read_request_valid = 1'b1;
                read_request_beats = BEATS_WIDTH'(width_reg >> 2);
                read_request_address = (vector_reg == 2'd0) ? type_address
                                     : (vector_reg == 2'd1) ? word_multiplier_address
                                                            : position_multiplier_address;
            end
            WORD_REQUEST: begin
                read_request_valid = 1'b1;
                read_request_address = word_row_address;
            end
            POSITION_REQUEST: begin
                read_request_valid = 1'b1;
                read_request_address = position_row_address;
            end
            VECTOR_RECEIVE, WORD_RECEIVE, POSITION_RECEIVE: read_ready = 1'b1;
            default: ;
        endcase
    end

    assign source_address = BUFFER_ADDRESS_WIDTH'(token_reg >> 3);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            width_reg <= '0;
            tokens_reg <= '0;
            token_reg <= '0;
            vector_reg <= '0;
            beat_reg <= '0;
            group_reg <= '0;
            wait_reg <= '0;
            id_reg <= '0;
            word_row_address <= '0;
            position_row_address <= '0;
        end else begin
            case (state_reg)
                IDLE: begin
                    if (start) begin
                        width_reg <= width;
                        tokens_reg <= token_count;
                        token_reg <= '0;
                        vector_reg <= '0;
                        state_reg <= VECTOR_REQUEST;
                    end
                end
                VECTOR_REQUEST: begin
                    if (read_request_ready) begin
                        beat_reg <= '0;
                        state_reg <= VECTOR_RECEIVE;
                    end
                end
                VECTOR_RECEIVE: begin
                    if (read_valid) begin
                        beat_reg <= beat_reg + 1'b1;
                        if (read_last) begin
                            vector_reg <= vector_reg + 1'b1;
                            state_reg <= (vector_reg == 2'd2) ? ID_READ : VECTOR_REQUEST;
                        end
                    end
                end
                ID_READ: begin                   // source_address is presented now
                    wait_reg <= 4'(READ_LATENCY - 1);
                    state_reg <= ID_WAIT;
                end
                ID_WAIT: begin
                    if (wait_reg == '0) begin
                        id_reg <= source_data[16 * token_reg[2:0] +: 16];
                        state_reg <= ROW_ADDRESS;
                    end else begin
                        wait_reg <= wait_reg - 1'b1;
                    end
                end
                ROW_ADDRESS: begin
                    word_row_address <= word_address + ADDRESS_WIDTH'(id_reg * word_stride);
                    position_row_address <= position_address + ADDRESS_WIDTH'(token_reg * position_stride);
                    state_reg <= WORD_REQUEST;
                end
                WORD_REQUEST: begin
                    if (read_request_ready) begin
                        beat_reg <= '0;
                        state_reg <= WORD_RECEIVE;
                    end
                end
                WORD_RECEIVE: begin
                    if (read_valid) begin
                        beat_reg <= beat_reg + 1'b1;
                        if (read_last) state_reg <= POSITION_REQUEST;
                    end
                end
                POSITION_REQUEST: begin
                    if (read_request_ready) begin
                        beat_reg <= '0;
                        state_reg <= POSITION_RECEIVE;
                    end
                end
                POSITION_RECEIVE: begin
                    if (read_valid) begin
                        beat_reg <= beat_reg + 1'b1;
                        if (read_last) begin
                            group_reg <= '0;
                            state_reg <= COMPUTE;
                        end
                    end
                end
                COMPUTE: begin
                    group_reg <= group_reg + 1'b1;
                    if (group_reg == (width_reg >> 1) - 1'b1) state_reg <= FLUSH;
                end
                FLUSH: begin
                    // the next token's rows may overwrite word_row / position_row only
                    // after the last group has read them (stage 1)
                    if (!pipeline_busy) begin
                        if (token_reg == tokens_reg - 1'b1) begin
                            state_reg <= FINISH;
                        end else begin
                            token_reg <= token_reg + 1'b1;
                            state_reg <= ID_READ;
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

    always_ff @(posedge clk) begin
        if (read_valid && read_ready) begin
            case (state_reg)
                VECTOR_RECEIVE: begin
                    case (vector_reg)
                        2'd0: type_ram[beat_reg] <= read_data;
                        2'd1: word_multiplier_ram[beat_reg] <= read_data;
                        default: position_multiplier_ram[beat_reg] <= read_data;
                    endcase
                end
                WORD_RECEIVE: word_row[beat_reg] <= read_data;
                POSITION_RECEIVE: position_row[beat_reg] <= read_data;
                default: ;
            endcase
        end
    end

    // ------------------------------------------------------------------ compute
    // c0 group issued; 1 operands; 2 products; 3 rounded, clamped terms; 4 sum -> R

    localparam int D = 4;
    logic [D:1] s_valid;
    logic [15:0] s_group [1:D];
    logic [7:0] s_token [1:D];

    always_ff @(posedge clk or posedge reset) begin
        if (reset) s_valid <= '0;
        else s_valid <= D'({s_valid, state_reg == COMPUTE});
    end
    always_ff @(posedge clk) begin
        s_group[1] <= group_reg;
        s_token[1] <= token_reg;
        for (int i = 2; i <= D; i++) begin
            s_group[i] <= s_group[i-1];
            s_token[i] <= s_token[i-1];
        end
    end
    assign pipeline_busy = |s_valid;

    logic signed [7:0] w_value [0:LANES-1], p_value [0:LANES-1];
    logic [16:0] w_multiplier [0:LANES-1], p_multiplier [0:LANES-1];
    logic signed [31:0] type_value [0:LANES-1], type_held [0:LANES-1];
    (* use_dsp = "no" *) logic signed [25:0] w_product [0:LANES-1];
    (* use_dsp = "no" *) logic signed [25:0] p_product [0:LANES-1];
    logic signed [16:0] w_term [0:LANES-1], p_term [0:LANES-1];
    logic signed [31:0] type_term [0:LANES-1];
    logic [LANES*16-1:0] out_pair;
    logic [BUFFER_ADDRESS_WIDTH-1:0] out_address;
    logic [15:0] out_enable;

    always_ff @(posedge clk) begin
        for (int e = 0; e < LANES; e++) begin
            logic [15:0] d;
            logic signed [25:0] w_rounded, p_rounded;
            logic signed [33:0] sum;
            d = 16'(group_reg * LANES + e);
            // stage 1: operands of element d
            w_value[e] <= $signed(word_row[d >> 4][8 * d[3:0] +: 8]);
            p_value[e] <= $signed(position_row[d >> 4][8 * d[3:0] +: 8]);
            w_multiplier[e] <= word_multiplier_ram[d >> 2][32 * d[1:0] +: 17];
            p_multiplier[e] <= position_multiplier_ram[d >> 2][32 * d[1:0] +: 17];
            type_value[e] <= $signed(type_ram[d >> 2][32 * d[1:0] +: 32]);
            // stage 2: products
            w_product[e] <= 26'(w_value[e]) * 26'($signed({1'b0, w_multiplier[e]}));
            p_product[e] <= 26'(p_value[e]) * 26'($signed({1'b0, p_multiplier[e]}));
            type_held[e] <= type_value[e];
            // stage 3: requantised, clamped terms
            w_rounded = (word_shift == '0) ? w_product[e]
                        : (w_product[e] + (26'sd1 <<< (word_shift - 6'd1))) >>> word_shift;
            p_rounded = (position_shift == '0) ? p_product[e]
                        : (p_product[e] + (26'sd1 <<< (position_shift - 6'd1))) >>> position_shift;
            w_term[e] <= 17'(clamp(64'(w_rounded), -64'sd32767, 64'sd32767));
            p_term[e] <= 17'(clamp(64'(p_rounded), -64'sd32767, 64'sd32767));
            type_term[e] <= type_held[e];
            // stage 4: sum, clamp
            sum = 34'(w_term[e]) + 34'(p_term[e]) + 34'(type_term[e]);
            out_pair[16*e +: 16] <= 16'(clamp(64'(sum), -64'sd32767, 64'sd32767));
        end
        // R row t: width / 8 INT16 words; the pair's 4 bytes at lane (first mod 8) * 2
        begin
            logic [15:0] first;
            first = 16'(s_group[D-1] * LANES);
            out_address <= BUFFER_ADDRESS_WIDTH'(s_token[D-1] * (width_reg >> 3) + (first >> 3));
            out_enable <= 16'((1 << (2 * LANES)) - 1) << (2 * first[2:0]);
        end
    end

    assign destination_write = s_valid[D];
    assign destination_address = out_address;
    assign destination_data = {(128 / (16 * LANES)){out_pair}};
    assign destination_enable = out_enable;

endmodule
