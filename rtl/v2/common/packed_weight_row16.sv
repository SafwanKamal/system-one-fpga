// Experimental row unpacker; not connected to any deployed design or DDR ABI.
// Sixteen two's-complement codes, least-significant code/bit first, matching
// functiongemma_packed_weights.pack_codes. Unused high input bits are ignored.
// One elastic register: one row/cycle without stalls, payload stable on stall.
module packed_weight_row16 #(
    parameter integer BITS = 7
) (
    input  logic clk, reset,
    input  logic in_valid,
    output logic in_ready,
    input  logic [127:0] packed_row,
    output logic out_valid,
    input  logic out_ready,
    output logic [127:0] signed_bytes
);
    wire [127:0] unpacked;
    assign in_ready = !reset && (!out_valid || out_ready);
    for (genvar i=0; i<16; i=i+1) begin : code
        assign unpacked[8*i +: 8] =
            {{(8-BITS){packed_row[BITS*i+BITS-1]}}, packed_row[BITS*i +: BITS]};
    end
    always_ff @(posedge clk) begin
        if (reset) begin
            out_valid <= 1'b0;
            signed_bytes <= 128'b0;
        end else if (in_ready) begin
            out_valid <= in_valid;
            if (in_valid) signed_bytes <= unpacked;
        end
    end
`ifndef SYNTHESIS
    initial begin
        if (BITS != 6 && BITS != 7 && BITS != 8)
            $fatal(1, "BITS must be 6, 7 or 8");
    end
`endif
endmodule
