// LINEAR instruction of the v2 encoder: y = clamp(requant(x @ W + b, M[c], S), lo, hi),
// optionally through a 256-entry INT8 table (GELU), for every token of the chain.
//
// Weight-stationary: the weights arrive from external memory as the tiled stream
// that scripts/v2/compile_image.py writes (src/sysone/v2/ddr_image.py), one memory
// request per output tile of TO channels:
//
//     channel block   TO x {bias int32, M int32}, (TO + 1) / 2 beats
//     input tile it   TO beats; beat c = W[16*it .. 16*it + 15, c] as 16 INT8 bytes
//
// A 16 x TO tile (one beat per output column) is held in registers and applied to
// every token, one token per clock (16 * TO MACs per clock), adding into an INT32
// accumulator RAM of MAX_TOKENS x TO. After the last input tile the accumulators
// are requantised one channel per clock and written to the destination buffer.
//
// Four processes overlap so that the MAC array is busy whenever it can be:
//   requests  issue the tile streams ahead (up to two output tiles in flight)
//   loader    takes the stream into two weight-tile banks and two channel banks
//   compute   streams tokens through the MACs (waits only for a loaded tile)
//   drain     requantises output tile ot from one accumulator bank while compute
//             fills the other with tile ot + 1
// With n tokens an output tile costs about max(in_tiles * max(n, TO), n * cols)
// clocks once the pipeline is full.
//
// The source buffer holds INT8 rows of ceil(in/16) words; the destination INT8 rows
// of ceil(out/16) words or, when hi > 127, INT16 rows of ceil(out/8) words.
module linear_engine
    import encoder_pkg::*;
