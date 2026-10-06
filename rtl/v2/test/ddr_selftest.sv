// External-memory bring-up test on the v2 memory port.
//
// Fills REGION_BYTES of memory with an address-dependent pattern, reads it all
// back, and counts beats that differ. Write and read phases are timed separately,
// which gives the sustained bandwidth the v2 encoder will actually see when it
// streams its weights (REQUEST_BEATS-beat bursts, sequential addresses).
//
// The pattern for the beat at byte address A is four 32-bit words
//     {A ^ 32'hA5A5_A5A5, ~A, A * 32'h9E37_79B1, A + SEED}
// so a stuck, shorted or swapped address or data line shows up as errors, and
// SEED changes between runs so a stale image from a previous run cannot pass.
//
// Platform-neutral: the Nexys 4 DDR top connects it to mig_memory_port; a KR260
// top would connect it to an AXI adapter.
module ddr_selftest #(
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer DATA_WIDTH = 128,
    parameter integer BEATS_WIDTH = 16,
    parameter longint REGION_BYTES = 64'd134217728,     // 128 MiB
    parameter integer REQUEST_BEATS = 64
) (
    input logic clk,
    input logic reset,
    input logic start,
    input logic [31:0] seed,

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,

    input logic read_valid,
    output logic read_ready,
    input logic [DATA_WIDTH-1:0] read_data,
    input logic read_last,

    output logic write_request_valid,
    input logic write_request_ready,
    output logic [ADDRESS_WIDTH-1:0] write_request_address,
    output logic [BEATS_WIDTH-1:0] write_request_beats,

    output logic write_valid,
    input logic write_ready,
    output logic [DATA_WIDTH-1:0] write_data,

    output logic busy,
    output logic write_done,
    output logic done,
    output logic passed,
    output logic [31:0] error_count,
    output logic [39:0] write_cycles,
    output logic [39:0] read_cycles
);

    localparam integer BEAT_BYTES = DATA_WIDTH / 8;
    localparam longint TOTAL_BEATS = REGION_BYTES / BEAT_BYTES;
    localparam longint REQUESTS = TOTAL_BEATS / REQUEST_BEATS;
    localparam integer REQUEST_BYTES = REQUEST_BEATS * BEAT_BYTES;

    typedef enum logic [2:0] {
        IDLE,
        WRITE_REQUEST,
        WRITE_DATA,
        READ_PHASE,
        FINISHED
    } state_t;

    state_t state_reg, state_next;

    logic [ADDRESS_WIDTH-1:0] request_address_reg, request_address_next;
    logic [ADDRESS_WIDTH-1:0] beat_address_reg, beat_address_next;     // write data / read check
    logic [BEATS_WIDTH-1:0] beat_count_reg, beat_count_next;
    logic [39:0] requests_left_reg, requests_left_next;
    logic [39:0] beats_left_reg, beats_left_next;                      // read beats to check
    logic [31:0] error_count_reg, error_count_next;
    logic [39:0] write_cycles_reg, write_cycles_next;
    logic [39:0] read_cycles_reg, read_cycles_next;
    logic [31:0] seed_reg, seed_next;
    logic write_done_reg, write_done_next;


    function automatic logic [DATA_WIDTH-1:0] pattern(input logic [ADDRESS_WIDTH-1:0] address,
                                                      input logic [31:0] run_seed);
        logic [31:0] a;
        logic [127:0] word;
        a = 32'(address);
        word = {a ^ 32'hA5A5_A5A5, ~a, a * 32'h9E37_79B1, a + run_seed};
        return DATA_WIDTH'(word);
    endfunction


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            request_address_reg <= '0;
            beat_address_reg <= '0;
            beat_count_reg <= '0;
            requests_left_reg <= '0;
            beats_left_reg <= '0;
            error_count_reg <= '0;
            write_cycles_reg <= '0;
            read_cycles_reg <= '0;
            seed_reg <= '0;
            write_done_reg <= 1'b0;
        end else begin
            state_reg <= state_next;
            request_address_reg <= request_address_next;
            beat_address_reg <= beat_address_next;
            beat_count_reg <= beat_count_next;
            requests_left_reg <= requests_left_next;
            beats_left_reg <= beats_left_next;
            error_count_reg <= error_count_next;
            write_cycles_reg <= write_cycles_next;
            read_cycles_reg <= read_cycles_next;
            seed_reg <= seed_next;
            write_done_reg <= write_done_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        request_address_next = request_address_reg;
        beat_address_next = beat_address_reg;
        beat_count_next = beat_count_reg;
        requests_left_next = requests_left_reg;
        beats_left_next = beats_left_reg;
        error_count_next = error_count_reg;
        write_cycles_next = write_cycles_reg;
        read_cycles_next = read_cycles_reg;
        seed_next = seed_reg;
        write_done_next = write_done_reg;

        write_request_valid = 1'b0;
        write_valid = 1'b0;
        read_request_valid = 1'b0;
        read_ready = 1'b0;

        case (state_reg)
            IDLE: begin
                if (start) begin
                    seed_next = seed;
                    request_address_next = '0;
                    beat_address_next = '0;
                    requests_left_next = 40'(REQUESTS);
                    error_count_next = '0;
                    write_cycles_next = '0;
                    read_cycles_next = '0;
                    write_done_next = 1'b0;
                    state_next = WRITE_REQUEST;
                end
            end

            WRITE_REQUEST: begin
                write_cycles_next = write_cycles_reg + 1'b1;
                write_request_valid = 1'b1;
                if (write_request_ready) begin
                    request_address_next = request_address_reg + REQUEST_BYTES[ADDRESS_WIDTH-1:0];
                    beat_count_next = BEATS_WIDTH'(REQUEST_BEATS);
                    state_next = WRITE_DATA;
                end
            end

            WRITE_DATA: begin
                write_cycles_next = write_cycles_reg + 1'b1;
                write_valid = 1'b1;
                if (write_ready) begin
                    beat_address_next = beat_address_reg + BEAT_BYTES[ADDRESS_WIDTH-1:0];
                    beat_count_next = beat_count_reg - 1'b1;
                    if (beat_count_reg == 1) begin
                        requests_left_next = requests_left_reg - 1'b1;
                        if (requests_left_reg == 1) begin
                            write_done_next = 1'b1;
                            request_address_next = '0;
                            beat_address_next = '0;
                            requests_left_next = 40'(REQUESTS);
                            beats_left_next = 40'(TOTAL_BEATS);
                            state_next = READ_PHASE;
                        end else begin
                            state_next = WRITE_REQUEST;
                        end
                    end
                end
            end

            READ_PHASE: begin
                // requests and data checking run concurrently
                read_cycles_next = read_cycles_reg + 1'b1;
                read_request_valid = (requests_left_reg != '0);
                if (read_request_valid && read_request_ready) begin
                    request_address_next = request_address_reg + REQUEST_BYTES[ADDRESS_WIDTH-1:0];
                    requests_left_next = requests_left_reg - 1'b1;
                end
                read_ready = 1'b1;
                if (read_valid) begin
                    if (read_data != pattern(beat_address_reg, seed_reg)
                        && error_count_reg != 32'hFFFF_FFFF) begin
                        error_count_next = error_count_reg + 1'b1;
                    end
                    beat_address_next = beat_address_reg + BEAT_BYTES[ADDRESS_WIDTH-1:0];
                    beats_left_next = beats_left_reg - 1'b1;
                    if (beats_left_reg == 1) begin
                        state_next = FINISHED;
                    end
                end
            end

            FINISHED: begin
                if (start) begin
                    state_next = IDLE;
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign write_request_address = request_address_reg;
    assign write_request_beats = BEATS_WIDTH'(REQUEST_BEATS);
    assign write_data = pattern(beat_address_reg, seed_reg);
    assign read_request_address = request_address_reg;
    assign read_request_beats = BEATS_WIDTH'(REQUEST_BEATS);

    assign busy = (state_reg != IDLE) && (state_reg != FINISHED);
    assign write_done = write_done_reg;
    assign done = (state_reg == FINISHED);
    assign passed = done && (error_count_reg == '0);
    assign error_count = error_count_reg;
    assign write_cycles = write_cycles_reg;
    assign read_cycles = read_cycles_reg;

endmodule
