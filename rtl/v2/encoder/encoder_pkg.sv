// Shared definitions of the v2 encoder: opcodes, buffer numbers and the integer
// helpers every engine uses. The arithmetic is exactly src/sysone/v2/ddr_image.py
// (ImageMachine), which is exactly src/sysone/v2/int_encoder.py.
package encoder_pkg;

    // opcodes (ddr_image.py)
    localparam logic [7:0] OP_EMBED = 8'h01;
    localparam logic [7:0] OP_LAYERNORM = 8'h02;
    localparam logic [7:0] OP_LINEAR = 8'h03;
    localparam logic [7:0] OP_ATTENTION = 8'h04;
    localparam logic [7:0] OP_ADD_SKIP = 8'h05;
    localparam logic [7:0] OP_POOL = 8'h06;
    localparam logic [7:0] OP_END = 8'h0F;

    // on-chip buffers (ddr_image.py BUF_*)
    localparam int BUFFER_NUMBER = 8;
    localparam logic [2:0] BUF_X = 3'd0;
    localparam logic [2:0] BUF_Q = 3'd1;
    localparam logic [2:0] BUF_K = 3'd2;
    localparam logic [2:0] BUF_V = 3'd3;
    localparam logic [2:0] BUF_CTX = 3'd4;
    localparam logic [2:0] BUF_R = 3'd5;           // INT16
    localparam logic [2:0] BUF_A = 3'd6;           // INT16
    localparam logic [2:0] BUF_G = 3'd7;

    // clocks from an engine presenting a buffer read address to the data arriving:
    // address register (after the logical -> physical mapping), the block RAM, and a
    // register after the physical -> port multiplexer. Every engine delays its issue
    // flags by this much; the host port has the same latency.
    localparam int READ_LATENCY = 3;

    // (a * M + 2^(S-1)) >>> S, S >= 1. |a * M| < 2^62 for every use in the encoder
    // (largest: LayerNorm-free paths, INT32 accumulator x 17-bit multiplier).
    function automatic logic signed [63:0] requantize(input logic signed [63:0] a,
                                                      input logic [31:0] multiplier,
                                                      input logic [5:0] shift);
        logic signed [63:0] product;
        product = a * $signed({32'd0, multiplier});
        if (shift == 6'd0) begin
            return product;
        end
        return (product + (64'sd1 <<< (shift - 6'd1))) >>> shift;
    endfunction

    function automatic logic signed [63:0] clamp(input logic signed [63:0] value,
                                                 input logic signed [63:0] minimum,
                                                 input logic signed [63:0] maximum);
        if (value < minimum) begin
            return minimum;
        end
        if (value > maximum) begin
            return maximum;
        end
        return value;
    endfunction

    // byte enables of element `index` (1 or 2 bytes) inside its 16-byte word
    function automatic logic [15:0] element_enable(input logic [15:0] index, input logic wide);
        logic [3:0] lane;
        lane = wide ? {index[2:0], 1'b0} : index[3:0];
        return wide ? (16'h0003 << lane) : (16'h0001 << lane);
    endfunction

    // word offset of element `index` inside its row
    function automatic logic [15:0] element_word(input logic [15:0] index, input logic wide);
        return wide ? (index >> 3) : (index >> 4);
    endfunction

    // the element value replicated across a word, so it lands under any byte enable
    function automatic logic [127:0] element_data(input logic signed [15:0] value, input logic wide);
        return wide ? {8{value}} : {16{value[7:0]}};
    endfunction

    // element `index` of a word (INT8 or INT16), sign-extended
    function automatic logic signed [15:0] word_element(input logic [127:0] word,
                                                        input logic [15:0] index,
                                                        input logic wide);
        if (wide) begin
            return $signed(word[16*index[2:0] +: 16]);
        end
        return 16'($signed(word[8*index[3:0] +: 8]));
    endfunction

endpackage
