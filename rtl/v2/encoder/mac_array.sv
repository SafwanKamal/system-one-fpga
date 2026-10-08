// The encoder's multiplier array, shared by the engines that need it (one runs at a
// time): LANES x 16 signed products a[c][r] * b[r], registered.
//
//   LINEAR      a = the weight tile (16 inputs x LANES output channels), b = one
//               token's 16 inputs                    -> 16-term dot product per lane
//   ATTENTION   scores: a = LANES queries' 16 dims, b = one key's 16 dims
//               P.V:    a = each query's probability (broadcast over r), b = one
//               value word                           -> outer product
//
// a is 9-bit signed so the attention probabilities (0..255) fit; b is INT8. The
// adder trees stay in the engines because they differ.
//
// PACK = 0: one DSP48E1 (25 x 18) per product.
// PACK = 1: two lanes per DSP48E1, as both share b[r]: the pre-adder forms
//   A + D = a[2k] * 2^16 + a[2k+1] (25 bits: |a| <= 255), P = (A + D) * b, and
//   a[2k+1] * b = P[15:0] (signed; |a * b| <= 255 * 128 < 2^15),
//   a[2k]   * b = P[42:16] + P[15]  (the borrow of the low product).
// Exact for every a in [-128, 255] (INT8 weights and queries, probabilities 0..255)
// and b in [-128, 127]: |a * b| <= 32,640 fits the 16-bit low half (a = -256 would not).
// Checked exhaustively in Python and against PACK = 0 on random operands. LANES
// products need LANES / 2 x 16 DSPs, so the Nexys 4 DDR's 240 fit a 24 x 16 array.
module mac_array #(
    parameter integer LANES = 12,
    parameter integer PACK = 0
) (
    input logic clk,
    input logic signed [8:0] a [0:LANES-1][0:15],
    input logic signed [7:0] b [0:15],
    output logic signed [16:0] product [0:LANES-1][0:15]
);

    if (PACK == 0) begin : gen_plain
        (* use_dsp = "yes" *) logic signed [16:0] product_reg [0:LANES-1][0:15];

        always_ff @(posedge clk) begin
            for (int c = 0; c < LANES; c++) begin
                for (int r = 0; r < 16; r++) begin
                    product_reg[c][r] <= a[c][r] * b[r];
                end
            end
        end

        assign product = product_reg;
    end else begin : gen_packed
        localparam integer PAIRS = LANES / 2;
        (* use_dsp = "yes" *) logic signed [42:0] packed_reg [0:PAIRS-1][0:15];

        always_ff @(posedge clk) begin
            for (int k = 0; k < PAIRS; k++) begin
                for (int r = 0; r < 16; r++) begin
                    logic signed [24:0] high, low;
                    high = 25'(a[2*k][r]) <<< 16;
                    low = 25'(a[2*k + 1][r]);
                    packed_reg[k][r] <= (high + low) * 43'(b[r]);
                end
            end
        end

        always_comb begin
            for (int k = 0; k < PAIRS; k++) begin
                for (int r = 0; r < 16; r++) begin
                    product[2*k + 1][r] = 17'($signed(packed_reg[k][r][15:0]));
                    product[2*k][r] = 17'(packed_reg[k][r][42:16] + 27'(packed_reg[k][r][15]));
                end
            end
        end

`ifndef SYNTHESIS
        initial begin
            if (LANES % 2 != 0) $fatal(1, "mac_array: PACK needs an even LANES (%0d)", LANES);
        end
`endif
    end

endmodule
