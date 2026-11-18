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
    parameter integer READ_LATENCY = encoder_pkg::READ_LATENCY,
    parameter integer TILE_OUT = 12,             // TO; TI is fixed at 16 (one beat)
    parameter integer MAC_LATENCY = 1,
    parameter integer PIPELINED_DOT = 0,
    parameter integer CACHED_REQUEST_WINDOW = 0,
    parameter integer INCREMENTAL_SOURCE_ROW = 0,
    parameter integer LINEAR_ACCUMULATORS_IN_BRAM = 0,
    parameter integer PIPELINED_DRAIN_SELECT = 0,
    // output channels requantised per clock (1, 2 or 4; divides TILE_OUT): the drain
    // takes n * TO / DRAIN_LANES clocks per output tile against n * in_tiles for the
    // MACs, so wide tiles (KR260, TO = 32) need more than one. 2 DSP48E1 per lane.
    parameter integer DRAIN_LANES = 1,
    // 1: the two accumulator banks (MAX_TOKENS x 32 x TO bits each) in LUT RAM instead
    // of block RAM: wide tiles need ~11 RAMB36 per bank for 128 shallow rows
    parameter integer ACCUMULATORS_IN_LUTS = 0,
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
    input logic raw,                             // raw INT32 output (heads): 4-byte elements
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
    input logic signed [23:0] mac_dot [0:TILE_OUT-1],

    // destination buffer
    output logic [2:0] perf_events, // compute issue, weight wait, accumulator/drain wait
    output logic destination_write,
    output logic [BUFFER_ADDRESS_WIDTH-1:0] destination_address,
    output logic [127:0] destination_data,
    output logic [15:0] destination_enable
);

    localparam integer TO = TILE_OUT;
    localparam integer PARAMETER_BEATS = (8 * TO + 15) / 16;
    localparam integer TOKEN_WIDTH = $clog2(MAX_TOKENS + 1);
    localparam integer COLUMN_WIDTH = $clog2(TO + 1);
    localparam integer MAC_EXTRA = MAC_LATENCY - 1 + (PIPELINED_DOT != 0 ? 3 : 0);
    localparam integer PASS_GAP = 4 + MAC_EXTRA;