#(
    parameter integer TILE_OUT = 12,             // TO; TI is fixed at 16 (one beat)
    parameter integer MAX_TOKENS = 128,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer BUFFER_ADDRESS_WIDTH = 14
) (
    input logic clk,
    input logic reset,

    input logic start,
    output logic busy,
    output logic done,                           // one-clock pulse

    // instruction (held by the caller while busy)
    input logic [ADDRESS_WIDTH-1:0] stream_address,
    input logic [15:0] in_dim,
    input logic [15:0] out_dim,
    input logic [5:0] shift,
    input logic signed [31:0] clamp_low,
    input logic signed [31:0] clamp_high,
    input logic [ADDRESS_WIDTH-1:0] lut_address, // 0 = no table
    input logic [7:0] token_count,               // 1 .. MAX_TOKENS

    // memory port, read side
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    // source buffer (INT8), READ_LATENCY clocks of read latency
    output logic [BUFFER_ADDRESS_WIDTH-1:0] source_address,
    input logic [127:0] source_data,

    // shared multiplier array (mac_array): operands now, products next clock
    output logic signed [8:0] mac_a [0:TILE_OUT-1][0:15],
    output logic signed [7:0] mac_b [0:15],
    input logic signed [16:0] mac_product [0:TILE_OUT-1][0:15],

    // destination buffer
    output logic destination_write,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    localparam integer TO = TILE_OUT;
    localparam integer PARAMETER_BEATS = (8 * TO + 15) / 16;
    localparam integer TOKEN_WIDTH = $clog2(MAX_TOKENS + 1);
    localparam integer COLUMN_WIDTH = $clog2(TO + 1);

    // ------------------------------------------------------- instruction latch

    logic running_reg;
    logic [ADDRESS_WIDTH-1:0] stream_reg;
    logic [15:0] in_tiles_reg, out_tiles_reg, out_dim_reg;
    logic [7:0] source_row_reg, destination_row_reg;
    logic wide_reg, use_lut_reg;
    logic [5:0] shift_reg;
    logic signed [31:0] low_reg, high_reg;
    logic [TOKEN_WIDTH-1:0] tokens_reg;
    logic [ADDRESS_WIDTH-1:0] lut_reg;
    logic finished;                              // drain wrote the last element

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            running_reg <= 1'b0;
            stream_reg <= '0;
            in_tiles_reg <= '0;
            out_tiles_reg <= '0;
            out_dim_reg <= '0;
            source_row_reg <= '0;
            destination_row_reg <= '0;
            wide_reg <= 1'b0;
            use_lut_reg <= 1'b0;
            shift_reg <= '0;
            low_reg <= '0;
            high_reg <= '0;
            tokens_reg <= '0;
            lut_reg <= '0;
        end else if (!running_reg && start) begin
            running_reg <= 1'b1;
            stream_reg <= stream_address;
            in_tiles_reg <= (in_dim + 16'd15) >> 4;
            out_tiles_reg <= 16'((32'(out_dim) + TO - 1) / TO);
            out_dim_reg <= out_dim;
            source_row_reg <= 8'((in_dim + 16'd15) >> 4);
            wide_reg <= (clamp_high > 32'sd127);
            destination_row_reg <= (clamp_high > 32'sd127) ? 8'((out_dim + 16'd7) >> 3)
                                                           : 8'((out_dim + 16'd15) >> 4);
            use_lut_reg <= (lut_address != '0);
            shift_reg <= shift;
            low_reg <= clamp_low;
            high_reg <= clamp_high;
            tokens_reg <= TOKEN_WIDTH'(token_count);
            lut_reg <= lut_address;
        end else if (finished) begin
            running_reg <= 1'b0;
        end
    end

    logic done_reg;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) done_reg <= 1'b0;
        else done_reg <= finished;
    end
    assign busy = running_reg | done_reg;
    assign done = done_reg;

    logic launch;                                 // first clock of a run
    logic launch_reg;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) launch_reg <= 1'b0;
        else launch_reg <= !running_reg && start;
    end
    assign launch = launch_reg;

    // ---------------------------------------------------------------- requests

    logic [16:0] request_tile_reg;               // output tiles requested (LUT first)
    logic lut_requested_reg;
    logic [16:0] load_tile_reg;                  // output tiles whose stream the loader started
    logic [15:0] tile_beats;
    assign tile_beats = 16'(PARAMETER_BEATS) + 16'(in_tiles_reg * TO);

    always_comb begin
        read_request_valid = 1'b0;
        read_request_address = '0;
        read_request_beats = '0;
        if (running_reg && !launch) begin
            if (use_lut_reg && !lut_requested_reg) begin
                read_request_valid = 1'b1;
                read_request_address = lut_reg;
                read_request_beats = BEATS_WIDTH'(16);
            end else if (request_tile_reg < 17'(out_tiles_reg) && request_tile_reg < load_tile_reg + 17'd2) begin
                read_request_valid = 1'b1;
                read_request_address = stream_reg + ADDRESS_WIDTH'(request_tile_reg * tile_beats * 16);
                read_request_beats = BEATS_WIDTH'(tile_beats);
            end
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            request_tile_reg <= '0;
            lut_requested_reg <= 1'b0;
        end else if (launch) begin
            request_tile_reg <= '0;
            lut_requested_reg <= 1'b0;
        end else if (read_request_valid && read_request_ready) begin
            if (use_lut_reg && !lut_requested_reg) lut_requested_reg <= 1'b1;
            else request_tile_reg <= request_tile_reg + 1'b1;
        end
    end

    // ------------------------------------------------------------------ loader

    typedef enum logic [2:0] {
        L_IDLE,
        L_LUT,
        L_PARAMETERS,
        L_TILE,
        L_DONE
    } load_state_t;

    load_state_t load_state;
    logic [15:0] load_beat;
    logic [15:0] load_in_tile;
    logic load_weight_bank;                      // bank the loader fills next
    logic [1:0] weight_full;
    logic [1:0] parameter_full;
    logic load_parameter_bank;
    logic release_weight;                        // compute frees bank release_weight_bank
    logic release_weight_bank;
    logic release_parameter;                     // drain frees bank drain_bank
    logic compute_weight_bank;
    logic drain_bank;

    logic signed [7:0] weight [0:1][0:TO-1][0:15];
    logic signed [31:0] bias [0:1][0:TO-1];
    logic [16:0] multiplier [0:1][0:TO-1];        // M < 2^17 (compile_image checks)
    logic signed [7:0] lut [0:255];

    always_comb begin
        read_ready = 1'b0;
        case (load_state)
            L_LUT: read_ready = 1'b1;
            L_PARAMETERS: read_ready = !parameter_full[load_parameter_bank];
            L_TILE: read_ready = !weight_full[load_weight_bank];
            default: read_ready = 1'b0;
        endcase
    end

    logic take;
    assign take = read_valid && read_ready;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            load_state <= L_IDLE;
            load_beat <= '0;
            load_in_tile <= '0;
            load_weight_bank <= 1'b0;
            load_parameter_bank <= 1'b0;
            load_tile_reg <= '0;
            weight_full <= '0;
            parameter_full <= '0;
        end else begin
            logic [1:0] wf, pf;
            wf = weight_full;
            pf = parameter_full;
            if (release_weight) wf[release_weight_bank] = 1'b0;
            if (release_parameter) pf[drain_bank] = 1'b0;
            case (load_state)
                L_IDLE: begin
                    if (launch) begin
                        load_beat <= '0;
                        load_tile_reg <= '0;
                        load_weight_bank <= 1'b0;
                        load_parameter_bank <= 1'b0;
                        wf = '0;
                        pf = '0;
                        load_state <= use_lut_reg ? L_LUT : L_PARAMETERS;
                    end
                end
                L_LUT: begin
                    if (take) begin
                        load_beat <= load_beat + 1'b1;
                        if (load_beat == 16'd15) begin
                            load_beat <= '0;
                            load_state <= L_PARAMETERS;
                        end
                    end
                end
                L_PARAMETERS: begin
                    if (take) begin
                        load_beat <= load_beat + 1'b1;
                        if (load_beat == 16'(PARAMETER_BEATS - 1)) begin
                            pf[load_parameter_bank] = 1'b1;
                            load_parameter_bank <= ~load_parameter_bank;
                            load_tile_reg <= load_tile_reg + 1'b1;
                            load_beat <= '0;
                            load_in_tile <= '0;
                            load_state <= L_TILE;
                        end
                    end
                end
                L_TILE: begin
                    if (take) begin
                        load_beat <= load_beat + 1'b1;
                        if (load_beat == 16'(TO - 1)) begin
                            wf[load_weight_bank] = 1'b1;
                            load_weight_bank <= ~load_weight_bank;
                            load_beat <= '0;
                            load_in_tile <= load_in_tile + 1'b1;
                            if (load_in_tile == in_tiles_reg - 1'b1) begin
                                load_state <= (load_tile_reg == 17'(out_tiles_reg)) ? L_DONE : L_PARAMETERS;
                            end
                        end
                    end
                end
                L_DONE: begin
                    if (finished) load_state <= L_IDLE;
                end
                default: load_state <= L_IDLE;
            endcase
            weight_full <= wf;
            parameter_full <= pf;
        end
    end

    always_ff @(posedge clk) begin
        if (load_state == L_LUT && take) begin
            for (int b = 0; b < 16; b++) begin
                lut[16 * load_beat[3:0] + b] <= $signed(read_data[8*b +: 8]);
            end
        end
        if (load_state == L_PARAMETERS && take) begin
            for (int h = 0; h < 2; h++) begin
                if (2 * load_beat + h < TO) begin
                    bias[load_parameter_bank][2 * load_beat + h] <= $signed(read_data[64*h +: 32]);
                    multiplier[load_parameter_bank][2 * load_beat + h] <= read_data[64*h + 32 +: 17];
                end
            end
        end
        if (load_state == L_TILE && take) begin
            for (int r = 0; r < 16; r++) begin
                weight[load_weight_bank][load_beat[COLUMN_WIDTH-1:0]][r] <= $signed(read_data[8*r +: 8]);
            end
        end
    end

    // ------------------------------------------------------- accumulator banks

    logic [32*TO-1:0] accumulator0 [0:MAX_TOKENS-1];
    logic [32*TO-1:0] accumulator1 [0:MAX_TOKENS-1];
    logic [TOKEN_WIDTH-1:0] bank_read_address [0:1];
    logic [32*TO-1:0] bank_read_data [0:1];
    logic accumulator_write;
    logic accumulator_write_bank;
    logic [TOKEN_WIDTH-1:0] accumulator_write_address;
    logic [32*TO-1:0] accumulator_write_data;

    always_ff @(posedge clk) begin
        bank_read_data[0] <= accumulator0[bank_read_address[0]];
        if (accumulator_write && !accumulator_write_bank) begin
            accumulator0[accumulator_write_address] <= accumulator_write_data;
        end
    end
    always_ff @(posedge clk) begin
        bank_read_data[1] <= accumulator1[bank_read_address[1]];
        if (accumulator_write && accumulator_write_bank) begin
            accumulator1[accumulator_write_address] <= accumulator_write_data;
        end
    end

    logic [1:0] accumulator_full;                // waiting for / being drained
    logic set_full;                              // compute finished bank `full_bank`
    logic full_bank;
    logic release_accumulator;                   // drain finished bank drain_bank

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            accumulator_full <= '0;
        end else begin
            logic [1:0] af;
            af = accumulator_full;
            if (launch) af = '0;
            if (set_full) af[full_bank] = 1'b1;
            if (release_accumulator) af[drain_bank] = 1'b0;
            accumulator_full <= af;
        end
    end

    // ----------------------------------------------------------------- compute

    typedef enum logic [1:0] {
        C_IDLE,
        C_WAIT,
        C_RUN,
        C_DONE
    } compute_state_t;

    compute_state_t compute_state;
    logic [15:0] compute_out_tile;
    logic [15:0] compute_in_tile;
    logic [TOKEN_WIDTH-1:0] compute_token;
    logic compute_bank;                          // accumulator / parameter bank = out_tile parity
    logic compute_issue;
    logic [3:0] since_pass_start;                // clocks since the previous pass began
    logic stage1_valid, stage2_valid, stage3_valid;
    logic stage1_last, stage2_last, stage3_last;  // last token of the last pass of an out tile

    logic can_start_pass;
    always_comb begin
        // a new pass may read an accumulator row only after the previous pass wrote it
        // (3 clocks of pipeline): automatic when n >= 4, otherwise wait it out
        can_start_pass = weight_full[compute_weight_bank]
                         && (tokens_reg >= TOKEN_WIDTH'(4) || since_pass_start >= 4'd4);
        if (compute_in_tile == '0) begin
            can_start_pass = can_start_pass && parameter_full[compute_bank]
                             && !accumulator_full[compute_bank];
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            compute_state <= C_IDLE;
            compute_out_tile <= '0;
            compute_in_tile <= '0;
            compute_token <= '0;
            compute_bank <= 1'b0;
            compute_weight_bank <= 1'b0;
            since_pass_start <= '0;
        end else begin
            if (since_pass_start != 4'hF) since_pass_start <= since_pass_start + 1'b1;
            case (compute_state)
                C_IDLE: begin
                    if (launch) begin
                        compute_out_tile <= '0;
                        compute_in_tile <= '0;
                        compute_token <= '0;
                        compute_bank <= 1'b0;
                        compute_weight_bank <= 1'b0;
                        since_pass_start <= 4'hF;
                        compute_state <= C_WAIT;
                    end
                end
                C_WAIT: begin
                    if (can_start_pass) begin
                        compute_token <= '0;
                        since_pass_start <= '0;
                        compute_state <= C_RUN;
                    end
                end
                C_RUN: begin
                    compute_token <= compute_token + 1'b1;
                    if (compute_token == tokens_reg - 1'b1) begin
                        compute_weight_bank <= ~compute_weight_bank;
                        if (compute_in_tile == in_tiles_reg - 1'b1) begin
                            compute_in_tile <= '0;
                            compute_bank <= ~compute_bank;
                            compute_out_tile <= compute_out_tile + 1'b1;
                            compute_state <= (compute_out_tile == out_tiles_reg - 1'b1) ? C_DONE : C_WAIT;
                        end else begin
                            compute_in_tile <= compute_in_tile + 1'b1;
                            compute_state <= C_WAIT;
                        end
                    end
                end
                C_DONE: begin
                    if (finished) compute_state <= C_IDLE;
                end
                default: compute_state <= C_IDLE;
            endcase
        end
    end

    assign compute_issue = (compute_state == C_RUN);
    assign source_address = BUFFER_ADDRESS_WIDTH'(compute_token * source_row_reg + compute_in_tile);

    // the source word arrives READ_LATENCY clocks after the issue; the accumulator row
    // is read one clock before that (stage r), and the pass's weight tile is released
    // there, as the loader can only refill it a clock later
    localparam int RD = READ_LATENCY - 1;          // issue -> stage r (>= 1)
    logic [RD:1] r_valid;
    logic [TOKEN_WIDTH-1:0] r_token [1:RD];
    logic r_first [1:RD];
    logic r_bank [1:RD];
    logic r_weight_bank [1:RD];
    logic r_last_token [1:RD];
    logic r_last [1:RD];

    always_ff @(posedge clk or posedge reset) begin
        if (reset) r_valid <= '0;
        else r_valid <= RD'({r_valid, compute_issue});
    end
    always_ff @(posedge clk) begin
        r_token[1] <= compute_token;
        r_first[1] <= (compute_in_tile == '0);
        r_bank[1] <= compute_bank;
        r_weight_bank[1] <= compute_weight_bank;
        r_last_token[1] <= (compute_token == tokens_reg - 1'b1);
        r_last[1] <= (compute_token == tokens_reg - 1'b1) && (compute_in_tile == in_tiles_reg - 1'b1);
        for (int i = 2; i <= RD; i++) begin
            r_token[i] <= r_token[i-1];
            r_first[i] <= r_first[i-1];
            r_bank[i] <= r_bank[i-1];
            r_weight_bank[i] <= r_weight_bank[i-1];
            r_last_token[i] <= r_last_token[i-1];
            r_last[i] <= r_last[i-1];
        end
    end

    assign release_weight = r_valid[RD] && r_last_token[RD];
    assign release_weight_bank = r_weight_bank[RD];

    // MAC pipeline: r accumulator read; 1 source data -> mac_array products;
    // 2 column sums; 3 accumulator write.
    logic stage1_first, stage2_first;
    logic stage1_bank, stage2_bank, stage3_bank;
    logic stage1_weight_bank;
    logic [TOKEN_WIDTH-1:0] stage1_token, stage2_token, stage3_token;
    logic signed [31:0] stage2_old [0:TO-1];
    logic signed [31:0] stage3_old [0:TO-1];
    logic signed [23:0] stage3_sum [0:TO-1];

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            stage1_valid <= 1'b0;
            stage2_valid <= 1'b0;
            stage3_valid <= 1'b0;
        end else begin
            stage1_valid <= r_valid[RD];
            stage2_valid <= stage1_valid;
            stage3_valid <= stage2_valid;
        end
    end

    always_ff @(posedge clk) begin
        stage1_token <= r_token[RD];
        stage1_first <= r_first[RD];
        stage1_bank <= r_bank[RD];
        stage1_weight_bank <= r_weight_bank[RD];
        stage1_last <= r_valid[RD] && r_last[RD];

        stage2_token <= stage1_token;
        stage2_first <= stage1_first;
        stage2_bank <= stage1_bank;
        stage2_last <= stage1_valid && stage1_last;
        for (int c = 0; c < TO; c++) begin
            stage2_old[c] <= stage1_first ? bias[stage1_bank][c]
                                          : $signed(bank_read_data[stage1_bank][32*c +: 32]);
        end

        stage3_token <= stage2_token;
        stage3_bank <= stage2_bank;
        stage3_last <= stage2_valid && stage2_last;
        for (int c = 0; c < TO; c++) begin
            logic signed [23:0] sum;
            sum = '0;
            for (int r = 0; r < 16; r++) begin
                sum = sum + 24'(mac_product[c][r]);
            end
            stage3_sum[c] <= sum;
            stage3_old[c] <= stage2_old[c];
        end
    end

    // stage 1: the array multiplies the tile by the arriving source word
    always_comb begin
        for (int r = 0; r < 16; r++) begin
            mac_b[r] = $signed(source_data[8*r +: 8]);
            for (int c = 0; c < TO; c++) begin
                mac_a[c][r] = 9'(weight[stage1_weight_bank][c][r]);
            end
        end
    end

    always_comb begin
        accumulator_write = stage3_valid;
        accumulator_write_bank = stage3_bank;
        accumulator_write_address = stage3_token;
        for (int c = 0; c < TO; c++) begin
            accumulator_write_data[32*c +: 32] = stage3_old[c] + 32'(stage3_sum[c]);
        end
    end

    assign set_full = stage3_valid && stage3_last;
    assign full_bank = stage3_bank;

    // ------------------------------------------------------------------- drain

    typedef enum logic [1:0] {
        D_IDLE,
        D_WAIT,
        D_RUN,
        D_RELEASE
    } drain_state_t;

    drain_state_t drain_state;
    logic [15:0] drain_out_tile;
    logic [TOKEN_WIDTH-1:0] drain_token;
    logic [COLUMN_WIDTH-1:0] drain_column;
    logic [COLUMN_WIDTH-1:0] drain_columns;
    logic drain_issue;

    always_comb begin
        logic [15:0] remaining;
        remaining = out_dim_reg - 16'(drain_out_tile * TO);
        drain_columns = (remaining >= TO) ? COLUMN_WIDTH'(TO) : COLUMN_WIDTH'(remaining);
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            drain_state <= D_IDLE;
            drain_out_tile <= '0;
            drain_token <= '0;
            drain_column <= '0;
            drain_bank <= 1'b0;
        end else begin
            case (drain_state)
                D_IDLE: begin
                    if (launch) begin
                        drain_out_tile <= '0;
                        drain_bank <= 1'b0;
                        drain_state <= D_WAIT;
                    end
                end
                D_WAIT: begin
                    if (accumulator_full[drain_bank]) begin
                        drain_token <= '0;
                        drain_column <= '0;
                        drain_state <= D_RUN;
                    end
                end
                D_RUN: begin
                    drain_column <= drain_column + 1'b1;
                    if (drain_column == drain_columns - 1'b1) begin
                        drain_column <= '0;
                        drain_token <= drain_token + 1'b1;
                        if (drain_token == tokens_reg - 1'b1) begin
                            drain_state <= D_RELEASE;
                        end
                    end
                end
                D_RELEASE: begin
                    // the last accumulator read has returned; free both banks
                    drain_bank <= ~drain_bank;
                    drain_out_tile <= drain_out_tile + 1'b1;
                    drain_state <= (drain_out_tile == out_tiles_reg - 1'b1) ? D_IDLE : D_WAIT;
                end
                default: drain_state <= D_IDLE;
            endcase
        end
    end

    assign drain_issue = (drain_state == D_RUN);
    assign release_accumulator = (drain_state == D_RELEASE);
    assign release_parameter = (drain_state == D_RELEASE);

    always_comb begin
        bank_read_address[0] = (r_bank[RD] == 1'b0 && r_valid[RD]) ? r_token[RD] : drain_token;
        bank_read_address[1] = (r_bank[RD] == 1'b1 && r_valid[RD]) ? r_token[RD] : drain_token;
        if (drain_issue) begin
            bank_read_address[drain_bank] = drain_token;
        end
    end

    // d0 issue (read row); d1 row arrives; d2 channel selected; d3 product;
    // d4 rounded shift; d5 clamp; d6 table -> destination
    localparam int DD = 6;
    logic [DD:1] d_valid;
    logic [DD:1] d_final;
    logic [15:0] d_column [1:DD];
    logic [TOKEN_WIDTH-1:0] d_token [1:DD];
    logic d1_bank;
    logic [COLUMN_WIDTH-1:0] d1_column_index;
    logic [16:0] d1_multiplier, d2_multiplier;
    logic signed [31:0] d2_selected;
    logic signed [49:0] d3_product;               // INT32 x 17-bit unsigned: 2 DSP48E1
    logic signed [49:0] d4_value;
    logic signed [31:0] d5_value;
    logic signed [15:0] d6_value;
    logic final_issue;

    assign final_issue = drain_issue && (drain_column == drain_columns - 1'b1)
                         && (drain_token == tokens_reg - 1'b1)
                         && (drain_out_tile == out_tiles_reg - 1'b1);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            d_valid <= '0;
            d_final <= '0;
        end else begin
            d_valid <= DD'({d_valid, drain_issue});
            d_final <= DD'({d_final, final_issue});
        end
    end

    always_ff @(posedge clk) begin
        d_column[1] <= 16'(drain_out_tile * TO) + 16'(drain_column);
        d_token[1] <= drain_token;
        for (int i = 2; i <= DD; i++) begin
            d_column[i] <= d_column[i-1];
            d_token[i] <= d_token[i-1];
        end

        d1_bank <= drain_bank;
        d1_column_index <= drain_column;
        d1_multiplier <= multiplier[drain_bank][drain_column];

        d2_selected <= $signed(bank_read_data[d1_bank][32*d1_column_index +: 32]);
        d2_multiplier <= d1_multiplier;

        d3_product <= 50'(d2_selected) * 50'($signed({1'b0, d2_multiplier}));

        if (shift_reg == '0) begin
            d4_value <= d3_product;
        end else begin
            d4_value <= (d3_product + (50'sd1 <<< (shift_reg - 6'd1))) >>> shift_reg;
        end

        d5_value <= 32'(clamp(64'(d4_value), 64'(low_reg), 64'(high_reg)));

        d6_value <= use_lut_reg ? 16'(lut[8'(d5_value[7:0] + 8'd127)]) : d5_value[15:0];
    end

    assign finished = d_valid[DD] && d_final[DD];

    assign destination_write = d_valid[DD];
    assign destination_address = BUFFER_ADDRESS_WIDTH'(d_token[DD] * destination_row_reg
                                                       + element_word(d_column[DD], wide_reg));
    assign destination_data = element_data(d6_value, wide_reg);
    assign destination_enable = element_enable(d_column[DD], wide_reg);

endmodule
