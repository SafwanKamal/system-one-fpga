// Experimental SYS3 read descriptor adapter. Not connected to the v2 executor.
// Rejects window faults and byte lengths that would truncate at the existing
// 16-bit AXI-port beat-count interface. The caller must chunk longer transfers.
// Errors use their own valid/ready completion channel and never reach memory.
module relative_read_request #(
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
    output logic error_valid,
    input logic error_ready,
    output logic [1:0] error_code
);
    localparam logic [32:0] MAX_REQUEST_BYTES = 33'(((64'd1 << BEATS_WIDTH)-1)*16);
    logic translated_valid, translated_ready, translator_ready, window_error;
    logic [32:0] translated_bytes;
    logic capacity_error, rejected;

    model_address_window window_inst (
        .clk, .reset, .model_base, .model_bytes,
        .in_valid(request_valid && !reset), .in_ready(translator_ready),
        .offset(request_offset), .bytes(request_bytes),
        .out_valid(translated_valid), .out_ready(translated_ready),
        .address(memory_address), .length(translated_bytes), .out_error(window_error)
    );
    assign capacity_error = translated_bytes > MAX_REQUEST_BYTES;
    assign rejected = window_error || capacity_error;
    assign request_ready = !reset && translator_ready;
    assign memory_valid = !reset && translated_valid && !rejected;
    assign memory_beats = BEATS_WIDTH'(translated_bytes >> 4);
    assign error_valid = !reset && translated_valid && rejected;
    assign error_code = window_error ? 2'd1 : capacity_error ? 2'd2 : 2'd0;
    assign translated_ready = !reset && (rejected ? error_ready : memory_ready);

    initial begin
        if (BEATS_WIDTH < 1 || BEATS_WIDTH > 28)
            $fatal(1, "BEATS_WIDTH must fit the 33-bit byte-count contract");
    end
endmodule