`ifndef SYNTHESIS
    initial begin
        if (TO % DRAIN_LANES != 0 || !(DRAIN_LANES == 1 || DRAIN_LANES == 2 || DRAIN_LANES == 4))
            $fatal(1, "linear_engine: DRAIN_LANES %0d must be 1, 2 or 4 and divide TILE_OUT %0d",
                   DRAIN_LANES, TO);
    end
`endif

    // ------------------------------------------------------- instruction latch

    logic running_reg;
    logic [ADDRESS_WIDTH-1:0] stream_reg;
    logic [15:0] in_tiles_reg, out_tiles_reg, out_dim_reg;
    logic [15:0] source_row_reg, destination_row_reg;
    logic wide_reg, use_lut_reg, raw_reg;
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
            raw_reg <= 1'b0;
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
            // raw rows are whole words: the columns padding the last one (M = 0 in the
            // stream) are written too, as 0
            out_dim_reg <= raw ? ((out_dim + 16'd3) & ~16'd3) : out_dim;
            source_row_reg <= 16'((in_dim + 16'd15) >> 4);
            wide_reg <= !raw && (clamp_high > 32'sd127);
            raw_reg <= raw;
            destination_row_reg <= raw ? 16'((out_dim + 16'd3) >> 2)
                                 : (clamp_high > 32'sd127) ? 16'((out_dim + 16'd7) >> 3)
                                                           : 16'((out_dim + 16'd15) >> 4);
            use_lut_reg <= !raw && (lut_address != '0);
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
    (* keep=(CACHED_REQUEST_WINDOW!=0 ? "true":"false"), dont_touch=(CACHED_REQUEST_WINDOW!=0 ? "true":"false") *) logic [16:0] request_window_limit_reg;
    logic [16:0] load_tile_reg;                  // output tiles whose stream the loader started
    logic [15:0] tile_beats;
    logic [ADDRESS_WIDTH-1:0] stream_cursor_reg;
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
            end else if (request_tile_reg < 17'(out_tiles_reg) && request_tile_reg < (CACHED_REQUEST_WINDOW!=0 ? request_window_limit_reg : load_tile_reg + 17'd2)) begin
                read_request_valid = 1'b1;
                read_request_address = PIPELINED_DOT != 0 ? stream_cursor_reg
                    : stream_reg + ADDRESS_WIDTH'(request_tile_reg * tile_beats * 16);
                read_request_beats = BEATS_WIDTH'(tile_beats);
            end
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            request_tile_reg <= '0;
            lut_requested_reg <= 1'b0;
            stream_cursor_reg <= '0;
        end else if (launch) begin
            request_tile_reg <= '0;
            lut_requested_reg <= 1'b0;
            stream_cursor_reg <= stream_reg;
        end else if (read_request_valid && read_request_ready) begin
            if (use_lut_reg && !lut_requested_reg) lut_requested_reg <= 1'b1;
            else begin
                request_tile_reg <= request_tile_reg + 1'b1;
                stream_cursor_reg <= stream_cursor_reg + (ADDRESS_WIDTH'(tile_beats) << 4);
            end
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
            request_window_limit_reg <= 17'd2;
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
            request_window_limit_reg <= 17'd2;
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
                            request_window_limit_reg <= request_window_limit_reg + 1'b1;
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

    // Local payload/row capture removes the AXI response bus from the LUT
    // write fanout. Only table writes move one edge; load/request FSMs do not.
    // Compute uses this table after subsequent parameter/weight loading.
    logic lut_capture_valid;
    logic [3:0] lut_capture_row;
    logic [127:0] lut_capture_data;
    always_ff @(posedge clk or posedge reset) begin
        if(reset) lut_capture_valid <= 1'b0;
        else lut_capture_valid <= load_state == L_LUT && take;
    end
    always_ff @(posedge clk) begin
        if(load_state == L_LUT && take) begin
            lut_capture_row <= load_beat[3:0];
            lut_capture_data <= read_data;
        end
        if(lut_capture_valid && !reset) begin
            for(int b=0;b<16;b++)
                lut[16 * lut_capture_row + b] <= $signed(lut_capture_data[8*b +: 8]);
        end
    end

    always_ff @(posedge clk) begin
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

    logic [TOKEN_WIDTH-1:0] bank_read_address [0:1];
    logic [32*TO-1:0] bank_read_data [0:1];
    logic accumulator_write;
    logic accumulator_write_bank;
    logic [TOKEN_WIDTH-1:0] accumulator_write_address;
    logic [32*TO-1:0] accumulator_write_data;

    for (genvar k = 0; k < 2; k++) begin : gen_bank
        if (LINEAR_ACCUMULATORS_IN_BRAM != 0) begin : gen_forced_block
            (* ram_style = "block" *) logic [32*TO-1:0] accumulator [0:MAX_TOKENS-1];
            always_ff @(posedge clk) begin
                bank_read_data[k] <= accumulator[bank_read_address[k]];
                if (accumulator_write && accumulator_write_bank == 1'(k)) begin
                    accumulator[accumulator_write_address] <= accumulator_write_data;
                end
            end
        end else if (ACCUMULATORS_IN_LUTS != 0) begin : gen_lut
            (* ram_style = "distributed" *) logic [32*TO-1:0] accumulator [0:MAX_TOKENS-1];
            always_ff @(posedge clk) begin
                bank_read_data[k] <= accumulator[bank_read_address[k]];
                if (accumulator_write && accumulator_write_bank == 1'(k)) begin
                    accumulator[accumulator_write_address] <= accumulator_write_data;
                end
            end
        end else begin : gen_block
            logic [32*TO-1:0] accumulator [0:MAX_TOKENS-1];
            always_ff @(posedge clk) begin
                bank_read_data[k] <= accumulator[bank_read_address[k]];
                if (accumulator_write && accumulator_write_bank == 1'(k)) begin
                    accumulator[accumulator_write_address] <= accumulator_write_data;
                end
            end
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
    logic [BUFFER_ADDRESS_WIDTH-1:0] compute_source_row;
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
                         && (tokens_reg >= TOKEN_WIDTH'(PASS_GAP) || since_pass_start >= 4'(PASS_GAP));
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
            compute_source_row <= '0;
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
            compute_source_row <= '0;
                        compute_bank <= 1'b0;
                        compute_weight_bank <= 1'b0;
                        since_pass_start <= 4'hF;
                        compute_state <= C_WAIT;
                    end
                end
                C_WAIT: begin
                    if (can_start_pass) begin
                        compute_token <= '0;
            compute_source_row <= '0;
                        since_pass_start <= '0;
                        compute_state <= C_RUN;
                    end
                end
                C_RUN: begin
                    compute_token <= compute_token + 1'b1;
                    compute_source_row <= &compute_token ? '0 : compute_source_row + BUFFER_ADDRESS_WIDTH'(source_row_reg);
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
    assign perf_events = {compute_issue,
        (compute_state == C_WAIT && !weight_full[compute_weight_bank]),
        (compute_state == C_WAIT && compute_in_tile == 0 && accumulator_full[compute_bank])};
    assign source_address = INCREMENTAL_SOURCE_ROW!=0 ? BUFFER_ADDRESS_WIDTH'(compute_source_row + compute_in_tile)
                                                   : BUFFER_ADDRESS_WIDTH'(compute_token * source_row_reg + compute_in_tile);

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

    // The accumulator/bias read occurs at its original time. Carry its value
    // and token/bank/last tags alongside any extra multiplier operand stages.
    wire aligned_valid [0:MAC_EXTRA];
    wire aligned_bank [0:MAC_EXTRA];
    wire aligned_last [0:MAC_EXTRA];
    wire [TOKEN_WIDTH-1:0] aligned_token [0:MAC_EXTRA];
    wire signed [31:0] aligned_old [0:MAC_EXTRA][0:TO-1];
    assign aligned_valid[0] = stage2_valid;
    assign aligned_bank[0] = stage2_bank;
    assign aligned_last[0] = stage2_last;
    assign aligned_token[0] = stage2_token;
    for (genvar c = 0; c < TO; c++) assign aligned_old[0][c] = stage2_old[c];
    for (genvar p = 1; p <= MAC_EXTRA; p++) begin : gen_mac_tags
        logic valid_reg, bank_reg, last_reg;
        logic [TOKEN_WIDTH-1:0] token_reg;
        logic signed [31:0] old_reg [0:TO-1];
        always_ff @(posedge clk or posedge reset) begin
            if (reset) valid_reg <= 1'b0;
            else valid_reg <= aligned_valid[p-1];
        end
        always_ff @(posedge clk) begin
            bank_reg <= aligned_bank[p-1];
            last_reg <= aligned_last[p-1];
            token_reg <= aligned_token[p-1];
            for (int c = 0; c < TO; c++) old_reg[c] <= aligned_old[p-1][c];
        end
        assign aligned_valid[p] = valid_reg;
        assign aligned_bank[p] = bank_reg;
        assign aligned_last[p] = last_reg;
        assign aligned_token[p] = token_reg;
        for (genvar c = 0; c < TO; c++) assign aligned_old[p][c] = old_reg[c];
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            stage1_valid <= 1'b0;
            stage2_valid <= 1'b0;
            stage3_valid <= 1'b0;
        end else begin
            stage1_valid <= r_valid[RD];
            stage2_valid <= stage1_valid;
            stage3_valid <= aligned_valid[MAC_EXTRA];
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

        stage3_token <= aligned_token[MAC_EXTRA];
        stage3_bank <= aligned_bank[MAC_EXTRA];
        stage3_last <= aligned_valid[MAC_EXTRA] && aligned_last[MAC_EXTRA];
        for (int c = 0; c < TO; c++) begin
            stage3_old[c] <= aligned_old[MAC_EXTRA][c];
        end
    end

    if (PIPELINED_DOT != 0) begin : gen_dot_pipeline
        assign stage3_sum = mac_dot;
    end else begin : gen_dot_legacy
        always_ff @(posedge clk) begin
            for (int c = 0; c < TO; c++) begin
                logic signed [23:0] sum;
                sum = '0;
                for (int r = 0; r < 16; r++) sum = sum + 24'(mac_product[c][r]);
                stage3_sum[c] <= sum;
            end
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
                    drain_column <= drain_column + COLUMN_WIDTH'(DRAIN_LANES);
                    if (drain_column + COLUMN_WIDTH'(DRAIN_LANES) >= drain_columns) begin
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

    // d0 issue (read row); d1 row arrives; d2 channels selected; d3 products;
    // d4 rounded shift; d5 clamp; d6 table -> destination. DRAIN_LANES adjacent
    // channels per clock (a group starts at a multiple of DRAIN_LANES, so its elements
    // share one destination word).
    localparam int DD = 6 + (PIPELINED_DRAIN_SELECT != 0);
    localparam int LN = DRAIN_LANES;
    logic [DD:1] d_valid;
    logic [DD:1] d_final;
    logic [15:0] d_column [1:DD];                 // first channel of the group
    logic [LN-1:0] d_lane_valid [1:DD];
    logic [TOKEN_WIDTH-1:0] d_token [1:DD];
    logic d1_bank;
    logic [COLUMN_WIDTH-1:0] d1_column_index;
    logic [16:0] d1_multiplier [0:LN-1], d2_multiplier [0:LN-1];
    logic signed [31:0] d2_selected [0:LN-1];
    logic signed [49:0] d3_product [0:LN-1];      // INT32 x 17-bit unsigned: 2 DSP48E1
    logic signed [49:0] d4_value [0:LN-1];
    logic signed [31:0] d5_value [0:LN-1];
    logic signed [31:0] d6_value [0:LN-1];
    logic final_issue;
    if(PIPELINED_DRAIN_SELECT!=0)begin : gen_pipelined_drain
    logic [32*LN-1:0] selected_packet;
    logic [17*LN-1:0] multiplier_packet,input_multiplier_packet;
    for(genvar l=0;l<LN;l++)begin : gen_drain_packet
        assign input_multiplier_packet[17*l+:17]=d1_multiplier[l];
        assign d2_selected[l]=$signed(selected_packet[32*l+:32]);
        assign d2_multiplier[l]=multiplier_packet[17*l+:17];
    end
    linear_drain_select #(.ROW_CHANNELS(TO),.LANES(LN),.COLUMN_WIDTH(COLUMN_WIDTH)) selector(
        .clk,.reset,.advance(1'b1),.in_valid(d_valid[1]),
        .row0(bank_read_data[0]),.row1(bank_read_data[1]),.bank(d1_bank),
        .column(d1_column_index),.lane_mask(d_lane_valid[1]),
        .multipliers(input_multiplier_packet),.tag(32'd0),.out_valid(),
        .selected(selected_packet),.out_lane_mask(),.out_multipliers(multiplier_packet),.out_tag());

    end else begin : gen_default_drain
        always_ff @(posedge clk)for(int l=0;l<LN;l++)begin
            d2_selected[l]<=$signed(bank_read_data[d1_bank][32*(32'(d1_column_index)+l)+:32]);
            d2_multiplier[l]<=d1_multiplier[l];
        end
    end

    assign final_issue = drain_issue && (drain_column + COLUMN_WIDTH'(DRAIN_LANES) >= drain_columns)
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
        for (int l = 0; l < LN; l++) begin
            d_lane_valid[1][l] <= (drain_column + COLUMN_WIDTH'(l) < drain_columns);
        end
        d_column[1] <= 16'(drain_out_tile * TO) + 16'(drain_column);
        d_token[1] <= drain_token;
        for (int i = 2; i <= DD; i++) begin
            d_column[i] <= d_column[i-1];
            d_token[i] <= d_token[i-1];
            d_lane_valid[i] <= d_lane_valid[i-1];
        end

        d1_bank <= drain_bank;
        d1_column_index <= drain_column;
        for (int l = 0; l < LN; l++) begin
            logic [COLUMN_WIDTH-1:0] c;
            c = drain_column + COLUMN_WIDTH'(l);
            d1_multiplier[l] <= (c < COLUMN_WIDTH'(TO)) ? multiplier[drain_bank][c] : 17'd0;


            d3_product[l] <= 50'(d2_selected[l]) * 50'($signed({1'b0, d2_multiplier[l]}));

            if (shift_reg == '0) begin
                d4_value[l] <= d3_product[l];
            end else begin
                d4_value[l] <= (d3_product[l] + (50'sd1 <<< (shift_reg - 6'd1))) >>> shift_reg;
            end

            d5_value[l] <= 32'(clamp(64'(d4_value[l]), 64'(low_reg), 64'(high_reg)));

            d6_value[l] <= use_lut_reg ? 32'(lut[8'(d5_value[l][7:0] + 8'd127)]) : d5_value[l];
        end
    end

    assign finished = d_valid[DD] && d_final[DD];

    // the group's elements into one word: INT8 (1 byte), INT16 (2) or raw INT32 (4)
    always_comb begin
        logic [15:0] c0;
        c0 = d_column[DD];
        destination_write = d_valid[DD];
        destination_address = BUFFER_ADDRESS_WIDTH'(d_token[DD] * destination_row_reg
                              + (raw_reg ? (c0 >> 2) : element_word(c0, wide_reg)));
        destination_data = '0;
        destination_enable = '0;
        for (int l = 0; l < LN; l++) begin
            logic [15:0] c;
            c = c0 + 16'(l);
            if (raw_reg) begin
                destination_data[32 * c[1:0] +: 32] = d6_value[l];
                if (d_lane_valid[DD][l]) destination_enable[4 * c[1:0] +: 4] = 4'hF;
            end else if (wide_reg) begin
                destination_data[16 * c[2:0] +: 16] = d6_value[l][15:0];
                if (d_lane_valid[DD][l]) destination_enable[2 * c[2:0] +: 2] = 2'b11;
            end else begin
                destination_data[8 * c[3:0] +: 8] = d6_value[l][7:0];
                if (d_lane_valid[DD][l]) destination_enable[c[3:0]] = 1'b1;
            end
        end
    end

endmodule
