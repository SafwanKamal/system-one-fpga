// LAYERNORM instruction: INT16 rows (R) -> INT8 rows (X), per token
//
//     mean = floor((2*sum + n) / (2n));  c = r - mean
//     var  = floor(sum(c^2) / n);        std = max(isqrt(var), 1)
//     inv  = floor(2^(F+16) / std);      z = (c*inv + 2^15) >>> 16
//     y    = clamp((z*g + b + 2^(F+7)) >>> (F+8), +-127)
//
// g and b (INT32 per element, g then b, at `parameter_address`) are fetched once
// into local RAM. Per token: one pass for the sum and one for the squares (eight
// elements per clock), three divisions and an integer square root (one bit per
// clock), then NORM_LANES (2) elements per clock out. Exactly ImageMachine._layernorm.
module layernorm_engine
    import encoder_pkg::*;
#(
    parameter integer MAX_WIDTH = 768,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic done,

    input logic [ADDRESS_WIDTH-1:0] parameter_address,
    input logic [15:0] width,                    // n, multiple of 16
    input logic [4:0] fraction,                  // F
    input logic [7:0] token_count,

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic [BUFFER_ADDRESS_WIDTH-1:0] source_address,     // INT16 rows
    input logic [127:0] source_data,

    output logic destination_write,                             // INT8 rows
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    localparam integer DIVIDER_WIDTH = 48;
    localparam integer GROUPS = MAX_WIDTH / 4;
    // elements normalised per clock (2 x two DSP48E1 products each); 1, 2 or 4
    localparam integer NORM_LANES = 2;
    localparam integer NORM_LOG = $clog2(NORM_LANES);

    typedef enum logic [4:0] {
        IDLE,
        PARAMETER_REQUEST,
        PARAMETER_RECEIVE,
        SUM,
        SUM_FLUSH,
        MEAN_DIVIDE,
        MEAN_WAIT,
        SQUARES,
        SQUARES_FLUSH,
        VARIANCE_DIVIDE,
        VARIANCE_WAIT,
        ROOT,
        INVERSE_DIVIDE,
        INVERSE_WAIT,
        NORMALISE,
        NORMALISE_FLUSH,
        FINISH
    } state_t;

    state_t state_reg, state_next;
    logic [15:0] width_reg, width_next;
    logic [7:0] tokens_reg, tokens_next;
    logic [4:0] fraction_reg, fraction_next;
    logic [7:0] token_reg, token_next;
    logic [15:0] index_reg, index_next;       // word (SUM/SQUARES) or group (NORMALISE)
    logic [15:0] beat_reg, beat_next;

    logic signed [47:0] total_reg, total_next;
    logic [47:0] squares_reg, squares_next;
    logic signed [31:0] mean_reg, mean_next;
    logic mean_negative_reg, mean_negative_next;
    logic [47:0] inverse_reg, inverse_next;
    logic [47:0] root_value_reg, root_value_next;   // isqrt: remaining value
    logic [47:0] root_reg, root_next;               // isqrt: result
    logic [47:0] root_bit_reg, root_bit_next;

    logic [127:0] gamma_ram [0:GROUPS-1];          // 4 x INT32 per word
    logic [127:0] beta_ram [0:GROUPS-1];
    logic [127:0] gamma_word, beta_word;

    // divider
    logic divider_start;
    logic [DIVIDER_WIDTH-1:0] divider_dividend, divider_divisor, divider_quotient;
    logic divider_busy, divider_done;

    sequential_divider #(.WIDTH(DIVIDER_WIDTH)) divider_inst (
        .clk(clk),
        .reset(reset),
        .start(divider_start),
        .dividend(divider_dividend),
        .divisor(divider_divisor),
        .busy(divider_busy),
        .done(divider_done),
        .quotient(divider_quotient)
    );

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            width_reg <= '0;
            tokens_reg <= '0;
            fraction_reg <= '0;
            token_reg <= '0;
            index_reg <= '0;
            beat_reg <= '0;
            total_reg <= '0;
            squares_reg <= '0;
            mean_reg <= '0;
            mean_negative_reg <= 1'b0;
            inverse_reg <= '0;
            root_value_reg <= '0;
            root_reg <= '0;
            root_bit_reg <= '0;
        end else begin
            state_reg <= state_next;
            width_reg <= width_next;
            tokens_reg <= tokens_next;
            fraction_reg <= fraction_next;
            token_reg <= token_next;
            index_reg <= index_next;
            beat_reg <= beat_next;
            total_reg <= total_next;
            squares_reg <= squares_next;
            mean_reg <= mean_next;
            mean_negative_reg <= mean_negative_next;
            inverse_reg <= inverse_next;
            root_value_reg <= root_value_next;
            root_reg <= root_next;
            root_bit_reg <= root_bit_next;
        end
    end

    logic issue_sum, issue_squares, issue_normalise;
    logic pipeline_busy;
    logic signed [47:0] numerator;

    // pipeline: c0 issue; cL (L = READ_LATENCY) source word
    //   sum        L: row sum (8 elements) -> L+1 accumulate
    //   squares    L: |c| = |r - mean| -> L+1 partial products -> L+2 c^2
    //              -> L+3 sum of 8 -> L+4 accumulate
    //   normalise  L: c -> L+1 c*inv -> L+2 z -> L+3 z*g -> L+4 + b, rounding
    //              -> L+5 shift, clamp -> L+6 destination
    localparam int L = READ_LATENCY;
    localparam int D = L + 6;
    logic [D:1] s_sum, s_squares, s_normalise;
    logic [15:0] s_index [1:D];
    logic [7:0] s_token [1:D];

    logic signed [18:0] sum_word;                   // 8 x INT16
    logic [34:0] squares_word;                      // 8 x c^2, c^2 < 2^32
    logic [16:0] square_c [0:7];                    // |c|
    // |r| <= 32767 and the mean is a mean of such values, so |c| <= 65534 (17 bits
    // unsigned). The eight squares are built from LUTs, to keep the DSP48E1s for the
    // MAC array, in two clocks: |c| = h*2^9 + l, c^2 = h^2*2^18 + h*l*2^10 + l^2
    (* use_dsp = "no" *) logic [15:0] square_hh [0:7];
    (* use_dsp = "no" *) logic [16:0] square_hl [0:7];
    (* use_dsp = "no" *) logic [17:0] square_ll [0:7];
    logic [31:0] square [0:7];

    always_comb begin
        state_next = state_reg;
        width_next = width_reg;
        tokens_next = tokens_reg;
        fraction_next = fraction_reg;
        token_next = token_reg;
        index_next = index_reg;
        beat_next = beat_reg;
        total_next = total_reg;
        squares_next = squares_reg;
        mean_next = mean_reg;
        mean_negative_next = mean_negative_reg;
        inverse_next = inverse_reg;
        root_value_next = root_value_reg;
        root_next = root_reg;
        root_bit_next = root_bit_reg;

        read_request_valid = 1'b0;
        read_request_address = parameter_address;
        read_request_beats = BEATS_WIDTH'(width_reg >> 1);     // 2n INT32 / 4 per beat
        read_ready = 1'b0;
        issue_sum = 1'b0;
        issue_squares = 1'b0;
        issue_normalise = 1'b0;
        divider_start = 1'b0;
        divider_dividend = '0;
        divider_divisor = '0;
        numerator = 2 * total_reg + 48'(width_reg);

        // accumulate whatever arrives
        if (s_sum[L+1]) begin
            total_next = total_reg + 48'(sum_word);
        end
        if (s_squares[L+4]) begin
            squares_next = squares_reg + 48'(squares_word);
        end

        case (state_reg)
            IDLE: begin
                if (start) begin
                    width_next = width;
                    tokens_next = token_count;
                    fraction_next = fraction;
                    beat_next = '0;
                    state_next = PARAMETER_REQUEST;
                end
            end

            PARAMETER_REQUEST: begin
                read_request_valid = 1'b1;
                if (read_request_ready) begin
                    state_next = PARAMETER_RECEIVE;
                end
            end

            PARAMETER_RECEIVE: begin
                read_ready = 1'b1;
                if (read_valid) begin
                    beat_next = beat_reg + 1'b1;
                    if (read_last) begin
                        token_next = '0;
                        index_next = '0;
                        total_next = '0;
                        state_next = SUM;
                    end
                end
            end

            SUM: begin
                issue_sum = 1'b1;
                index_next = index_reg + 1'b1;
                if (index_reg == (width_reg >> 3) - 1'b1) begin
                    state_next = SUM_FLUSH;
                end
            end

            SUM_FLUSH: begin
                if (!pipeline_busy) begin
                    state_next = MEAN_DIVIDE;
                end
            end

            MEAN_DIVIDE: begin
                // floor(numerator / 2n) for either sign of the numerator
                divider_start = 1'b1;
                divider_divisor = DIVIDER_WIDTH'(2 * width_reg);
                if (numerator >= 0) begin
                    divider_dividend = DIVIDER_WIDTH'(numerator);
                    mean_negative_next = 1'b0;
                end else begin
                    divider_dividend = DIVIDER_WIDTH'(-numerator + 48'(2 * width_reg) - 1);
                    mean_negative_next = 1'b1;
                end
                state_next = MEAN_WAIT;
            end

            MEAN_WAIT: begin
                if (divider_done) begin
                    mean_next = mean_negative_reg ? -32'(divider_quotient) : 32'(divider_quotient);
                    index_next = '0;
                    squares_next = '0;
                    state_next = SQUARES;
                end
            end

            SQUARES: begin
                issue_squares = 1'b1;
                index_next = index_reg + 1'b1;
                if (index_reg == (width_reg >> 3) - 1'b1) begin
                    state_next = SQUARES_FLUSH;
                end
            end

            SQUARES_FLUSH: begin
                if (!pipeline_busy) begin
                    state_next = VARIANCE_DIVIDE;
                end
            end

            VARIANCE_DIVIDE: begin
                divider_start = 1'b1;
                divider_dividend = DIVIDER_WIDTH'(squares_reg);
                divider_divisor = DIVIDER_WIDTH'(width_reg);
                state_next = VARIANCE_WAIT;
            end

            VARIANCE_WAIT: begin
                if (divider_done) begin
                    root_value_next = divider_quotient;
                    root_next = '0;
                    root_bit_next = 48'd1 << 46;
                    state_next = ROOT;
                end
            end

            // digit-by-digit integer square root, two bits of the value per clock
            ROOT: begin
                if (root_bit_reg == '0) begin
                    state_next = INVERSE_DIVIDE;
                end else begin
                    if (root_value_reg >= root_reg + root_bit_reg) begin
                        root_value_next = root_value_reg - (root_reg + root_bit_reg);
                        root_next = (root_reg >> 1) + root_bit_reg;
                    end else begin
                        root_next = root_reg >> 1;
                    end
                    root_bit_next = root_bit_reg >> 2;
                end
            end

            INVERSE_DIVIDE: begin
                divider_start = 1'b1;
                divider_dividend = DIVIDER_WIDTH'(1) << (fraction_reg + 5'd16);
                divider_divisor = (root_reg == '0) ? DIVIDER_WIDTH'(1) : DIVIDER_WIDTH'(root_reg);
                state_next = INVERSE_WAIT;
            end

            INVERSE_WAIT: begin
                if (divider_done) begin
                    inverse_next = divider_quotient;
                    index_next = '0;
                    state_next = NORMALISE;
                end
            end

            NORMALISE: begin
                issue_normalise = 1'b1;
                index_next = index_reg + 1'b1;
                if (index_reg == (width_reg >> NORM_LOG) - 1'b1) begin
                    state_next = NORMALISE_FLUSH;
                end
            end

            NORMALISE_FLUSH: begin
                if (!pipeline_busy) begin
                    if (token_reg == tokens_reg - 1'b1) begin
                        state_next = FINISH;
                    end else begin
                        token_next = token_reg + 1'b1;
                        index_next = '0;
                        total_next = '0;
                        state_next = SUM;
                    end
                end
            end

            FINISH: state_next = IDLE;
            default: state_next = IDLE;
        endcase
    end

    assign busy = (state_reg != IDLE);
    assign done = (state_reg == FINISH);

    // parameters into local RAM: first n/4 beats gamma, then n/4 beats beta
    always_ff @(posedge clk) begin
        if (state_reg == PARAMETER_RECEIVE && read_valid) begin
            if (beat_reg < (width_reg >> 2)) begin
                gamma_ram[beat_reg] <= read_data;
            end else begin
                beta_ram[beat_reg - (width_reg >> 2)] <= read_data;
            end
        end
    end

    // source rows: n / 8 INT16 words per token
    logic [15:0] word_index;
    assign word_index = issue_normalise ? (index_reg >> (3 - NORM_LOG)) : index_reg;
    assign source_address = BUFFER_ADDRESS_WIDTH'(token_reg * (width_reg >> 3) + word_index);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            s_sum <= '0;
            s_squares <= '0;
            s_normalise <= '0;
        end else begin
            s_sum <= {s_sum[D-1:1], issue_sum};
            s_squares <= {s_squares[D-1:1], issue_squares};
            s_normalise <= {s_normalise[D-1:1], issue_normalise};
        end
    end

    always_ff @(posedge clk) begin
        s_index[1] <= index_reg;
        s_token[1] <= token_reg;
        for (int i = 2; i <= D; i++) begin
            s_index[i] <= s_index[i-1];
            s_token[i] <= s_token[i-1];
        end
    end

    assign pipeline_busy = |{s_sum, s_squares, s_normalise};

    // sum and squares of the arriving word
    always_ff @(posedge clk) begin
        logic signed [18:0] row_sum;
        logic [34:0] row_squares;
        row_sum = '0;
        for (int e = 0; e < 8; e++) begin
            logic signed [17:0] v;
            logic signed [17:0] c, minus_c;
            v = 18'($signed(source_data[16*e +: 16]));
            row_sum = row_sum + 19'(v);
            c = v - 18'(mean_reg);
            minus_c = 18'(mean_reg) - v;
            square_c[e] <= c[17] ? 17'(minus_c) : 17'(c);
        end
        sum_word <= row_sum;
        for (int e = 0; e < 8; e++) begin
            logic [7:0] h;
            logic [8:0] l;
            h = square_c[e][16:9];
            l = square_c[e][8:0];
            square_hh[e] <= 16'(h) * 16'(h);
            square_hl[e] <= 17'(h) * 17'(l);
            square_ll[e] <= 18'(l) * 18'(l);
            square[e] <= (32'(square_hh[e]) << 18) + (32'(square_hl[e]) << 10) + 32'(square_ll[e]);
        end
        row_squares = '0;
        for (int e = 0; e < 8; e++) begin
            row_squares = row_squares + 35'(square[e]);
        end
        squares_word <= row_squares;
    end

    // gamma at L+3 and beta at L+4, for the group then in that stage
    always_ff @(posedge clk) begin
        gamma_word <= gamma_ram[s_index[L+2] >> (2 - NORM_LOG)];
        beta_word <= beta_ram[s_index[L+3] >> (2 - NORM_LOG)];
    end

    // normalise NORM_LANES elements of the arriving word (group s_index)
    // c: 18 bits; inv <= 2^(F+16) = 2^28 (F = 12): 29 bits; c * inv: 47 bits.
    // |z| < 2.83 * sqrt(n) * 2^F < 2^19 for n <= 1024, because c_i^2 <= sum c^2
    // < n * (var + 1) and std = isqrt(var) >= sqrt(var) / 2, so z fits 21 bits;
    // z * g + b: 21 x 32 bits + 32 -> 54 bits. Two DSP48E1 per product.
    logic signed [17:0] n_c [0:NORM_LANES-1];
    logic signed [47:0] n_scaled [0:NORM_LANES-1];
    logic signed [20:0] n_z [0:NORM_LANES-1];
    logic signed [53:0] n_product [0:NORM_LANES-1];
    logic signed [53:0] n_sum [0:NORM_LANES-1];
    logic [5:0] round_shift;
    logic signed [53:0] round_constant;
    logic [BUFFER_ADDRESS_WIDTH-1:0] d_address;
    logic [127:0] d_data;
    logic [15:0] d_enable;

    always_ff @(posedge clk) begin
        round_shift <= 6'(fraction_reg) + 6'd8;
        round_constant <= 54'sd1 <<< (fraction_reg + 5'd7);
    end

    always_ff @(posedge clk) begin
        logic [15:0] first_in, first_g, first_b, first_out;
        first_in = 16'(s_index[L] << NORM_LOG);
        first_g = 16'(s_index[L+3] << NORM_LOG);
        first_b = 16'(s_index[L+4] << NORM_LOG);
        first_out = 16'(s_index[L+5] << NORM_LOG);
        for (int e = 0; e < NORM_LANES; e++) begin
            logic signed [47:0] rounded;
            logic signed [53:0] y;
            logic signed [63:0] out;
            int element_in_word, element_in_gamma;
            element_in_word = int'(first_in[2:0]) + e;          // INT16 source word: 8 elements
            element_in_gamma = int'(first_g[1:0]) + e;          // gamma/beta word: 4 elements

            n_c[e] <= 18'($signed(source_data[16 * element_in_word +: 16])) - 18'(mean_reg);
            n_scaled[e] <= 48'(n_c[e]) * 48'($signed({1'b0, inverse_reg[28:0]}));
            rounded = (n_scaled[e] + 48'sd32768) >>> 16;
            n_z[e] <= 21'(rounded);
`ifndef SYNTHESIS
            if (s_normalise[L+2] && 48'(21'(rounded)) != rounded) $error("layernorm: z out of 21 bits");
`endif
            n_product[e] <= 54'(n_z[e]) * 54'($signed(gamma_word[32*element_in_gamma +: 32]));
            n_sum[e] <= n_product[e] + 54'($signed(beta_word[32*(int'(first_b[1:0]) + e) +: 32]))
                        + round_constant;
            y = n_sum[e] >>> round_shift;
            out = clamp(64'(y), -64'sd127, 64'sd127);
            for (int r = 0; r < 16 / NORM_LANES; r++) begin
                // the byte goes to lane first[3:0] + e; write it at every lane = e mod NORM_LANES
                d_data[8 * (NORM_LANES * r + e) +: 8] <= out[7:0];
            end
        end
        d_address <= BUFFER_ADDRESS_WIDTH'(s_token[L+5] * (width_reg >> 4) + (first_out >> 4));
        d_enable <= 16'((1 << NORM_LANES) - 1) << first_out[3:0];
    end

    assign destination_write = s_normalise[D];
    assign destination_address = d_address;
    assign destination_data = d_data;
    assign destination_enable = d_enable;

endmodule
