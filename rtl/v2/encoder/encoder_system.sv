// One encoder request, start to finish, on the board's memory (heads on the host).
//
// The memory link's RUN command (src/sysone/v2/memory_protocol.py) hands over a
// 16-byte descriptor, little-endian:
//
//     bytes 0..3    program address (the image's program section)
//     bytes 4..5    token count n (1 .. MAX_TOKENS)
//     bytes 6..7    hidden size H (multiple of 16, <= MAX_HIDDEN)
//     bytes 8..11   token ids address: n UINT16, written by the host beforehand
//     bytes 12..15  result address: X (n x H INT8 rows) is written here
//
// and the memory port, until run_done. Then:
//   1. the ids are read into buffer X (INT16 elements, where EMBED expects them)
//   2. the program runs from instruction 0 to END (encoder_layer)
//   3. X, the final hidden state, is written to the result address, row after row
//   4. the 16-byte result: bytes 0..3 encoder clocks (EMBED to END), 4..7 clocks for
//      the whole request, 8 status (0 ok, bit 0 sequencer error, bit 1 bad
//      descriptor), 10..11 the instruction the sequencer stopped at
//
// The clock counts are this block's own (memory clock, 75 MHz on the Nexys 4 DDR),
// so they are a board-side latency that does not depend on the Ethernet link.
module encoder_system
    import encoder_pkg::*;
