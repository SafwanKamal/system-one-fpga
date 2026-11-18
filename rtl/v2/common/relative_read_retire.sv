// Experimental single-request SYS3 read retirement. Local validation faults
// cannot overtake an outstanding DDR read. Response faults drain the current
// read and poison this channel until coordinated adapter/memory-port reset.
// No timeout is imposed: an unresponsive AXI slave still requires a watchdog.
module relative_read_retire #(
    parameter integer BEATS_WIDTH = 16
) (
    input logic clk, reset,
    input logic [39:0] model_base,
    input logic [32:0] model_bytes,
    input logic request_valid,
    output logic request_ready,
    input logic [31:0] request_offset,
    input logic [32:0] request_bytes,
    output logic memory_valid,
    input logic memory_ready,
    output logic [39:0] memory_address,
    output logic [BEATS_WIDTH-1:0] memory_beats,
    input logic memory_read_valid,
    output logic memory_read_ready,
    input logic [127:0] memory_read_data,
    input logic memory_read_last,
    input logic memory_response_error,
    output logic read_valid,
    input logic read_ready,
    output logic [127:0] read_data,
    output logic read_last,
    output logic completion_valid,
    input logic completion_ready,
    output logic [1:0] completion_code,
    output logic poisoned
);
    typedef enum logic [2:0] {IDLE, ACTIVE, WAIT_STATUS, DONE, POISON} state_t;
    state_t state;
    logic adapter_ready, adapter_valid, error_valid, error_ready, issued;
    logic [1:0] error_code;
    assign request_ready = !reset && state == IDLE && !memory_response_error && adapter_ready;
    relative_read_request #(.BEATS_WIDTH(BEATS_WIDTH)) adapter (
        .clk, .reset, .model_base, .model_bytes,
        .request_valid(request_valid && state == IDLE && !memory_response_error),
        .request_ready(adapter_ready), .request_offset, .request_bytes,
        .memory_valid(adapter_valid), .memory_ready(memory_ready && state == ACTIVE),
        .memory_address, .memory_beats, .error_valid, .error_ready, .error_code);
    assign memory_valid = !reset && state == ACTIVE && adapter_valid;
    assign error_ready = !reset && state == ACTIVE && !issued;
    assign read_valid = !reset && state == ACTIVE && issued && memory_read_valid;
    assign memory_read_ready = !reset && state == ACTIVE && issued && read_ready;
    assign read_data = memory_read_data;
    assign read_last = memory_read_last;
    assign completion_valid = !reset && state == DONE;
    assign poisoned = state == POISON || (state == IDLE && memory_response_error);
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
            issued <= 0;
            completion_code <= 0;
        end else begin
            case (state)
                IDLE: if (request_valid && request_ready) begin
                    state <= ACTIVE;
                    issued <= 0;
                end
                ACTIVE: begin
                    if (memory_valid && memory_ready) issued <= 1;
                    if (error_valid && error_ready) begin
                        completion_code <= error_code;
                        state <= DONE;
                    end else if (read_valid && read_ready && memory_read_last)
                        state <= WAIT_STATUS;
                end
                // Sample after the last-beat handshake, so sticky RRESP status
                // asserted on that same edge cannot be missed at retirement.
                WAIT_STATUS: begin
                    completion_code <= memory_response_error ? 2'd3 : 2'd0;
                    state <= DONE;
                end
                DONE: if (completion_ready)
                    state <= completion_code == 3 ? POISON : IDLE;
                POISON: state <= POISON;
                default: state <= POISON;
            endcase
        end
    end
endmodule
