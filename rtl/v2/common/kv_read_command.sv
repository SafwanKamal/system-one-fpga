// Experimental logical KV read command -> serial relative descriptors.
// No AXI data path, executor, decoder or deployed-app integration.
// One command outstanding. Window context is captured with the logical slice;
// local span faults retire without reaching the chunker. Downstream must retire
// each accepted descriptor once and in order before another descriptor issues.
module kv_read_command #(
    parameter integer BEATS_WIDTH = 16
) (
    input logic clk, reset,
    input logic in_valid,
    output logic in_ready,
    input logic [39:0] model_base,
    input logic [32:0] window_bytes,
    input logic [31:0] cache_offset, row_stride, capacity,
    input logic [15:0] layers, layer,
    input logic value_matrix,
    input logic [31:0] first_token, token_count,
    output logic descriptor_valid,
    input logic descriptor_ready,
    output logic [39:0] descriptor_model_base,
    output logic [32:0] descriptor_model_bytes,
    output logic [31:0] descriptor_offset,
    output logic [32:0] descriptor_bytes,
    input logic completion_valid,
    output logic completion_ready,
    input logic [1:0] completion_code,
    output logic done_valid,
    input logic done_ready,
    output logic [1:0] done_code,
    output logic done_local_error,
    output logic [32:0] completed_bytes
);
    typedef enum logic [1:0] {IDLE, WAIT_SPAN, ACTIVE, LOCAL_DONE} state_t;
    state_t state;
    logic planner_ready, span_valid, span_ready, chunk_ready;
    logic [31:0] span_offset;
    logic [32:0] span_bytes, held_window, chunk_completed;
    logic [39:0] held_base;
    logic [1:0] span_error, local_code, chunk_code;
    logic chunk_descriptor_valid, chunk_completion_ready, chunk_done_valid;

    assign in_ready = !reset && state == IDLE && planner_ready;
    assign span_ready = !reset && state == WAIT_SPAN && (span_error != 0 || chunk_ready);
    assign descriptor_valid = !reset && state == ACTIVE && chunk_descriptor_valid;
    assign completion_ready = !reset && state == ACTIVE && chunk_completion_ready;
    assign done_valid = !reset && (state == LOCAL_DONE || (state == ACTIVE && chunk_done_valid));
    assign done_local_error = state == LOCAL_DONE;
    assign done_code = state == LOCAL_DONE ? local_code : chunk_code;
    assign completed_bytes = state == LOCAL_DONE ? 33'd0 : chunk_completed;

    kv_cache_span planner (
        .clk, .reset, .in_valid(in_valid && in_ready), .in_ready(planner_ready),
        .window_bytes, .cache_offset, .row_stride, .capacity, .layers, .layer,
        .value_matrix, .first_token, .token_count, .out_valid(span_valid),
        .out_ready(span_ready), .offset(span_offset), .bytes(span_bytes), .error_code(span_error)
    );
    relative_read_chunker #(.BEATS_WIDTH(BEATS_WIDTH)) chunker (
        .clk, .reset,
        .operation_valid(!reset && state == WAIT_SPAN && span_valid && span_error == 0),
        .operation_ready(chunk_ready), .model_base(held_base), .model_bytes(held_window),
        .operation_offset(span_offset), .operation_bytes(span_bytes),
        .descriptor_valid(chunk_descriptor_valid),
        .descriptor_ready(descriptor_ready && state == ACTIVE && !reset),
        .descriptor_model_base, .descriptor_model_bytes, .descriptor_offset, .descriptor_bytes,
        .completion_valid(completion_valid && state == ACTIVE && !reset),
        .completion_ready(chunk_completion_ready), .completion_code,
        .done_valid(chunk_done_valid), .done_ready(done_ready && state == ACTIVE && !reset),
        .done_code(chunk_code), .completed_bytes(chunk_completed)
    );
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
            held_base <= 0;
            held_window <= 0;
            local_code <= 0;
        end else case (state)
            IDLE: if (in_valid && in_ready) begin
                held_base <= model_base;
                held_window <= window_bytes;
                state <= WAIT_SPAN;
            end
            WAIT_SPAN: if (span_valid && span_ready) begin
                if (span_error != 0) begin
                    local_code <= span_error;
                    state <= LOCAL_DONE;
                end else state <= ACTIVE;
            end
            ACTIVE: if (chunk_done_valid && done_ready) state <= IDLE;
            LOCAL_DONE: if (done_ready) state <= IDLE;
            default: begin local_code <= 3; state <= LOCAL_DONE; end
        endcase
    end
endmodule