#(
    parameter integer TILE_OUT = 12,
    parameter integer MAX_TOKENS = 128,
    parameter integer MAX_HEAD_DIM = 64,
    parameter integer MAX_HIDDEN = 384,
    parameter integer DRAIN_LANES = 1,
    parameter integer NORM_LANES = 2,
    parameter integer MAC_PACK = 0,
    parameter integer ATTENTION_LANES = TILE_OUT,
    parameter integer ACCUMULATORS_IN_LUTS = 0,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer MAX_WRITE_BEATS = 64
) (
    input logic clk,
    input logic reset,

    input logic run_start,
    input logic [127:0] run_descriptor,
    output logic run_done,                       // one clock, with run_result
    output logic [127:0] run_result,
    output logic busy,

    // memory port (read and write)
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic write_request_valid,
    input logic write_request_ready,
    output logic [ADDRESS_WIDTH-1:0] write_request_address,
    output logic [BEATS_WIDTH-1:0] write_request_beats,
    output logic write_valid,
    input logic write_ready,
    output logic [127:0] write_data
);

    localparam integer BUFFER_ADDRESS_WIDTH = $clog2(4 * MAX_TOKENS * MAX_HIDDEN / 16);

    typedef enum logic [3:0] {
        IDLE,
        CHECK,
        IDS_REQUEST,
        IDS_RECEIVE,
        RUN,
        WAIT,
        OUT_REQUEST,
        OUT_READ,
        OUT_WAIT,
        OUT_BEAT,
        FINISH
    } state_t;

    state_t state_reg;
    logic [ADDRESS_WIDTH-1:0] program_reg, ids_reg, result_reg;
    logic [15:0] tokens_reg, hidden_reg;
    logic [15:0] word_reg, words_reg, chunk_left_reg;
    logic [3:0] wait_reg;
    logic [31:0] encoder_clocks_reg, total_clocks_reg;
    logic [7:0] status_reg;
    logic [15:0] stopped_at_reg;

    // encoder
    logic encoder_start, encoder_busy, encoder_done, encoder_error, instruction_done;
    logic [15:0] instruction_index;
    logic encoder_read_request_valid, encoder_read_ready;
    logic [ADDRESS_WIDTH-1:0] encoder_read_request_address;
    logic [BEATS_WIDTH-1:0] encoder_read_request_beats;
    logic host_write;
    logic [BUFFER_ADDRESS_WIDTH-1:0] host_address;
    logic [127:0] host_read_data;

    encoder_layer #(
        .TILE_OUT(TILE_OUT),
        .MAX_TOKENS(MAX_TOKENS),
        .MAX_HEAD_DIM(MAX_HEAD_DIM),
        .MAX_HIDDEN(MAX_HIDDEN),
        .FPGA_HEADS(0),
        .DRAIN_LANES(DRAIN_LANES),
        .NORM_LANES(NORM_LANES),
        .MAC_PACK(MAC_PACK),
        .ATTENTION_LANES(ATTENTION_LANES),
        .ACCUMULATORS_IN_LUTS(ACCUMULATORS_IN_LUTS),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH)
    ) encoder_inst (
        .clk(clk),
        .reset(reset),
        .start(encoder_start),
        .program_address(program_reg),
        .first_instruction(16'd0),
        .instruction_count(16'hFFFF),            // until END
        .hidden(hidden_reg),
        .token_count(tokens_reg[7:0]),
        .busy(encoder_busy),
        .done(encoder_done),
        .error(encoder_error),
        .instruction_done(instruction_done),
        .instruction_index(instruction_index),
        .read_request_valid(encoder_read_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(encoder_read_request_address),
        .read_request_beats(encoder_read_request_beats),
        .read_valid(read_valid),
        .read_ready(encoder_read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .host_buffer(BUF_X),
        .host_write(host_write),
        .host_address(host_address),
        .host_write_data(read_data),
        .host_write_enable(16'hFFFF),
        .host_read_data(host_read_data)
    );

    // the memory port: the encoder while it runs, otherwise this block
    always_comb begin
        if (state_reg == RUN || state_reg == WAIT) begin
            read_request_valid = encoder_read_request_valid;
            read_request_address = encoder_read_request_address;
            read_request_beats = encoder_read_request_beats;
            read_ready = encoder_read_ready;
        end else begin
            read_request_valid = (state_reg == IDS_REQUEST);
            read_request_address = ids_reg;
            read_request_beats = BEATS_WIDTH'((tokens_reg + 16'd7) >> 3);
            read_ready = (state_reg == IDS_RECEIVE);
        end
    end

    assign host_write = (state_reg == IDS_RECEIVE) && read_valid;
    assign host_address = BUFFER_ADDRESS_WIDTH'(word_reg);
    assign encoder_start = (state_reg == RUN);

    logic [15:0] chunk;
    assign chunk = (words_reg - word_reg > 16'(MAX_WRITE_BEATS)) ? 16'(MAX_WRITE_BEATS)
                                                                : words_reg - word_reg;
    assign write_request_valid = (state_reg == OUT_REQUEST);
    assign write_request_address = result_reg + ADDRESS_WIDTH'({word_reg, 4'b0000});
    assign write_request_beats = BEATS_WIDTH'(chunk);
    assign write_valid = (state_reg == OUT_BEAT);
    assign write_data = host_read_data;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            program_reg <= '0;
            ids_reg <= '0;
            result_reg <= '0;
            tokens_reg <= '0;
            hidden_reg <= '0;
            word_reg <= '0;
            words_reg <= '0;
            chunk_left_reg <= '0;
            wait_reg <= '0;
            encoder_clocks_reg <= '0;
            total_clocks_reg <= '0;
            status_reg <= '0;
            stopped_at_reg <= '0;
        end else begin
            if (state_reg != IDLE) total_clocks_reg <= total_clocks_reg + 1'b1;
            if (encoder_busy) encoder_clocks_reg <= encoder_clocks_reg + 1'b1;
            case (state_reg)
                IDLE: begin
                    if (run_start) begin
                        program_reg <= ADDRESS_WIDTH'(run_descriptor[31:0]);
                        tokens_reg <= run_descriptor[47:32];
                        hidden_reg <= run_descriptor[63:48];
                        ids_reg <= ADDRESS_WIDTH'(run_descriptor[95:64]);
                        result_reg <= ADDRESS_WIDTH'(run_descriptor[127:96]);
                        encoder_clocks_reg <= '0;
                        total_clocks_reg <= '0;
                        status_reg <= '0;
                        stopped_at_reg <= '0;
                        state_reg <= CHECK;
                    end
                end
                CHECK: begin
                    word_reg <= '0;
                    words_reg <= 16'((32'(tokens_reg) * 32'(hidden_reg)) >> 4);
                    if (tokens_reg == '0 || tokens_reg > 16'(MAX_TOKENS) || hidden_reg == '0
                        || hidden_reg > 16'(MAX_HIDDEN) || hidden_reg[3:0] != '0
                        || program_reg[3:0] != '0 || ids_reg[3:0] != '0 || result_reg[3:0] != '0) begin
                        status_reg <= 8'h02;
                        state_reg <= FINISH;
                    end else begin
                        state_reg <= IDS_REQUEST;
                    end
                end
                IDS_REQUEST: if (read_request_ready) state_reg <= IDS_RECEIVE;
                IDS_RECEIVE: begin
                    if (read_valid) begin
                        word_reg <= word_reg + 1'b1;
                        if (read_last) state_reg <= RUN;
                    end
                end
                RUN: state_reg <= WAIT;                  // encoder_start this clock
                WAIT: begin
                    if (encoder_done) begin
                        status_reg <= {7'd0, encoder_error};
                        stopped_at_reg <= instruction_index;
                        word_reg <= '0;
                        state_reg <= OUT_REQUEST;
                    end
                end
                OUT_REQUEST: begin
                    if (write_request_ready) begin
                        chunk_left_reg <= chunk;
                        state_reg <= OUT_READ;
                    end
                end
                OUT_READ: begin                          // host_address = word_reg now
                    wait_reg <= 4'(READ_LATENCY - 1);
                    state_reg <= OUT_WAIT;
                end
                OUT_WAIT: begin
                    if (wait_reg == '0) state_reg <= OUT_BEAT;
                    else wait_reg <= wait_reg - 1'b1;
                end
                OUT_BEAT: begin
                    if (write_ready) begin
                        word_reg <= word_reg + 1'b1;
                        chunk_left_reg <= chunk_left_reg - 1'b1;
                        if (word_reg + 1'b1 == words_reg) begin
                            state_reg <= FINISH;
                        end else if (chunk_left_reg == 16'd1) begin
                            state_reg <= OUT_REQUEST;
                        end else begin
                            state_reg <= OUT_READ;
                        end
                    end
                end
                FINISH: state_reg <= IDLE;
                default: state_reg <= IDLE;
            endcase
        end
    end

    assign busy = (state_reg != IDLE);
    assign run_done = (state_reg == FINISH);
    assign run_result = {32'd0, stopped_at_reg, 8'd0, status_reg, total_clocks_reg, encoder_clocks_reg};

endmodule
