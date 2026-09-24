// Salted FNV-1a mixes for every feature type, one index per clock, in order.
//
// This is the RTL side of _mix() in src/sysone/hashing.py:
//     mix(a, b, salt) = fnv_multiply(fnv_multiply(a ^ salt) ^ b)
// and the feature types use it like this:
//     unigram   : a                                   (the word hash itself)
//     bigram    : mix(a, b, BIGRAM_SALT)
//     trigram   : mix(mix(a, b, TRIGRAM_SALT), c, TRIGRAM_SALT)
//     character : mix(a, n, CHARACTER_SALT)           (a = hash of the window, n = its size)
//
// A trigram needs four multiplies, so the pipeline is four stages deep with one
// multiply per stage. The other types pass through the stages they do not need,
// which keeps every feature the same latency and the output in issue order.
module feature_hash_pipeline #(
    parameter integer INDEX_WIDTH = 14
) (
    input  logic clk,
    input  logic reset,

    input  logic valid_in,
    input  logic end_in,
    input  logic [1:0] feature_type_in,
    input  logic [31:0] first_hash_in,
    input  logic [31:0] second_hash_in,
    input  logic [31:0] third_hash_in,
    input  logic [2:0] ngram_size_in,

    output logic valid_out,
    output logic end_out,
    output logic [INDEX_WIDTH-1:0] index_out
);

    // Feature type codes, shared with feature_generator
    localparam logic [1:0] UNIGRAM   = 2'd0;
    localparam logic [1:0] BIGRAM    = 2'd1;
    localparam logic [1:0] TRIGRAM   = 2'd2;
    localparam logic [1:0] CHARACTER = 2'd3;

    localparam logic [31:0] BIGRAM_SALT    = 32'h9E3779B9;
    localparam logic [31:0] TRIGRAM_SALT   = 32'h85EBCA6B;
    localparam logic [31:0] CHARACTER_SALT = 32'hC2B2AE35;

    // value * 0x01000193 mod 2^32, written as shifts and adds.
    // 0x01000193 = 2^24 + 2^8 + 2^7 + 2^4 + 2^1 + 1
    function automatic logic [31:0] fnv_multiply(
        input logic [31:0] value
    );
        begin
            fnv_multiply = (value << 24) + (value << 8) + (value << 7)
                + (value << 4) + (value << 1) + value;
        end
    endfunction

    logic [3:0] valid_reg, valid_next;
    logic [3:0] end_reg, end_next;

    // stage 1
    logic [1:0] type_1_reg, type_1_next;
    logic [31:0] hash_1_reg, hash_1_next;
    logic [31:0] second_1_reg, second_1_next;
    logic [31:0] third_1_reg, third_1_next;
    logic [2:0] ngram_size_1_reg, ngram_size_1_next;

    // stage 2
    logic [1:0] type_2_reg, type_2_next;
    logic [31:0] hash_2_reg, hash_2_next;
    logic [31:0] third_2_reg, third_2_next;

    // stage 3
    logic [1:0] type_3_reg, type_3_next;
    logic [31:0] hash_3_reg, hash_3_next;
    logic [31:0] third_3_reg, third_3_next;

    // stage 4
    logic [31:0] hash_4_reg, hash_4_next;

    logic [31:0] salt;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            valid_reg <= '0;
            end_reg <= '0;
            type_1_reg <= UNIGRAM;
            hash_1_reg <= '0;
            second_1_reg <= '0;
            third_1_reg <= '0;
            ngram_size_1_reg <= '0;
            type_2_reg <= UNIGRAM;
            hash_2_reg <= '0;
            third_2_reg <= '0;
            type_3_reg <= UNIGRAM;
            hash_3_reg <= '0;
            third_3_reg <= '0;
            hash_4_reg <= '0;
        end else begin
            valid_reg <= valid_next;
            end_reg <= end_next;
            type_1_reg <= type_1_next;
            hash_1_reg <= hash_1_next;
            second_1_reg <= second_1_next;
            third_1_reg <= third_1_next;
            ngram_size_1_reg <= ngram_size_1_next;
            type_2_reg <= type_2_next;
            hash_2_reg <= hash_2_next;
            third_2_reg <= third_2_next;
            type_3_reg <= type_3_next;
            hash_3_reg <= hash_3_next;
            third_3_reg <= third_3_next;
            hash_4_reg <= hash_4_next;
        end
    end

    always_comb begin
        valid_next = {valid_reg[2:0], valid_in};
        end_next = {end_reg[2:0], end_in};

        case (feature_type_in)
            BIGRAM:  salt = BIGRAM_SALT;
            TRIGRAM: salt = TRIGRAM_SALT;
            default: salt = CHARACTER_SALT;
        endcase

        // Stage 1: first half of the first mix
        type_1_next = feature_type_in;
        second_1_next = second_hash_in;
        third_1_next = third_hash_in;
        ngram_size_1_next = ngram_size_in;

        if (feature_type_in == UNIGRAM) begin
            hash_1_next = first_hash_in;
        end else begin
            hash_1_next = fnv_multiply(first_hash_in ^ salt);
        end

        // Stage 2: second half of the first mix. A character n-gram mixes in its size.
        type_2_next = type_1_reg;
        third_2_next = third_1_reg;

        if (type_1_reg == UNIGRAM) begin
            hash_2_next = hash_1_reg;
        end else if (type_1_reg == CHARACTER) begin
            hash_2_next = fnv_multiply(hash_1_reg ^ {29'd0, ngram_size_1_reg});
        end else begin
            hash_2_next = fnv_multiply(hash_1_reg ^ second_1_reg);
        end

        // Stages 3 and 4: the second mix, trigrams only
        type_3_next = type_2_reg;
        third_3_next = third_2_reg;

        if (type_2_reg == TRIGRAM) begin
            hash_3_next = fnv_multiply(hash_2_reg ^ TRIGRAM_SALT);
        end else begin
            hash_3_next = hash_2_reg;
        end

        if (type_3_reg == TRIGRAM) begin
            hash_4_next = fnv_multiply(hash_3_reg ^ third_3_reg);
        end else begin
            hash_4_next = hash_3_reg;
        end
    end

    // The table has a power-of-two number of rows, so the index is just the low bits
    assign valid_out = valid_reg[3];
    assign end_out = end_reg[3];
    assign index_out = hash_4_reg[INDEX_WIDTH-1:0];

endmodule
