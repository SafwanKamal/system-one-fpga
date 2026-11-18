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
    parameter integer PACK = 0,
    // Optional operand stage before the multiply: one additional clock, II = 1.
    // Engines must use MAC_LATENCY = 1 + INPUT_REGISTERS to align their tags.
    parameter integer INPUT_REGISTERS = 0
) (
    input logic clk,
    input logic signed [8:0] a [0:LANES-1][0:15],
    input logic signed [7:0] b [0:15],
    output logic signed [16:0] product [0:LANES-1][0:15]
);

    logic signed [8:0] operand_a [0:LANES-1][0:15];
    logic signed [7:0] operand_b [0:15];
    if (INPUT_REGISTERS != 0) begin : gen_inputs
        logic signed [8:0] a_reg [0:LANES-1][0:15];
        (* max_fanout = 8 *) logic signed [7:0] b_reg [0:15];
        always_ff @(posedge clk) begin
            a_reg <= a;
            b_reg <= b;
        end
        assign operand_a = a_reg;
        assign operand_b = b_reg;
    end else begin : gen_direct
        assign operand_a = a;
        assign operand_b = b;
    end

    if (PACK == 0) begin : gen_plain
        (* use_dsp = "yes" *) logic signed [16:0] product_reg [0:LANES-1][0:15];

        always_ff @(posedge clk) begin
            for (int c = 0; c < LANES; c++) begin
                for (int r = 0; r < 16; r++) begin
                    product_reg[c][r] <= operand_a[c][r] * operand_b[r];
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
                    high = 25'(operand_a[2*k][r]) <<< 16;
                    low = 25'(operand_a[2*k + 1][r]);
                    packed_reg[k][r] <= (high + low) * 43'(operand_b[r]);
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

// Signed wide product split into two independently registered <=18-bit halves.
// Three-clock latency (operand register, parallel products, signed combine).
module split_product_pipeline #(
    parameter integer LANES=4,
    parameter integer A_WIDTH=21,
    parameter integer B_WIDTH=32,
    parameter integer OUT_WIDTH=54
) (
    input logic clk,
    input logic signed [A_WIDTH-1:0] a [0:LANES-1],
    input logic signed [B_WIDTH-1:0] b [0:LANES-1],
    output logic signed [OUT_WIDTH-1:0] product [0:LANES-1]
);
    logic signed [A_WIDTH-1:0] a_reg [0:LANES-1];
    logic signed [B_WIDTH-1:0] b_reg [0:LANES-1];
    (* use_dsp="yes" *) logic signed [A_WIDTH+17-1:0] low [0:LANES-1];
    (* use_dsp="yes" *) logic signed [A_WIDTH+B_WIDTH-16-1:0] high [0:LANES-1];
    always_ff @(posedge clk) begin
        for(int c=0;c<LANES;c++) begin
            a_reg[c]<=a[c];b_reg[c]<=b[c];
            low[c]<=a_reg[c]*$signed({1'b0,b_reg[c][15:0]});
            high[c]<=a_reg[c]*$signed(b_reg[c][B_WIDTH-1:16]);
            product[c]<=OUT_WIDTH'(low[c])+(OUT_WIDTH'(high[c])<<<16);
        end
    end
`ifndef SYNTHESIS
    initial if(B_WIDTH<=16 || OUT_WIDTH<A_WIDTH+B_WIDTH)
        $fatal(1,"split_product_pipeline width contract violated");
`endif
endmodule

// Four registered levels, one signed addition per stage. Output is the same
// WIDTH-bit modular sum as the original sixteen-product reduction.
module dot16_pipeline #(
    parameter integer LANES = 32,
    parameter integer WIDTH = 24
) (
    input logic clk,
    input logic signed [16:0] product [0:LANES-1][0:15],
    output logic signed [WIDTH-1:0] sum [0:LANES-1]
);
    // Full signed 17-bit operands need 18/19/20/21 bits at each level.
    // Smaller WIDTH retains modular addition; larger WIDTH sign-extends.
    localparam integer PAIR_WIDTH = WIDTH < 18 ? WIDTH : 18;
    localparam integer QUAD_WIDTH = WIDTH < 19 ? WIDTH : 19;
    localparam integer OCTET_WIDTH = WIDTH < 20 ? WIDTH : 20;
    localparam integer SUM_WIDTH = WIDTH < 21 ? WIDTH : 21;
    logic signed [PAIR_WIDTH-1:0] pairs [0:LANES-1][0:7];
    logic signed [QUAD_WIDTH-1:0] quads [0:LANES-1][0:3];
    logic signed [OCTET_WIDTH-1:0] octets [0:LANES-1][0:1];
    always_ff @(posedge clk) begin
        for (int c = 0; c < LANES; c++) begin
            for (int r = 0; r < 8; r++)
                pairs[c][r] <= PAIR_WIDTH'(product[c][2*r]) + PAIR_WIDTH'(product[c][2*r+1]);
            for (int r = 0; r < 4; r++)
                quads[c][r] <= QUAD_WIDTH'(pairs[c][2*r]) + QUAD_WIDTH'(pairs[c][2*r+1]);
            for (int r = 0; r < 2; r++)
                octets[c][r] <= OCTET_WIDTH'(quads[c][2*r]) + OCTET_WIDTH'(quads[c][2*r+1]);
            sum[c] <= WIDTH'($signed(SUM_WIDTH'(octets[c][0]) + SUM_WIDTH'(octets[c][1])));
        end
    end
endmodule
