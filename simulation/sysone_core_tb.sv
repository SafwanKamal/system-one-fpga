`timescale 1ns / 1ps

/*
Bit-exact check of sysone_core against the NumPy golden model.

The vectors come from `uv run python scripts/rtl_pack.py --vectors`:
    vectors/bytes.hex    one 9-bit word per line; 0x100 ends a message
    vectors/idx.hex      per message: the feature count, then that many table indices
    vectors/logits.hex   CLASS_NUMBER x int16 per message, in class order
    vectors/argmax.hex   one class per message

Every index, every logit and every decision is compared. The run passes only if
all of them match. Every logit the RTL emits is also written to rtl_logits.hex so
scripts/rtl_metrics.py can score the RTL's own output.
*/
module sysone_core_tb;

    `include "model_parameters.svh"

    parameter integer MESSAGE_NUMBER = 5515;
    parameter string MEMORY_DIRECTORY = "../memory";
    parameter string VECTOR_DIRECTORY = "vectors";

    localparam integer MAXIMUM_BYTE_WORDS  = 400_000;
    localparam integer MAXIMUM_INDEX_WORDS = 800_000;
    localparam integer MAXIMUM_LOGITS      = 1_000_000;
    localparam integer MAXIMUM_MESSAGES    = 8_000;
    localparam integer MAXIMUM_CYCLES      = 10_000;
    localparam integer MAXIMUM_REPORTS     = 10;

    localparam integer INDEX_WIDTH = $clog2(MODEL_ROW_NUMBER);
    localparam integer COUNT_WIDTH = $clog2(MODEL_MAXIMUM_FEATURES + 1);

    logic clk;
    logic reset;

    logic [7:0] data_in;
    logic valid_in;
    logic message_end_in;
    logic ready_out;

    logic logit_valid_out;
    logic [7:0] logit_class_out;
    logic signed [15:0] logit_out;

    logic decision_valid_out;
    logic [7:0] decision_class_out;
    logic signed [15:0] top_logit_out;
    logic signed [15:0] second_logit_out;
    logic [COUNT_WIDTH-1:0] feature_count_out;
    logic overflow_out;

    logic feature_valid_out;
    logic [INDEX_WIDTH-1:0] feature_index_out;

    logic [8:0] byte_ROM [0:MAXIMUM_BYTE_WORDS - 1];
    logic [15:0] index_ROM [0:MAXIMUM_INDEX_WORDS - 1];
    logic [15:0] logit_ROM [0:MAXIMUM_LOGITS - 1];
    logic [7:0] argmax_ROM [0:MAXIMUM_MESSAGES - 1];

    // Where the checkers are in the vector files
    integer message_index;
    integer byte_pointer;
    integer index_base;
    integer feature_count;
    integer features_seen;
    integer logits_seen;

    integer index_errors;
    integer logit_errors;
    integer decision_errors;
    integer count_errors;

    integer cycle_number = 0;
    integer message_end_cycle;
    integer latency_sum;
    integer latency_minimum;
    integer latency_maximum;

    integer logit_file;


    /*
     * 100 MHz clock:
     * period = 10 ns
     */
    always begin
        #5 clk = ~clk;
    end


    sysone_core #(
        .ROW_NUMBER      (MODEL_ROW_NUMBER),
        .DIMENSION       (MODEL_DIMENSION),
        .HIDDEN          (MODEL_HIDDEN),
        .CLASS_NUMBER    (MODEL_CLASS_NUMBER),
        .MAXIMUM_FEATURES(MODEL_MAXIMUM_FEATURES),
        .POOL_GAIN       (MODEL_POOL_GAIN),

        .EMBEDDING_LOW_FILE    ({MEMORY_DIRECTORY, "/embedding_low.mem"}),
        .EMBEDDING_HIGH_FILE   ({MEMORY_DIRECTORY, "/embedding_high.mem"}),
        .RECIPROCAL_FILE       ({MEMORY_DIRECTORY, "/pool_reciprocals.mem"}),
        .HIDDEN_WEIGHT_FILE    ({MEMORY_DIRECTORY, "/dense_hidden_weights.mem"}),
        .HIDDEN_BIAS_FILE      ({MEMORY_DIRECTORY, "/dense_hidden_biases.mem"}),
        .OUTPUT_WEIGHT_FILE    ({MEMORY_DIRECTORY, "/dense_output_weights.mem"}),
        .OUTPUT_BIAS_FILE      ({MEMORY_DIRECTORY, "/dense_output_biases.mem"}),
        .HIDDEN_MULTIPLIER_FILE({MEMORY_DIRECTORY, "/requant_hidden_multipliers.mem"}),
        .HIDDEN_REQUANT_FILE   ({MEMORY_DIRECTORY, "/requant_hidden_biases.mem"}),
        .OUTPUT_MULTIPLIER_FILE({MEMORY_DIRECTORY, "/requant_output_multipliers.mem"}),
        .OUTPUT_REQUANT_FILE   ({MEMORY_DIRECTORY, "/requant_output_biases.mem"})
    ) DUT (
        .clk               (clk),
        .reset             (reset),
        .data_in           (data_in),
        .valid_in          (valid_in),
        .message_end_in    (message_end_in),
        .ready_out         (ready_out),
        .logit_valid_out   (logit_valid_out),
        .logit_class_out   (logit_class_out),
        .logit_out         (logit_out),
        .decision_valid_out(decision_valid_out),
        .decision_class_out(decision_class_out),
        .top_logit_out     (top_logit_out),
        .second_logit_out  (second_logit_out),
        .feature_count_out (feature_count_out),
        .overflow_out      (overflow_out),
        .feature_valid_out (feature_valid_out),
        .feature_index_out (feature_index_out)
    );


    always @(posedge clk) begin
        cycle_number <= cycle_number + 1;
    end


    /*
     * Index and logit checkers.
     *
     * Both streams are registered one-clock pulses, so they are stable
     * at the falling edge.
     */
    always @(negedge clk) begin
        if (!reset && feature_valid_out) begin
            if (
                features_seen >= feature_count
                || feature_index_out !== index_ROM[index_base + 1 + features_seen][INDEX_WIDTH-1:0]
            ) begin
                if (index_errors < MAXIMUM_REPORTS) begin
                    $error(
                        "Message %0d feature %0d: expected index %0d, received %0d (count %0d)",
                        message_index,
                        features_seen,
                        index_ROM[index_base + 1 + features_seen],
                        feature_index_out,
                        feature_count
                    );
                end

                index_errors++;
            end

            features_seen++;
        end

        if (!reset && logit_valid_out) begin
            if (logit_out !== $signed(logit_ROM[message_index * MODEL_CLASS_NUMBER + logit_class_out])) begin
                if (logit_errors < MAXIMUM_REPORTS) begin
                    $error(
                        "Message %0d class %0d: expected logit %0d, received %0d",
                        message_index,
                        logit_class_out,
                        $signed(logit_ROM[message_index * MODEL_CLASS_NUMBER + logit_class_out]),
                        logit_out
                    );
                end

                logit_errors++;
            end

            logits_seen++;
            $fwrite(logit_file, "%04h\n", logit_out);
        end
    end


    task automatic run_message;

        integer wait_cycles;
        integer latency;

        begin
            /*
             * Send the bytes, then the message_end beat.
             *
             * ready_out only changes on rising edges, so its value at the
             * falling edge is the value the next rising edge will use.
             */
            while (1) begin
                @(negedge clk);
                valid_in = 1'b1;
                data_in = byte_ROM[byte_pointer][7:0];
                message_end_in = byte_ROM[byte_pointer][8];

                while (!ready_out) begin
                    @(negedge clk);
                end

                byte_pointer++;

                if (message_end_in) begin
                    message_end_cycle = cycle_number;
                    break;
                end
            end

            @(negedge clk);
            valid_in = 1'b0;
            message_end_in = 1'b0;


            /*
             * Wait for the decision with a timeout.
             */
            wait_cycles = 0;

            while (!decision_valid_out && wait_cycles < MAXIMUM_CYCLES) begin
                @(negedge clk);
                wait_cycles++;
            end

            if (!decision_valid_out) begin
                $fatal(
                    1,
                    "Message %0d: no decision after %0d cycles",
                    message_index,
                    MAXIMUM_CYCLES
                );
            end

            latency = cycle_number - message_end_cycle;
            latency_sum += latency;

            if (latency < latency_minimum) begin
                latency_minimum = latency;
            end

            if (latency > latency_maximum) begin
                latency_maximum = latency;
            end


            /*
             * Case inequality also detects X and Z.
             */
            if (decision_class_out !== argmax_ROM[message_index]) begin
                if (decision_errors < MAXIMUM_REPORTS) begin
                    $error(
                        "Message %0d: expected class %0d, received %0d",
                        message_index,
                        argmax_ROM[message_index],
                        decision_class_out
                    );
                end

                decision_errors++;
            end

            if (
                features_seen != feature_count
                || feature_count_out != feature_count
                || logits_seen != MODEL_CLASS_NUMBER
            ) begin
                if (count_errors < MAXIMUM_REPORTS) begin
                    $error(
                        "Message %0d: %0d features emitted, %0d counted, %0d expected, %0d logits",
                        message_index,
                        features_seen,
                        feature_count_out,
                        feature_count,
                        logits_seen
                    );
                end

                count_errors++;
            end

            if (overflow_out) begin
                $display("Message %0d: message buffer overflow flagged", message_index);
            end


            /*
             * Move the checkers to the next message.
             */
            message_index++;
            index_base = index_base + 1 + feature_count;
            feature_count = index_ROM[index_base];
            features_seen = 0;
            logits_seen = 0;

            if (message_index % 500 == 0) begin
                $display("Checked %0d/%0d messages", message_index, MESSAGE_NUMBER);
            end
        end

    endtask


    initial begin
        clk            = 1'b0;
        reset          = 1'b1;
        data_in        = 8'h00;
        valid_in       = 1'b0;
        message_end_in = 1'b0;

        message_index = 0;
        byte_pointer = 0;
        index_base = 0;
        features_seen = 0;
        logits_seen = 0;
        index_errors = 0;
        logit_errors = 0;
        decision_errors = 0;
        count_errors = 0;
        latency_sum = 0;
        latency_minimum = 1 << 30;
        latency_maximum = 0;

        $readmemh({VECTOR_DIRECTORY, "/bytes.hex"}, byte_ROM);
        $readmemh({VECTOR_DIRECTORY, "/idx.hex"}, index_ROM);
        $readmemh({VECTOR_DIRECTORY, "/logits.hex"}, logit_ROM);
        $readmemh({VECTOR_DIRECTORY, "/argmax.hex"}, argmax_ROM);
        feature_count = index_ROM[0];

        logit_file = $fopen("rtl_logits.hex", "w");


        /*
         * A missing .mem file can load silently, and it turns a bit-exact run into
         * mismatches that look like an arithmetic bug. Verilator is two-state, so
         * an unloaded memory reads as zeros rather than X; check for non-zero
         * words instead. dense_engine zero-fills its ROM first, so the same check
         * works there.
         */
        if (
            DUT.embedding_bag_inst.embedding_low_ROM[0] == 0
            || DUT.embedding_bag_inst.reciprocal_ROM[1] == 0
            || DUT.classifier_head_inst.hidden_dense_engine_inst.distributed_weight_ROM.weight_ROM[0] == 0
            || DUT.classifier_head_inst.output_dense_engine_inst.block_weight_ROM.weight_ROM[0] == 0
        ) begin
            $fatal(1, "Model memories not loaded: check MEMORY_DIRECTORY and run from simulation/");
        end

        if (byte_ROM[0] == 0 || index_ROM[0] == 0) begin
            $fatal(1, "Vectors not loaded: run `make vectors` first");
        end


        /*
         * Hold reset for five clock cycles.
         */
        repeat (5) begin
            @(negedge clk);
        end

        reset = 1'b0;

        repeat (2) begin
            @(negedge clk);
        end


        for (int i = 0; i < MESSAGE_NUMBER; i++) begin
            run_message();
        end

        $fclose(logit_file);

        $display("----------------------------------------------------------");
        $display("messages           %0d", message_index);
        $display("index mismatches   %0d", index_errors);
        $display("logit mismatches   %0d of %0d", logit_errors, message_index * MODEL_CLASS_NUMBER);
        $display("decision mismatches %0d", decision_errors);
        $display("count mismatches   %0d", count_errors);
        $display(
            "latency (cycles, message end -> decision): min %0d  mean %0d  max %0d",
            latency_minimum,
            latency_sum / message_index,
            latency_maximum
        );

        if (index_errors != 0 || logit_errors != 0 || decision_errors != 0 || count_errors != 0) begin
            $fatal(1, "FAIL: RTL does not match the golden model");
        end

        $display("PASS: RTL is bit-exact against the golden model");
        $finish;
    end

endmodule
