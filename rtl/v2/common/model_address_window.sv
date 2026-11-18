// Experimental SYS3 translator, not connected to the deployed v2 datapath.
// out_error is a completion status: an integrating consumer MUST reject errored
// requests before AXI. The output tuple remains stable until out_ready.
module model_address_window (
    input logic clk,
    input logic reset,
    input logic [39:0] model_base,
    input logic [32:0] model_bytes,
    input logic in_valid,
    output logic in_ready,
    input logic [31:0] offset,
    input logic [32:0] bytes,
    output logic out_valid,
    input logic out_ready,
    output logic [39:0] address,
    output logic [32:0] length,
    output logic out_error
);
    logic [40:0] physical, window_end;
    logic [33:0] span;
    logic invalid;
    always_comb begin
        physical = {1'b0,model_base} + 41'(offset);
        window_end = {1'b0,model_base} + 41'(model_bytes);
        span = 34'(offset) + 34'(bytes);
        invalid = model_base[9:0] != 0 || model_bytes == 0
            || model_bytes > 33'h100000000
            || window_end > 41'h10000000000
            || bytes == 0 || offset[3:0] != 0 || bytes[3:0] != 0
            || span > 34'(model_bytes) || physical[40];
    end
    assign in_ready = !out_valid || out_ready;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            out_valid <= 0;
            address <= 0;
            length <= 0;
            out_error <= 0;
        end else if (in_ready) begin
            out_valid <= in_valid;
            if (in_valid) begin
                address <= physical[39:0];
                length <= bytes;
                out_error <= invalid;
            end
        end
    end
endmodule
