// The encoder's multiplier array, shared by the engines that need it (one runs at a
// time): LANES x 16 signed products a[c][r] * b[r], registered.
//
//   LINEAR      a = the weight tile (16 inputs x LANES output channels), b = one
//               token's 16 inputs                    -> 16-term dot product per lane
//   ATTENTION   scores: a = LANES queries' 16 dims, b = one key's 16 dims
//               P.V:    a = each query's probability (broadcast over r), b = one
//               value word                           -> outer product
//
// a is 9-bit signed so the attention probabilities (0..255) fit; b is INT8. On a
// 7-series part each product maps to one DSP48E1 (25 x 18) or to LUTs; the adder
// trees stay in the engines because they differ.
module mac_array #(
    parameter integer LANES = 12
) (
    input logic clk,
    input logic signed [8:0] a [0:LANES-1][0:15],
    input logic signed [7:0] b [0:15],
    output logic signed [16:0] product [0:LANES-1][0:15]
);

    (* use_dsp = "yes" *) logic signed [16:0] product_reg [0:LANES-1][0:15];

    always_ff @(posedge clk) begin
        for (int c = 0; c < LANES; c++) begin
            for (int r = 0; r < 16; r++) begin
                product_reg[c][r] <= a[c][r] * b[r];
            end
        end
    end

    assign product = product_reg;

endmodule
