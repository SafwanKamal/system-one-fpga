// The v2 encoder datapath: a sequencer that runs the layer program from the DDR
// image (scripts/v2/compile_image.py), the four engines, the multiplier array that
// LINEAR and ATTENTION share (16 x TILE_OUT), and the eight on-chip activation
// buffers. Everything model-specific (weights, constants, tables, the
// program) comes from external memory through one memory port; the RTL only knows
// the tile width, the maximum chain length and the buffer sizes.
//
// The caller (later: the v2 request handler; now: the testbench) loads the input
// rows through the host port, then runs instructions [first, first + count) of the
// program at `program_address` (the image's program section) and reads results
// back through the host port. `instruction_done` pulses after every instruction,
// with its index, so a testbench can single-step.
//
// Instruction encoding (64 bytes, little-endian), ddr_image.py:
//   byte 0 opcode, 1 src buffer, 2 src2 buffer, 3 dst buffer, 4 layer, payload at 8
//   LAYERNORM  params u32 @8, n u16 @12, fraction u8 @14
//   LINEAR     stream u32 @8, bytes u32 @12, in u16 @16, out u16 @18, S u8 @20,
//              mode u8 @21 (0 clamp, 1 raw INT32), lo i32 @22, hi i32 @26, lut u32 @30,
//              TI u16 @34, TO u16 @36, rows u16 @38 (0 = token_count)
//   ATTENTION  heads u16 @8, head_dim u16 @10, Msm u32 @12, Ssm u8 @16, Mctx u32 @17,
//              Sctx u8 @21, exp table u32 @22, exp steps u16 @26   (V is buffer V)
//   ADD_SKIP   M u32 @8, S u8 @12                                  (width = hidden)
//   END
//   EMBED      word u32 @8, word stride u16 @12, pos u32 @14, pos stride u16 @18,
//              max pos u16 @20, type u32 @22, Mw u32 @26, Sw u8 @30, Mp u32 @31, Sp u8 @35
//              (token ids: INT16 elements of the src buffer, written by the host)
//   POOL       first row u16 @8, rows u16 @10, out row u16 @12, recip table u32 @14
// An unknown opcode, or a LINEAR tile shape other than 16 x TILE_OUT, sets `error`.
module encoder_layer
    import encoder_pkg::*;
