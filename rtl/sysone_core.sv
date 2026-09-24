// Raw text bytes in, calibrated integer logits and a decision out.
//
//   bytes -> feature_generator -> embedding_bag -> classifier_head -> logits, argmax, top two
//
// One message at a time: ready_out falls after the message_end beat and rises again
// once the decision is out. Overlapping the next message's receive with this
// message's head is a later optimisation; it does not matter while the network
// transport, not the compute, sets the latency.
//
// The logits already carry the fitted temperature (folded into the output
// multipliers at export), so softmax(logit_out * s_out) on the host gives calibrated
// probabilities with no further correction. top_logit_out - second_logit_out is the
// margin for the cascade threshold.
//
// The model shape and pool_gain are parameters. The testbench and the board top pass
// the MODEL_* values from model_parameters.svh, which scripts/rtl_pack.py generates
// from the export manifest, so the RTL cannot drift from the model.
module sysone_core #(
    parameter integer ROW_NUMBER       = 16384,
    parameter integer DIMENSION        = 64,
    parameter integer HIDDEN           = 256,
    parameter integer CLASS_NUMBER     = 151,
    parameter integer MAXIMUM_FEATURES = 256,
    parameter integer POOL_GAIN        = 5,
    parameter integer MESSAGE_BYTES    = 2048,

    parameter string EMBEDDING_LOW_FILE     = "embedding_low.mem",
    parameter string EMBEDDING_HIGH_FILE    = "embedding_high.mem",
    parameter string RECIPROCAL_FILE        = "pool_reciprocals.mem",
    parameter string HIDDEN_WEIGHT_FILE     = "dense_hidden_weights.mem",
    parameter string HIDDEN_BIAS_FILE       = "dense_hidden_biases.mem",
    parameter string OUTPUT_WEIGHT_FILE     = "dense_output_weights.mem",
    parameter string OUTPUT_BIAS_FILE       = "dense_output_biases.mem",
    parameter string HIDDEN_MULTIPLIER_FILE = "requant_hidden_multipliers.mem",
    parameter string HIDDEN_REQUANT_FILE    = "requant_hidden_biases.mem",
    parameter string OUTPUT_MULTIPLIER_FILE = "requant_output_multipliers.mem",
    parameter string OUTPUT_REQUANT_FILE    = "requant_output_biases.mem"
) (
    input logic clk,
    input logic reset,

    // message bytes in
    input  logic [7:0] data_in,
    input  logic valid_in,
    input  logic message_end_in,
    output logic ready_out,

    // every logit, in class order
    output logic logit_valid_out,
    output logic [7:0] logit_class_out,
    output logic signed [15:0] logit_out,

    // the decision
    output logic decision_valid_out,
    output logic [7:0] decision_class_out,
    output logic signed [15:0] top_logit_out,
    output logic signed [15:0] second_logit_out,
    output logic [$clog2(MAXIMUM_FEATURES + 1)-1:0] feature_count_out,
    output logic overflow_out,

    // index stream, for the bit-exact testbench
    output logic feature_valid_out,
    output logic [$clog2(ROW_NUMBER)-1:0] feature_index_out
);

    localparam integer INDEX_WIDTH = $clog2(ROW_NUMBER);

    logic feature_valid;
    logic feature_end;
    logic [INDEX_WIDTH-1:0] feature_index;

    logic bag_done;
    logic signed [9:0] pooled_data [0:DIMENSION-1];

    logic head_busy;

    logic release_reg, release_next;
    logic clear_reg, clear_next;
    logic head_start_reg, head_start_next;
    logic started_reg, started_next;


    feature_generator #(
        .MESSAGE_BYTES   (MESSAGE_BYTES),
        .MAXIMUM_WORDS   (256),
        .MAXIMUM_FEATURES(MAXIMUM_FEATURES),
        .INDEX_WIDTH     (INDEX_WIDTH)
    ) feature_generator_inst (
        .clk              (clk),
        .reset            (reset),
        .data_in          (data_in),
        .valid_in         (valid_in),
        .message_end_in   (message_end_in),
        .ready_out        (ready_out),
        .feature_valid_out(feature_valid),
        .feature_index_out(feature_index),
        .feature_end_out  (feature_end),
        .release_in       (release_reg),
        .overflow_out     (overflow_out)
    );


    embedding_bag #(
        .ROW_NUMBER      (ROW_NUMBER),
        .DIMENSION       (DIMENSION),
        .INDEX_WIDTH     (INDEX_WIDTH),
        .MAXIMUM_FEATURES(MAXIMUM_FEATURES),
        .RECIPROCAL_SHIFT(16),
        .POOL_GAIN       (POOL_GAIN),

        .EMBEDDING_LOW_FILE (EMBEDDING_LOW_FILE),
        .EMBEDDING_HIGH_FILE(EMBEDDING_HIGH_FILE),
        .RECIPROCAL_FILE    (RECIPROCAL_FILE)
    ) embedding_bag_inst (
        .clk          (clk),
        .reset        (reset),
        .clear        (clear_reg),
        .valid_in     (feature_valid),
        .index_in     (feature_index),
        .end_in       (feature_end),
        .done         (bag_done),
        .feature_count(feature_count_out),
        .pooled_data  (pooled_data)
    );


    classifier_head #(
        .DIMENSION   (DIMENSION),
        .HIDDEN      (HIDDEN),
        .CLASS_NUMBER(CLASS_NUMBER),
        .MAC_LANES   (64),
        .ACC_WIDTH   (25),

        .HIDDEN_WEIGHT_FILE    (HIDDEN_WEIGHT_FILE),
        .HIDDEN_BIAS_FILE      (HIDDEN_BIAS_FILE),
        .OUTPUT_WEIGHT_FILE    (OUTPUT_WEIGHT_FILE),
        .OUTPUT_BIAS_FILE      (OUTPUT_BIAS_FILE),
        .HIDDEN_MULTIPLIER_FILE(HIDDEN_MULTIPLIER_FILE),
        .HIDDEN_REQUANT_FILE   (HIDDEN_REQUANT_FILE),
        .OUTPUT_MULTIPLIER_FILE(OUTPUT_MULTIPLIER_FILE),
        .OUTPUT_REQUANT_FILE   (OUTPUT_REQUANT_FILE)
    ) classifier_head_inst (
        .clk           (clk),
        .reset         (reset),
        .start         (head_start_reg),
        .pooled_data   (pooled_data),
        .busy          (head_busy),
        .logit_valid   (logit_valid_out),
        .logit_class   (logit_class_out),
        .logit_value   (logit_out),
        .decision_valid(decision_valid_out),
        .decision_class(decision_class_out),
        .top_logit     (top_logit_out),
        .second_logit  (second_logit_out)
    );


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            release_reg <= 1'b0;
            clear_reg <= 1'b0;
            head_start_reg <= 1'b0;
            started_reg <= 1'b0;
        end else begin
            release_reg <= release_next;
            clear_reg <= clear_next;
            head_start_reg <= head_start_next;
            started_reg <= started_next;
        end
    end


    always_comb begin
        release_next = 1'b0;
        clear_next = 1'b0;
        head_start_next = 1'b0;
        started_next = started_reg;

        // Start the head once per message. started_reg is only cleared after the bag
        // has actually dropped done, so the done level that is still high in the clock
        // between the decision and the clear cannot start the head a second time.
        if (bag_done && !started_reg) begin
            head_start_next = 1'b1;
            started_next = 1'b1;
        end

        if (!bag_done) begin
            started_next = 1'b0;
        end

        // Decision out: release the feature generator and clear the bag for the next message
        if (decision_valid_out) begin
            release_next = 1'b1;
            clear_next = 1'b1;
        end
    end

    assign feature_valid_out = feature_valid;
    assign feature_index_out = feature_index;

endmodule
