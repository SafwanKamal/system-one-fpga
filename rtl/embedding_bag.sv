// Embedding lookup, sum, and mean pool with pool_gain.
//
// This is the RTL side of steps 1 and 2 of QuantModel._forward_int_block:
//     summed[d] = sum over features of embedding[index, d]
//     pooled[d] = (summed[d] * reciprocal[n] + 2^(S-1)) >>> S,   S = 16 - POOL_GAIN
//
// One table row (DIMENSION x INT4) is read per clock and every dimension accumulates
// in parallel. The row is split into 252 + 4 bits: a single 256-bit row would round
// up to 8 x 36-bit BRAM columns (128 RAMB36) and leave no room for the head.
//
// The 252-bit part is stored as 4096 words of 4 x 252 bits (bank b holds rows
// b*4096 .. b*4096+4095, bank 0 in the MSBs) and the bank is picked after the read.
// Left as a 16384-deep array, Vivado maps it in 16K x 2 mode, 126 RAMB36; at 4096
// deep every aspect ratio it can pick packs 1008 bits into 112 RAMB36. The 4-bit
// part is 2 RAMB36 in 16K x 2 mode, so the table is 114 in total.
//
// Why POOL_GAIN exists: a mean of ~96 INT4 codes concentrates, and without the gain
// the pooled value spans only about 3 bits. The gain refills the activation width and
// is folded back out in the first requantisation multiplier, so it costs one shift.
//
// Widths come from worst-case bounds, not from the measured maxima:
//     |sum| <= 7 * 256 = 1792                  -> 12 bits signed
//     |pooled| <= 7 * 2^POOL_GAIN (+1)         -> 10 bits signed for POOL_GAIN <= 5
module embedding_bag #(
    parameter integer ROW_NUMBER       = 16384,
    parameter integer DIMENSION        = 64,
    parameter integer INDEX_WIDTH      = 14,
    parameter integer MAXIMUM_FEATURES = 256,
    parameter integer RECIPROCAL_SHIFT = 16,
    parameter integer POOL_GAIN        = 5,

    parameter string EMBEDDING_LOW_FILE  = "embedding_low.mem",
    parameter string EMBEDDING_HIGH_FILE = "embedding_high.mem",
    parameter string RECIPROCAL_FILE     = "pool_reciprocals.mem"
) (
    input logic clk,
    input logic reset,
    input logic clear,

    input logic valid_in,
    input logic [INDEX_WIDTH-1:0] index_in,
    input logic end_in,

    output logic done,
    output logic [$clog2(MAXIMUM_FEATURES + 1)-1:0] feature_count,

    output logic signed [9:0] pooled_data
        [0:DIMENSION-1]
);

    localparam integer SUM_WIDTH = 12;
    localparam integer POOLED_WIDTH = 10;
    localparam integer POOL_SHIFT = RECIPROCAL_SHIFT - POOL_GAIN;
    localparam integer LOW_WIDTH = 4 * (DIMENSION - 1);
    localparam integer COUNT_WIDTH = $clog2(MAXIMUM_FEATURES + 1);
    localparam integer DIMENSION_INDEX_WIDTH = $clog2(DIMENSION);
    localparam integer PRODUCT_WIDTH = SUM_WIDTH + 18;
    localparam integer BANK_NUMBER = 4;
    localparam integer BANK_ROWS = ROW_NUMBER / BANK_NUMBER;
    localparam integer BANK_INDEX_WIDTH = $clog2(BANK_NUMBER);
    localparam integer BANK_ROW_WIDTH = INDEX_WIDTH - BANK_INDEX_WIDTH;

    typedef enum logic [1:0] {
        ACCUMULATE,
        POOL,
        HOLD
    } state_t;

    state_t state_reg, state_next;

    (* rom_style = "block" *)
    logic [BANK_NUMBER*LOW_WIDTH-1:0] embedding_low_ROM [0:BANK_ROWS - 1];

    (* rom_style = "block" *)
    logic [3:0] embedding_high_ROM [0:ROW_NUMBER - 1];

    logic [31:0] reciprocal_ROM [0:MAXIMUM_FEATURES];

    initial begin
        $readmemh(EMBEDDING_LOW_FILE, embedding_low_ROM);
        $readmemh(EMBEDDING_HIGH_FILE, embedding_high_ROM);
        $readmemh(RECIPROCAL_FILE, reciprocal_ROM);
    end

    // Table row for the index that arrived last clock
    logic [BANK_NUMBER*LOW_WIDTH-1:0] row_low_word_reg;
    logic [BANK_INDEX_WIDTH-1:0] row_bank_reg;
    logic [LOW_WIDTH-1:0] row_low;
    logic [3:0] row_high_reg;
    logic [4*DIMENSION-1:0] row;

    logic row_valid_reg, row_valid_next;
    logic row_end_reg, row_end_next;

    logic signed [SUM_WIDTH-1:0] sum_reg [0:DIMENSION-1];
    logic signed [SUM_WIDTH-1:0] sum_next [0:DIMENSION-1];
    logic signed [POOLED_WIDTH-1:0] pooled_reg [0:DIMENSION-1];
    logic signed [POOLED_WIDTH-1:0] pooled_next [0:DIMENSION-1];

    logic [COUNT_WIDTH-1:0] feature_count_reg, feature_count_next;
    logic [DIMENSION_INDEX_WIDTH-1:0] dimension_index_reg, dimension_index_next;

    logic signed [17:0] reciprocal;
    logic signed [PRODUCT_WIDTH-1:0] pool_product;
    logic signed [PRODUCT_WIDTH-1:0] pool_rounded;
    logic signed [PRODUCT_WIDTH-1:0] pool_shifted;


    // Separate clocked block with no reset, so the table is inferred as BRAM
    always_ff @(posedge clk) begin
        row_low_word_reg <= embedding_low_ROM[index_in[BANK_ROW_WIDTH-1:0]];
        row_bank_reg <= index_in[INDEX_WIDTH-1 -: BANK_INDEX_WIDTH];
        row_high_reg <= embedding_high_ROM[index_in];
    end

    assign row_low = row_low_word_reg[(BANK_NUMBER - 1 - row_bank_reg) * LOW_WIDTH +: LOW_WIDTH];
    assign row = {row_high_reg, row_low};


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= ACCUMULATE;
            row_valid_reg <= 1'b0;
            row_end_reg <= 1'b0;
            feature_count_reg <= '0;
            dimension_index_reg <= '0;
            for (int i = 0; i < DIMENSION; i++) begin
                sum_reg[i] <= '0;
                pooled_reg[i] <= '0;
            end
        end else begin
            state_reg <= state_next;
            row_valid_reg <= row_valid_next;
            row_end_reg <= row_end_next;
            feature_count_reg <= feature_count_next;
            dimension_index_reg <= dimension_index_next;
            sum_reg <= sum_next;
            pooled_reg <= pooled_next;
        end
    end


    // Mean pool of one dimension per clock: Q16 reciprocal, round half up, arithmetic shift
    always_comb begin
        reciprocal = {1'b0, reciprocal_ROM[feature_count_reg][16:0]};
        pool_product = sum_reg[dimension_index_reg] * reciprocal;
        pool_rounded = pool_product + (PRODUCT_WIDTH'(1) <<< (POOL_SHIFT - 1));
        pool_shifted = pool_rounded >>> POOL_SHIFT;
    end


    always_comb begin
        state_next = state_reg;
        row_valid_next = valid_in;
        row_end_next = end_in;
        feature_count_next = feature_count_reg;
        dimension_index_next = dimension_index_reg;
        sum_next = sum_reg;
        pooled_next = pooled_reg;

        case (state_reg)
            ACCUMULATE: begin
                if (row_valid_reg) begin
                    for (int i = 0; i < DIMENSION; i++) begin
                        // sign-extend the INT4 code
                        sum_next[i] = sum_reg[i] + {{(SUM_WIDTH-4){row[4*i+3]}}, row[4*i +: 4]};
                    end
                    feature_count_next = feature_count_reg + 1'b1;
                end

                if (row_end_reg) begin
                    dimension_index_next = '0;
                    state_next = POOL;
                end
            end

            POOL: begin
                // |pooled| fits 10 bits by the bound above, so the truncation is exact
                pooled_next[dimension_index_reg] = pool_shifted[POOLED_WIDTH-1:0];
                dimension_index_next = dimension_index_reg + 1'b1;

                if (dimension_index_reg == DIMENSION - 1) begin
                    state_next = HOLD;
                end
            end

            HOLD: begin
                // pooled_data stays valid until the next message clears the bag
            end

            default: begin
                state_next = ACCUMULATE;
            end
        endcase

        if (clear) begin
            state_next = ACCUMULATE;
            feature_count_next = '0;
            for (int i = 0; i < DIMENSION; i++) begin
                sum_next[i] = '0;
            end
        end
    end

    assign done = (state_reg == HOLD);
    assign feature_count = feature_count_reg;
    assign pooled_data = pooled_reg;

endmodule