#(
    parameter integer TILE_OUT = 12,
    parameter integer MAX_TOKENS = 128,
    parameter integer MAX_HEAD_DIM = 64,
    parameter integer MAX_HIDDEN = 384,                  // multiple of 16; FFN <= 4 x this
    // 1: POOL and raw INT32 LINEAR, so the heads can run here (ddr_image.head_program);
    // 0: the heads run on the host from X, and those instructions set `error`
    parameter integer FPGA_HEADS = 0,
    // output channels requantised per clock in LINEAR (linear_engine): 1 on the Nexys
    parameter integer DRAIN_LANES = 1,
    // elements per clock in LAYERNORM's output pass (layernorm_engine): 2 on the Nexys
    parameter integer NORM_LANES = 2,
    // two products per DSP48E1 in the MAC array (mac_array PACK): TILE_OUT 24 in 192 DSPs
    parameter integer MAC_PACK = 0,
    // queries handled together by ATTENTION (<= TILE_OUT; it uses that many array lanes)
    parameter integer ATTENTION_LANES = TILE_OUT,
    // LINEAR's accumulator banks in LUT RAM (frees block RAM for wide tiles)
    parameter integer ACCUMULATORS_IN_LUTS = 0,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    // logical buffer addresses; G spans the four attention buffers
    parameter integer BUFFER_ADDRESS_WIDTH = $clog2(4 * MAX_TOKENS * MAX_HIDDEN / 16)
) (
    input logic clk,
    input logic reset,

    input logic start,
    input logic [ADDRESS_WIDTH-1:0] program_address,
    input logic [15:0] first_instruction,
    input logic [15:0] instruction_count,
    input logic [15:0] hidden,
    input logic [7:0] token_count,
    output logic busy,
    output logic done,
    output logic error,
    output logic instruction_done,
    output logic [15:0] instruction_index,

    // memory port, read side
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    // host access to the buffers, only while not busy
    input logic [2:0] host_buffer,
    input logic host_write,
    input logic [BUFFER_ADDRESS_WIDTH-1:0] host_address,
    input logic [127:0] host_write_data,
    input logic [15:0] host_write_enable,
    output logic [127:0] host_read_data                 // READ_LATENCY clocks after host_address
);

    typedef enum logic [2:0] {
        IDLE,
        FETCH_REQUEST,
        FETCH_RECEIVE,
        DISPATCH,
        EXECUTE,
        NEXT,
        FINISH
    } state_t;

    state_t state_reg, state_next;
    logic [15:0] index_reg, index_next;
    logic [15:0] remaining_reg, remaining_next;
    logic [1:0] beat_reg, beat_next;
    logic [511:0] instruction_reg;
    logic error_reg, error_next;
    logic [7:0] tokens_reg, tokens_next;
    logic [15:0] hidden_reg, hidden_next;
    logic [ADDRESS_WIDTH-1:0] program_reg, program_next;

    function automatic logic [7:0] byte_at(input int i);
        return instruction_reg[8*i +: 8];
    endfunction
    function automatic logic [15:0] u16_at(input int i);
        return instruction_reg[8*i +: 16];
    endfunction
    function automatic logic [31:0] u32_at(input int i);
        return instruction_reg[8*i +: 32];
    endfunction

    logic [7:0] opcode;
    logic [2:0] source_buffer, source2_buffer, destination_buffer;
    assign opcode = byte_at(0);
    assign source_buffer = instruction_reg[8*1 +: 3];
    assign source2_buffer = instruction_reg[8*2 +: 3];
    assign destination_buffer = instruction_reg[8*3 +: 3];

    // engines
    logic linear_start, linear_busy, linear_done;
    logic attention_start, attention_busy, attention_done;
    logic add_start, add_busy, add_done;
    logic norm_start, norm_busy, norm_done;
    logic embed_start, embed_busy, embed_done;
    logic pool_start, pool_busy, pool_done;

    logic engine_done;
    assign engine_done = linear_done | attention_done | add_done | norm_done | embed_done | pool_done;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            index_reg <= '0;
            remaining_reg <= '0;
            beat_reg <= '0;
            error_reg <= 1'b0;
            tokens_reg <= '0;
            hidden_reg <= '0;
            program_reg <= '0;
        end else begin
            state_reg <= state_next;
            index_reg <= index_next;
            remaining_reg <= remaining_next;
            beat_reg <= beat_next;
            error_reg <= error_next;
            tokens_reg <= tokens_next;
            hidden_reg <= hidden_next;
            program_reg <= program_next;
        end
    end

    always_ff @(posedge clk) begin
        if (state_reg == FETCH_RECEIVE && read_valid) begin
            instruction_reg[128 * beat_reg +: 128] <= read_data;
        end
    end

    // memory port: the sequencer while fetching, otherwise the running engine
    logic linear_request_valid, attention_request_valid, norm_request_valid, embed_request_valid;
    logic [ADDRESS_WIDTH-1:0] linear_request_address, attention_request_address, norm_request_address;
    logic [ADDRESS_WIDTH-1:0] embed_request_address;
    logic [BEATS_WIDTH-1:0] linear_request_beats, attention_request_beats, norm_request_beats;
    logic [BEATS_WIDTH-1:0] embed_request_beats;
    logic linear_read_ready, attention_read_ready, norm_read_ready, embed_read_ready;
    logic pool_request_valid, pool_read_ready;
    logic [ADDRESS_WIDTH-1:0] pool_request_address;
    logic [BEATS_WIDTH-1:0] pool_request_beats;
    logic fetch_request_valid, fetch_read_ready;

    always_comb begin
        state_next = state_reg;
        index_next = index_reg;
        remaining_next = remaining_reg;
        beat_next = beat_reg;
        error_next = error_reg;
        tokens_next = tokens_reg;
        hidden_next = hidden_reg;
        program_next = program_reg;
        fetch_request_valid = 1'b0;
        fetch_read_ready = 1'b0;
        linear_start = 1'b0;
        attention_start = 1'b0;
        add_start = 1'b0;
        norm_start = 1'b0;
        embed_start = 1'b0;
        pool_start = 1'b0;

        case (state_reg)
            IDLE: begin
                if (start) begin
                    index_next = first_instruction;
                    remaining_next = instruction_count;
                    tokens_next = token_count;
                    hidden_next = hidden;
                    program_next = program_address;
                    error_next = 1'b0;
                    state_next = (instruction_count == '0) ? FINISH : FETCH_REQUEST;
                end
            end

            FETCH_REQUEST: begin
                fetch_request_valid = 1'b1;
                if (read_request_ready) begin
                    beat_next = '0;
                    state_next = FETCH_RECEIVE;
                end
            end

            FETCH_RECEIVE: begin
                fetch_read_ready = 1'b1;
                if (read_valid) begin
                    beat_next = beat_reg + 1'b1;
                    if (read_last) begin
                        state_next = DISPATCH;
                    end
                end
            end

            DISPATCH: begin
                state_next = EXECUTE;
                case (opcode)
                    OP_LINEAR: begin
                        if (u16_at(34) != 16'd16 || u16_at(36) != 16'(TILE_OUT) || byte_at(21) > 8'd1
                            || (FPGA_HEADS == 0 && byte_at(21) != 8'd0)) begin
                            error_next = 1'b1;
                            state_next = FINISH;
                        end else begin
                            linear_start = 1'b1;
                        end
                    end
                    OP_ATTENTION: attention_start = 1'b1;
                    OP_ADD_SKIP: add_start = 1'b1;
                    OP_LAYERNORM: norm_start = 1'b1;
                    OP_EMBED: embed_start = 1'b1;
                    OP_POOL: begin
                        if (FPGA_HEADS != 0) begin
                            pool_start = 1'b1;
                        end else begin
                            error_next = 1'b1;
                            state_next = FINISH;
                        end
                    end
                    OP_END: state_next = FINISH;
                    default: begin
                        error_next = 1'b1;
                        state_next = FINISH;
                    end
                endcase
            end

            EXECUTE: begin
                if (engine_done) begin
                    state_next = NEXT;
                end
            end

            NEXT: begin
                index_next = index_reg + 1'b1;
                remaining_next = remaining_reg - 1'b1;
                state_next = (remaining_reg == 16'd1) ? FINISH : FETCH_REQUEST;
            end

            FINISH: state_next = IDLE;
            default: state_next = IDLE;
        endcase
    end

    assign busy = (state_reg != IDLE);
    assign done = (state_reg == FINISH);
    assign error = error_reg;
    assign instruction_done = (state_reg == NEXT);
    assign instruction_index = index_reg;

    always_comb begin
        read_request_valid = 1'b0;
        read_request_address = '0;
        read_request_beats = '0;
        read_ready = 1'b0;
        if (state_reg == FETCH_REQUEST || state_reg == FETCH_RECEIVE) begin
            read_request_valid = fetch_request_valid;
            read_request_address = program_reg + ADDRESS_WIDTH'(16) + ADDRESS_WIDTH'(64 * index_reg);
            read_request_beats = BEATS_WIDTH'(4);
            read_ready = fetch_read_ready;
        end else if (opcode == OP_LINEAR) begin
            read_request_valid = linear_request_valid;
            read_request_address = linear_request_address;
            read_request_beats = linear_request_beats;
            read_ready = linear_read_ready;
        end else if (opcode == OP_ATTENTION) begin
            read_request_valid = attention_request_valid;
            read_request_address = attention_request_address;
            read_request_beats = attention_request_beats;
            read_ready = attention_read_ready;
        end else if (opcode == OP_LAYERNORM) begin
            read_request_valid = norm_request_valid;
            read_request_address = norm_request_address;
            read_request_beats = norm_request_beats;
            read_ready = norm_read_ready;
        end else if (opcode == OP_EMBED) begin
            read_request_valid = embed_request_valid;
            read_request_address = embed_request_address;
            read_request_beats = embed_request_beats;
            read_ready = embed_read_ready;
        end else if (opcode == OP_POOL) begin
            read_request_valid = pool_request_valid;
            read_request_address = pool_request_address;
            read_request_beats = pool_request_beats;
            read_ready = pool_read_ready;
        end
    end

    // ---------------------------------------------------------------- buffers
    //
    // Seven physical buffers of 128-bit words: X, Q, K, V, CTX hold MAX_TOKENS rows of
    // MAX_HIDDEN INT8 (SMALL_DEPTH words); R and A hold INT16 rows (twice that). G, the
    // FFN intermediate (up to 4 x MAX_HIDDEN wide), has no storage of its own: it lives
    // in Q, K, V and CTX, which are dead between the attention output projection and
    // the end of the layer. G word a is word a / 4 of buffer Q + (a mod 4).

    localparam integer SMALL_DEPTH = MAX_TOKENS * MAX_HIDDEN / 16;
    localparam integer WIDE_DEPTH = 2 * SMALL_DEPTH;
    localparam integer PHYSICAL_NUMBER = 7;

    logic [BUFFER_ADDRESS_WIDTH-1:0] port_address [0:2];   // src, src2, V
    logic [127:0] port_data [0:2];
    logic [2:0] port_buffer [0:2];
    logic [127:0] physical_read_data [0:PHYSICAL_NUMBER-1];

    logic engine_write;
    logic [BUFFER_ADDRESS_WIDTH-1:0] engine_write_address;
    logic [127:0] engine_write_data;
    logic [15:0] engine_write_enable;

    assign port_buffer[0] = source_buffer;
    assign port_buffer[1] = source2_buffer;
    assign port_buffer[2] = BUF_V;

    // logical (buffer, address) -> physical buffer and word
    function automatic logic [2:0] physical_of(input logic [2:0] b,
                                               input logic [BUFFER_ADDRESS_WIDTH-1:0] a);
        return (b == BUF_G) ? (BUF_Q + 3'(a[1:0])) : b;
    endfunction
    function automatic logic [BUFFER_ADDRESS_WIDTH-1:0] offset_of(input logic [2:0] b,
                                                                  input logic [BUFFER_ADDRESS_WIDTH-1:0] a);
        return (b == BUF_G) ? (a >> 2) : a;
    endfunction

    // read ports: 0..2 the engine's, 3 the host's. READ_LATENCY = 3 clocks: the mapped
    // address is registered at each physical buffer, the block RAM answers a clock
    // later, and each port's data is registered after the physical multiplexer.
    logic [2:0] read_physical [0:3];
    logic [BUFFER_ADDRESS_WIDTH-1:0] read_offset [0:3];
    logic [2:0] read_physical_d1 [0:3];
    logic [2:0] read_physical_d2 [0:3];
    logic [127:0] port_data_reg [0:3];

    always_comb begin
        for (int p = 0; p < 3; p++) begin
            read_physical[p] = physical_of(port_buffer[p], port_address[p]);
            read_offset[p] = offset_of(port_buffer[p], port_address[p]);
        end
        read_physical[3] = physical_of(host_buffer, host_address);
        read_offset[3] = offset_of(host_buffer, host_address);
    end

    always_ff @(posedge clk) begin
        for (int p = 0; p < 4; p++) begin
            read_physical_d1[p] <= read_physical[p];
            read_physical_d2[p] <= read_physical_d1[p];
            port_data_reg[p] <= physical_read_data[read_physical_d2[p]];
        end
    end

    for (genvar p = 0; p < 3; p++) begin : gen_port
        assign port_data[p] = port_data_reg[p];
    end
    assign host_read_data = port_data_reg[3];

    // writes: mapped and registered, so they reach the block RAM a clock after the
    // engine (or host) presents them
    logic [2:0] write_physical;
    logic [BUFFER_ADDRESS_WIDTH-1:0] write_offset;
    logic write_request;
    logic [127:0] write_data_mux;
    logic [15:0] write_enable_mux;
    always_comb begin
        if (!busy) begin
            write_physical = physical_of(host_buffer, host_address);
            write_offset = offset_of(host_buffer, host_address);
            write_request = host_write;
            write_data_mux = host_write_data;
            write_enable_mux = host_write_enable;
        end else begin
            write_physical = physical_of(destination_buffer, engine_write_address);
            write_offset = offset_of(destination_buffer, engine_write_address);
            write_request = engine_write;
            write_data_mux = engine_write_data;
            write_enable_mux = engine_write_enable;
        end
    end

    logic [PHYSICAL_NUMBER-1:0] write_select_reg;
    logic [BUFFER_ADDRESS_WIDTH-1:0] write_offset_reg;
    logic [127:0] write_data_reg;
    logic [15:0] write_enable_reg;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            write_select_reg <= '0;
        end else begin
            for (int b = 0; b < PHYSICAL_NUMBER; b++) begin
                write_select_reg[b] <= write_request && (write_physical == 3'(b));
            end
        end
    end
    always_ff @(posedge clk) begin
        write_offset_reg <= write_offset;
        write_data_reg <= write_data_mux;
        write_enable_reg <= write_enable_mux;
    end

    for (genvar b = 0; b < PHYSICAL_NUMBER; b++) begin : gen_buffer
        localparam integer DEPTH = (b == BUF_R || b == BUF_A) ? WIDE_DEPTH : SMALL_DEPTH;
        localparam integer AW = $clog2(DEPTH);
        logic [BUFFER_ADDRESS_WIDTH-1:0] read_address;
        // replicated near the RAMs: each bit drives up to 24 block RAMs
        (* max_fanout = 8 *) logic [BUFFER_ADDRESS_WIDTH-1:0] read_address_reg;

        always_comb begin
            if (!busy) begin
                read_address = read_offset[3];
            end else begin
                // an instruction never has two ports on one physical buffer
                if (read_physical[0] == 3'(b)) begin
                    read_address = read_offset[0];
                end else if (read_physical[1] == 3'(b)) begin
                    read_address = read_offset[1];
                end else begin
                    read_address = read_offset[2];
                end
            end
        end

        always_ff @(posedge clk) begin
            read_address_reg <= read_address;
        end

        activation_buffer #(.DEPTH(DEPTH), .ADDRESS_WIDTH(AW)) buffer_inst (
            .clk(clk),
            .read_address(AW'(read_address_reg)),
            .read_data(physical_read_data[b]),
            .write_enable(write_select_reg[b]),
            .write_address(AW'(write_offset_reg)),
            .write_data(write_data_reg),
            .write_byte_enable(write_enable_reg)
        );
    end

    // ---------------------------------------------------------------- engines

    // the multiplier array, shared by LINEAR and ATTENTION
    logic signed [8:0] mac_a [0:TILE_OUT-1][0:15];
    logic signed [7:0] mac_b [0:15];
    logic signed [16:0] mac_product [0:TILE_OUT-1][0:15];
    logic signed [8:0] linear_mac_a [0:TILE_OUT-1][0:15];
    logic signed [7:0] linear_mac_b [0:15];
    logic signed [8:0] attention_mac_a [0:TILE_OUT-1][0:15];
    logic signed [7:0] attention_mac_b [0:15];
    logic signed [8:0] attention_lane_a [0:ATTENTION_LANES-1][0:15];
    logic signed [16:0] attention_product [0:ATTENTION_LANES-1][0:15];

    // ATTENTION drives the first ATTENTION_LANES lanes of the array
    always_comb begin
        for (int c = 0; c < ATTENTION_LANES; c++) attention_mac_a[c] = attention_lane_a[c];
        for (int c = ATTENTION_LANES; c < TILE_OUT; c++) begin
            for (int r = 0; r < 16; r++) attention_mac_a[c][r] = 9'sd0;
        end
        for (int c = 0; c < ATTENTION_LANES; c++) attention_product[c] = mac_product[c];
    end

    always_comb begin
        if (opcode == OP_ATTENTION) begin
            mac_a = attention_mac_a;
            mac_b = attention_mac_b;
        end else begin
            mac_a = linear_mac_a;
            mac_b = linear_mac_b;
        end
    end

    mac_array #(.LANES(TILE_OUT), .PACK(MAC_PACK)) mac_array_inst (
        .clk(clk),
        .a(mac_a),
        .b(mac_b),
        .product(mac_product)
    );

    logic [BUFFER_ADDRESS_WIDTH-1:0] linear_source, add_a, add_x, norm_source, embed_source, pool_source;
    logic [BUFFER_ADDRESS_WIDTH-1:0] attention_q, attention_k, attention_v;
    logic linear_write, attention_write, add_write, norm_write, embed_write, pool_write;
    logic [BUFFER_ADDRESS_WIDTH-1:0] linear_waddr, attention_waddr, add_waddr, norm_waddr, embed_waddr;
    logic [BUFFER_ADDRESS_WIDTH-1:0] pool_waddr;
    logic [127:0] linear_wdata, attention_wdata, add_wdata, norm_wdata, embed_wdata, pool_wdata;
    logic [15:0] linear_wen, attention_wen, add_wen, norm_wen, embed_wen, pool_wen;

    always_comb begin
        port_address[0] = '0;
        port_address[1] = '0;
        port_address[2] = '0;
        case (opcode)
            OP_LINEAR: port_address[0] = linear_source;
            OP_ADD_SKIP: begin
                port_address[0] = add_a;
                port_address[1] = add_x;
            end
            OP_LAYERNORM: port_address[0] = norm_source;
            OP_EMBED: port_address[0] = embed_source;
            OP_POOL: port_address[0] = pool_source;
            OP_ATTENTION: begin
                port_address[0] = attention_q;
                port_address[1] = attention_k;
                port_address[2] = attention_v;
            end
            default: ;
        endcase
        engine_write = linear_write | attention_write | add_write | norm_write | embed_write
                       | pool_write;
        engine_write_address = linear_write ? linear_waddr : attention_write ? attention_waddr
                               : add_write ? add_waddr : norm_write ? norm_waddr
                               : embed_write ? embed_waddr : pool_waddr;
        engine_write_data = linear_write ? linear_wdata : attention_write ? attention_wdata
                            : add_write ? add_wdata : norm_write ? norm_wdata
                            : embed_write ? embed_wdata : pool_wdata;
        engine_write_enable = linear_write ? linear_wen : attention_write ? attention_wen
                              : add_write ? add_wen : norm_write ? norm_wen
                              : embed_write ? embed_wen : pool_wen;
    end

    linear_engine #(
        .TILE_OUT(TILE_OUT),
        .DRAIN_LANES(DRAIN_LANES),
        .ACCUMULATORS_IN_LUTS(ACCUMULATORS_IN_LUTS),
        .MAX_TOKENS(MAX_TOKENS),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH),
        .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
    ) linear_inst (
        .clk(clk),
        .reset(reset),
        .start(linear_start),
        .busy(linear_busy),
        .done(linear_done),
        .stream_address(ADDRESS_WIDTH'(u32_at(8))),
        .in_dim(u16_at(16)),
        .out_dim(u16_at(18)),
        .shift(instruction_reg[8*20 +: 6]),
        .clamp_low($signed(u32_at(22))),
        .clamp_high($signed(u32_at(26))),
        .lut_address(ADDRESS_WIDTH'(u32_at(30))),
        .raw(FPGA_HEADS != 0 && byte_at(21) == 8'd1),
        .token_count((u16_at(38) != '0) ? 8'(u16_at(38)) : tokens_reg),
        .read_request_valid(linear_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(linear_request_address),
        .read_request_beats(linear_request_beats),
        .read_valid(read_valid),
        .read_ready(linear_read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .source_address(linear_source),
        .source_data(port_data[0]),
        .mac_a(linear_mac_a),
        .mac_b(linear_mac_b),
        .mac_product(mac_product),
        .destination_write(linear_write),
        .destination_address(linear_waddr),
        .destination_data(linear_wdata),
        .destination_enable(linear_wen)
    );

    attention_engine #(
        .LANES(ATTENTION_LANES),
        .MAX_TOKENS(MAX_TOKENS),
        .MAX_HEAD_DIM(MAX_HEAD_DIM),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH),
        .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
    ) attention_inst (
        .clk(clk),
        .reset(reset),
        .start(attention_start),
        .busy(attention_busy),
        .done(attention_done),
        .heads(u16_at(8)),
        .head_dim(u16_at(10)),
        .softmax_multiplier(17'(u32_at(12))),
        .softmax_shift(instruction_reg[8*16 +: 6]),
        .context_multiplier(17'(u32_at(17))),
        .context_shift(instruction_reg[8*21 +: 6]),
        .exp_address(ADDRESS_WIDTH'(u32_at(22))),
        .token_count(tokens_reg),
        .read_request_valid(attention_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(attention_request_address),
        .read_request_beats(attention_request_beats),
        .read_valid(read_valid),
        .read_ready(attention_read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .q_address(attention_q),
        .q_data(port_data[0]),
        .k_address(attention_k),
        .k_data(port_data[1]),
        .v_address(attention_v),
        .v_data(port_data[2]),
        .mac_a(attention_lane_a),
        .mac_b(attention_mac_b),
        .mac_product(attention_product),
        .destination_write(attention_write),
        .destination_address(attention_waddr),
        .destination_data(attention_wdata),
        .destination_enable(attention_wen)
    );

    add_skip_engine #(
        .MAX_TOKENS(MAX_TOKENS),
        .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
    ) add_skip_inst (
        .clk(clk),
        .reset(reset),
        .start(add_start),
        .busy(add_busy),
        .done(add_done),
        .multiplier(17'(u32_at(8))),
        .shift(instruction_reg[8*12 +: 6]),
        .width(hidden_reg),
        .token_count(tokens_reg),
        .a_address(add_a),
        .a_data(port_data[0]),
        .x_address(add_x),
        .x_data(port_data[1]),
        .destination_write(add_write),
        .destination_address(add_waddr),
        .destination_data(add_wdata),
        .destination_enable(add_wen)
    );

    layernorm_engine #(
        .MAX_WIDTH(MAX_HIDDEN),
        .NORM_LANES(NORM_LANES),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH),
        .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
    ) layernorm_inst (
        .clk(clk),
        .reset(reset),
        .start(norm_start),
        .busy(norm_busy),
        .done(norm_done),
        .parameter_address(ADDRESS_WIDTH'(u32_at(8))),
        .width(u16_at(12)),
        .fraction(instruction_reg[8*14 +: 5]),
        .token_count(tokens_reg),
        .read_request_valid(norm_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(norm_request_address),
        .read_request_beats(norm_request_beats),
        .read_valid(read_valid),
        .read_ready(norm_read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .source_address(norm_source),
        .source_data(port_data[0]),
        .destination_write(norm_write),
        .destination_address(norm_waddr),
        .destination_data(norm_wdata),
        .destination_enable(norm_wen)
    );

    embed_engine #(
        .MAX_WIDTH(MAX_HIDDEN),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH),
        .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
    ) embed_inst (
        .clk(clk),
        .reset(reset),
        .start(embed_start),
        .busy(embed_busy),
        .done(embed_done),
        .word_address(ADDRESS_WIDTH'(u32_at(8))),
        .word_stride(u16_at(12)),
        .position_address(ADDRESS_WIDTH'(u32_at(14))),
        .position_stride(u16_at(18)),
        .type_address(ADDRESS_WIDTH'(u32_at(22))),
        .word_multiplier_address(ADDRESS_WIDTH'(u32_at(26))),
        .word_shift(instruction_reg[8*30 +: 6]),
        .position_multiplier_address(ADDRESS_WIDTH'(u32_at(31))),
        .position_shift(instruction_reg[8*35 +: 6]),
        .width(hidden_reg),
        .token_count(tokens_reg),
        .read_request_valid(embed_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(embed_request_address),
        .read_request_beats(embed_request_beats),
        .read_valid(read_valid),
        .read_ready(embed_read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .source_address(embed_source),
        .source_data(port_data[0]),
        .destination_write(embed_write),
        .destination_address(embed_waddr),
        .destination_data(embed_wdata),
        .destination_enable(embed_wen)
    );

    if (FPGA_HEADS != 0) begin : gen_pool
        pool_engine #(
            .ADDRESS_WIDTH(ADDRESS_WIDTH),
            .BEATS_WIDTH(BEATS_WIDTH),
            .BUFFER_ADDRESS_WIDTH(BUFFER_ADDRESS_WIDTH)
        ) pool_inst (
            .clk(clk),
            .reset(reset),
            .start(pool_start),
            .busy(pool_busy),
            .done(pool_done),
            .first_row(u16_at(8)),
            .row_count(u16_at(10)),
            .out_row(u16_at(12)),
            .recip_address(ADDRESS_WIDTH'(u32_at(14))),
            .width(hidden_reg),
            .read_request_valid(pool_request_valid),
            .read_request_ready(read_request_ready),
            .read_request_address(pool_request_address),
            .read_request_beats(pool_request_beats),
            .read_valid(read_valid),
            .read_ready(pool_read_ready),
            .read_data(read_data),
            .read_last(read_last),
            .source_address(pool_source),
            .source_data(port_data[0]),
            .destination_write(pool_write),
            .destination_address(pool_waddr),
            .destination_data(pool_wdata),
            .destination_enable(pool_wen)
        );
    end else begin : gen_no_pool
        assign pool_busy = 1'b0;
        assign pool_done = 1'b0;
        assign pool_request_valid = 1'b0;
        assign pool_request_address = '0;
        assign pool_request_beats = '0;
        assign pool_read_ready = 1'b0;
        assign pool_source = '0;
        assign pool_write = 1'b0;
        assign pool_waddr = '0;
        assign pool_wdata = '0;
        assign pool_wen = '0;
    end

endmodule
