// Raw message bytes in, embedding-table row indices out.
//
// This is the RTL side of hash_features() in src/sysone/hashing.py. The index
// stream has to match the Python one element for element, including the order,
// because the model keeps only the first MAXIMUM_FEATURES features. When a message
// produces more than that, the order decides which ones are dropped (30 of the
// 22,500 CLINC150 utterances do).
//
// The order, exactly as in Python:
//   1. word unigrams
//   2. word bigrams
//   3. word trigrams
//   4. for each word, for n = 3, 4, 5, every character n-gram of "<word>" in start order
// A message with no words at all produces a single index 0.
//
// That order needs two passes over the message, so the word bytes are stored:
//   RECEIVE     one byte per clock. Fold to lower case, find word boundaries and hash
//               each word on the fly. Only word bytes are stored, packed, with the
//               start and length of every word.
//   UNIGRAM,
//   BIGRAM,
//   TRIGRAM     one feature per clock from the stored word hashes.
//   CHARACTER   walk each word's bytes three times (n = 3, 4, 5). FNV is not a rolling
//               hash, but n staggered lanes are: lane (position mod n) restarts at each
//               byte, so the lane that started n - 1 bytes ago completes a window every
//               clock. One index per clock, no extra memory reads.
//
// More than MESSAGE_BYTES word bytes sets overflow_out, because the character pass
// would then be wrong. More than MAXIMUM_WORDS words is not an error: with more than
// 256 words the first 256 features are all unigrams, so later words are never used.
module feature_generator #(
    parameter integer MESSAGE_BYTES    = 2048,
    parameter integer MAXIMUM_WORDS    = 256,
    parameter integer MAXIMUM_FEATURES = 256,
    parameter integer INDEX_WIDTH      = 14
) (
    input  logic clk,
    input  logic reset,

    // message bytes: a data beat carries one byte, a message_end beat ends the message
    input  logic [7:0] data_in,
    input  logic valid_in,
    input  logic message_end_in,
    output logic ready_out,

    // one index per clock while emitting, then one end beat. There is no backpressure.
    output logic feature_valid_out,
    output logic [INDEX_WIDTH-1:0] feature_index_out,
    output logic feature_end_out,

    // the rest of the core is done with this message
    input  logic release_in,
    output logic overflow_out
);

    localparam integer BYTE_ADDRESS_WIDTH  = $clog2(MESSAGE_BYTES + 1);
    localparam integer WORD_COUNT_WIDTH    = $clog2(MAXIMUM_WORDS + 1);
    localparam integer FEATURE_COUNT_WIDTH = $clog2(MAXIMUM_FEATURES + 1);
    localparam integer MESSAGE_INDEX_WIDTH = $clog2(MESSAGE_BYTES);
    localparam integer WORD_INDEX_WIDTH    = $clog2(MAXIMUM_WORDS);

    localparam logic [31:0] FNV_OFFSET = 32'h811C9DC5;
    localparam logic [7:0] WORD_START_MARKER = 8'h3C;   // '<'
    localparam logic [7:0] WORD_END_MARKER   = 8'h3E;   // '>'

    // Feature type codes, shared with feature_hash_pipeline
    localparam logic [1:0] UNIGRAM   = 2'd0;
    localparam logic [1:0] BIGRAM    = 2'd1;
    localparam logic [1:0] TRIGRAM   = 2'd2;
    localparam logic [1:0] CHARACTER = 2'd3;

    typedef enum logic [2:0] {
        RECEIVE,
        UNIGRAM_FEATURES,
        BIGRAM_FEATURES,
        TRIGRAM_FEATURES,
        CHARACTER_FEATURES,
        FINISH,
        HOLD
    } state_t;

    state_t state_reg, state_next;

    // value * 0x01000193 mod 2^32, written as shifts and adds
    function automatic logic [31:0] fnv_multiply(
        input logic [31:0] value
    );
        begin
            fnv_multiply = (value << 24) + (value << 8) + (value << 7)
                + (value << 4) + (value << 1) + value;
        end
    endfunction

    // One FNV-1a step: xor the byte in, then multiply
    function automatic logic [31:0] fnv_step(
        input logic [31:0] hash,
        input logic [7:0] data
    );
        begin
            fnv_step = fnv_multiply(hash ^ {24'd0, data});
        end
    endfunction


    // ------------------------------------------------------------------ storage
    // Small enough for LUTRAM, and read combinationally like parameterized_reg_file.
    logic [7:0] message_memory [0:MESSAGE_BYTES - 1];
    logic [31:0] word_hash_memory [0:MAXIMUM_WORDS - 1];
    logic [BYTE_ADDRESS_WIDTH-1:0] word_start_memory [0:MAXIMUM_WORDS - 1];
    logic [BYTE_ADDRESS_WIDTH-1:0] word_length_memory [0:MAXIMUM_WORDS - 1];

    logic message_write_enable;
    logic [7:0] message_write_data;
    logic word_write_enable;

    // ------------------------------------------------------------------ receive state
    logic [BYTE_ADDRESS_WIDTH-1:0] write_address_reg, write_address_next;
    logic [WORD_COUNT_WIDTH-1:0] word_count_reg, word_count_next;
    logic in_word_reg, in_word_next;
    logic [31:0] current_hash_reg, current_hash_next;
    logic [BYTE_ADDRESS_WIDTH-1:0] current_start_reg, current_start_next;
    logic [BYTE_ADDRESS_WIDTH-1:0] current_length_reg, current_length_next;
    logic overflow_reg, overflow_next;

    // ------------------------------------------------------------------ emit state
    logic [WORD_COUNT_WIDTH-1:0] word_index_reg, word_index_next;
    logic [FEATURE_COUNT_WIDTH-1:0] feature_count_reg, feature_count_next;
    logic [2:0] ngram_size_reg, ngram_size_next;
    logic [BYTE_ADDRESS_WIDTH:0] position_reg, position_next;           // 0 .. length + 1 in "<word>"
    logic [2:0] position_lane_reg, position_lane_next;                 // position mod n
    logic [2:0] finishing_lane_reg, finishing_lane_next;               // (position + 1) mod n
    logic [31:0] lane_hash_reg [0:4];
    logic [31:0] lane_hash_next [0:4];

    // ------------------------------------------------------------------ issue port
    logic issue_valid_reg, issue_valid_next;
    logic issue_end_reg, issue_end_next;
    logic [1:0] issue_type_reg, issue_type_next;
    logic [31:0] issue_first_reg, issue_first_next;
    logic [31:0] issue_second_reg, issue_second_next;
    logic [31:0] issue_third_reg, issue_third_next;
    logic [2:0] issue_ngram_size_reg, issue_ngram_size_next;

    // ------------------------------------------------------------------ combinational helpers
    logic [7:0] folded_byte;
    logic word_byte;
    logic close_word;

    logic [31:0] word_hash_0, word_hash_1, word_hash_2;
    logic [BYTE_ADDRESS_WIDTH-1:0] word_start, word_length;
    logic [BYTE_ADDRESS_WIDTH-1:0] character_address;
    logic [7:0] character_byte;
    logic [31:0] character_lane_hash [0:4];
    logic [31:0] completed_window_hash;


    // Case folding and the word-byte test are both plain comparators.
    // Anything that is not [a-z0-9], including every byte >= 0x80, is a separator.
    always_comb begin
        if (data_in >= 8'h41 && data_in <= 8'h5A) begin
            folded_byte = data_in + 8'd32;
        end else begin
            folded_byte = data_in;
        end

        word_byte = (folded_byte >= 8'h61 && folded_byte <= 8'h7A)
            || (folded_byte >= 8'h30 && folded_byte <= 8'h39);
    end


    // Memory writes are kept in their own block, without reset, so they stay LUTRAM
    always_ff @(posedge clk) begin
        if (message_write_enable) begin
            message_memory[write_address_reg[MESSAGE_INDEX_WIDTH-1:0]] <= message_write_data;
        end

        if (word_write_enable) begin
            word_hash_memory[word_count_reg[WORD_INDEX_WIDTH-1:0]] <= current_hash_reg;
            word_start_memory[word_count_reg[WORD_INDEX_WIDTH-1:0]] <= current_start_reg;
            word_length_memory[word_count_reg[WORD_INDEX_WIDTH-1:0]] <= current_length_reg;
        end
    end


    // Memory reads for the emit states
    always_comb begin
        word_hash_0 = word_hash_memory[word_index_reg[WORD_INDEX_WIDTH-1:0]];
        word_hash_1 = word_hash_memory[word_index_reg[WORD_INDEX_WIDTH-1:0] + 1'b1];
        word_hash_2 = word_hash_memory[word_index_reg[WORD_INDEX_WIDTH-1:0] + 2'd2];
        word_start = word_start_memory[word_index_reg[WORD_INDEX_WIDTH-1:0]];
        word_length = word_length_memory[word_index_reg[WORD_INDEX_WIDTH-1:0]];

        // Position 0 is '<', positions 1 .. length are the word, length + 1 is '>'
        character_address = word_start + position_reg[BYTE_ADDRESS_WIDTH-1:0] - 1'b1;

        if (position_reg == 0) begin
            character_byte = WORD_START_MARKER;
        end else if (position_reg == {1'b0, word_length} + 1'b1) begin
            character_byte = WORD_END_MARKER;
        end else begin
            character_byte = message_memory[character_address[MESSAGE_INDEX_WIDTH-1:0]];
        end

        // Every lane absorbs the byte; the lane for this position starts a new window
        for (int lane = 0; lane < 5; lane++) begin
            if (lane == position_lane_reg) begin
                character_lane_hash[lane] = fnv_step(FNV_OFFSET, character_byte);
            end else begin
                character_lane_hash[lane] = fnv_step(lane_hash_reg[lane], character_byte);
            end
        end

        // The lane that started n - 1 bytes ago has just completed its window
        completed_window_hash = character_lane_hash[finishing_lane_reg];
    end


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= RECEIVE;
            write_address_reg <= '0;
            word_count_reg <= '0;
            in_word_reg <= 1'b0;
            current_hash_reg <= '0;
            current_start_reg <= '0;
            current_length_reg <= '0;
            overflow_reg <= 1'b0;
            word_index_reg <= '0;
            feature_count_reg <= '0;
            ngram_size_reg <= 3'd3;
            position_reg <= '0;
            position_lane_reg <= '0;
            finishing_lane_reg <= 3'd1;
            for (int lane = 0; lane < 5; lane++) begin
                lane_hash_reg[lane] <= '0;
            end
            issue_valid_reg <= 1'b0;
            issue_end_reg <= 1'b0;
            issue_type_reg <= UNIGRAM;
            issue_first_reg <= '0;
            issue_second_reg <= '0;
            issue_third_reg <= '0;
            issue_ngram_size_reg <= '0;
        end else begin
            state_reg <= state_next;
            write_address_reg <= write_address_next;
            word_count_reg <= word_count_next;
            in_word_reg <= in_word_next;
            current_hash_reg <= current_hash_next;
            current_start_reg <= current_start_next;
            current_length_reg <= current_length_next;
            overflow_reg <= overflow_next;
            word_index_reg <= word_index_next;
            feature_count_reg <= feature_count_next;
            ngram_size_reg <= ngram_size_next;
            position_reg <= position_next;
            position_lane_reg <= position_lane_next;
            finishing_lane_reg <= finishing_lane_next;
            lane_hash_reg <= lane_hash_next;
            issue_valid_reg <= issue_valid_next;
            issue_end_reg <= issue_end_next;
            issue_type_reg <= issue_type_next;
            issue_first_reg <= issue_first_next;
            issue_second_reg <= issue_second_next;
            issue_third_reg <= issue_third_next;
            issue_ngram_size_reg <= issue_ngram_size_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        write_address_next = write_address_reg;
        word_count_next = word_count_reg;
        in_word_next = in_word_reg;
        current_hash_next = current_hash_reg;
        current_start_next = current_start_reg;
        current_length_next = current_length_reg;
        overflow_next = overflow_reg;
        word_index_next = word_index_reg;
        feature_count_next = feature_count_reg;
        ngram_size_next = ngram_size_reg;
        position_next = position_reg;
        position_lane_next = position_lane_reg;
        finishing_lane_next = finishing_lane_reg;
        lane_hash_next = lane_hash_reg;

        issue_valid_next = 1'b0;
        issue_end_next = 1'b0;
        issue_type_next = issue_type_reg;
        issue_first_next = issue_first_reg;
        issue_second_next = issue_second_reg;
        issue_third_next = issue_third_reg;
        issue_ngram_size_next = issue_ngram_size_reg;

        message_write_enable = 1'b0;
        message_write_data = folded_byte;
        word_write_enable = 1'b0;
        close_word = 1'b0;

        case (state_reg)
            RECEIVE: begin
                if (valid_in) begin
                    if (message_end_in) begin
                        // A word still open at the end of the message is closed first
                        close_word = in_word_reg;
                        state_next = UNIGRAM_FEATURES;
                        word_index_next = '0;
                        feature_count_next = '0;
                    end else if (word_byte) begin
                        if (!in_word_reg) begin
                            in_word_next = 1'b1;
                            current_hash_next = fnv_step(FNV_OFFSET, folded_byte);
                            current_start_next = write_address_reg;
                            current_length_next = 1;
                        end else begin
                            current_hash_next = fnv_step(current_hash_reg, folded_byte);
                            current_length_next = current_length_reg + 1'b1;
                        end

                        if (write_address_reg < MESSAGE_BYTES) begin
                            message_write_enable = 1'b1;
                            write_address_next = write_address_reg + 1'b1;
                        end else begin
                            overflow_next = 1'b1;
                        end
                    end else begin
                        // Any separator ends the current word
                        close_word = in_word_reg;
                    end
                end
            end

            UNIGRAM_FEATURES: begin
                if (feature_count_reg == MAXIMUM_FEATURES) begin
                    state_next = FINISH;
                end else if (word_count_reg == 0) begin
                    // No words: a single index 0, so the pooling never divides by zero
                    issue_valid_next = 1'b1;
                    issue_type_next = UNIGRAM;
                    issue_first_next = '0;
                    feature_count_next = feature_count_reg + 1'b1;
                    state_next = FINISH;
                end else if (word_index_reg == word_count_reg) begin
                    word_index_next = '0;
                    state_next = BIGRAM_FEATURES;
                end else begin
                    issue_valid_next = 1'b1;
                    issue_type_next = UNIGRAM;
                    issue_first_next = word_hash_0;
                    feature_count_next = feature_count_reg + 1'b1;
                    word_index_next = word_index_reg + 1'b1;
                end
            end

            BIGRAM_FEATURES: begin
                if (feature_count_reg == MAXIMUM_FEATURES) begin
                    state_next = FINISH;
                end else if (word_count_reg < 2 || word_index_reg == word_count_reg - 1'b1) begin
                    word_index_next = '0;
                    state_next = TRIGRAM_FEATURES;
                end else begin
                    issue_valid_next = 1'b1;
                    issue_type_next = BIGRAM;
                    issue_first_next = word_hash_0;
                    issue_second_next = word_hash_1;
                    feature_count_next = feature_count_reg + 1'b1;
                    word_index_next = word_index_reg + 1'b1;
                end
            end

            TRIGRAM_FEATURES: begin
                if (feature_count_reg == MAXIMUM_FEATURES) begin
                    state_next = FINISH;
                end else if (word_count_reg < 3 || word_index_reg == word_count_reg - 2'd2) begin
                    word_index_next = '0;
                    ngram_size_next = 3'd3;
                    position_next = '0;
                    position_lane_next = 3'd0;
                    finishing_lane_next = 3'd1;
                    state_next = CHARACTER_FEATURES;
                end else begin
                    issue_valid_next = 1'b1;
                    issue_type_next = TRIGRAM;
                    issue_first_next = word_hash_0;
                    issue_second_next = word_hash_1;
                    issue_third_next = word_hash_2;
                    feature_count_next = feature_count_reg + 1'b1;
                    word_index_next = word_index_reg + 1'b1;
                end
            end

            CHARACTER_FEATURES: begin
                if (feature_count_reg == MAXIMUM_FEATURES || word_index_reg == word_count_reg) begin
                    state_next = FINISH;
                end else begin
                    lane_hash_next = character_lane_hash;

                    // A window is complete once n bytes of "<word>" have been seen
                    if (position_reg >= ngram_size_reg - 1'b1) begin
                        issue_valid_next = 1'b1;
                        issue_type_next = CHARACTER;
                        issue_first_next = completed_window_hash;
                        issue_ngram_size_next = ngram_size_reg;
                        feature_count_next = feature_count_reg + 1'b1;
                    end

                    if (position_reg == {1'b0, word_length} + 1'b1) begin
                        // End of "<word>": next n, or the next word after n = 5
                        position_next = '0;
                        position_lane_next = 3'd0;
                        finishing_lane_next = 3'd1;

                        if (ngram_size_reg == 3'd5) begin
                            ngram_size_next = 3'd3;
                            word_index_next = word_index_reg + 1'b1;
                        end else begin
                            ngram_size_next = ngram_size_reg + 1'b1;
                        end
                    end else begin
                        position_next = position_reg + 1'b1;

                        if (position_lane_reg == ngram_size_reg - 1'b1) begin
                            position_lane_next = 3'd0;
                        end else begin
                            position_lane_next = position_lane_reg + 1'b1;
                        end

                        if (finishing_lane_reg == ngram_size_reg - 1'b1) begin
                            finishing_lane_next = 3'd0;
                        end else begin
                            finishing_lane_next = finishing_lane_reg + 1'b1;
                        end
                    end
                end
            end

            FINISH: begin
                // The end beat follows the last feature through the hash pipeline
                issue_end_next = 1'b1;
                state_next = HOLD;
            end

            HOLD: begin
                if (release_in) begin
                    state_next = RECEIVE;
                    write_address_next = '0;
                    word_count_next = '0;
                    in_word_next = 1'b0;
                    overflow_next = 1'b0;
                end
            end

            default: begin
                state_next = RECEIVE;
            end
        endcase

        // Words past MAXIMUM_WORDS are not stored; they can never be reached
        if (close_word) begin
            in_word_next = 1'b0;

            if (word_count_reg < MAXIMUM_WORDS) begin
                word_write_enable = 1'b1;
                word_count_next = word_count_reg + 1'b1;
            end
        end
    end


    feature_hash_pipeline #(
        .INDEX_WIDTH(INDEX_WIDTH)
    ) feature_hash_pipeline_inst (
        .clk            (clk),
        .reset          (reset),
        .valid_in       (issue_valid_reg),
        .end_in         (issue_end_reg),
        .feature_type_in(issue_type_reg),
        .first_hash_in  (issue_first_reg),
        .second_hash_in (issue_second_reg),
        .third_hash_in  (issue_third_reg),
        .ngram_size_in  (issue_ngram_size_reg),
        .valid_out      (feature_valid_out),
        .end_out        (feature_end_out),
        .index_out      (feature_index_out)
    );

    assign ready_out = (state_reg == RECEIVE);
    assign overflow_out = overflow_reg;

endmodule
