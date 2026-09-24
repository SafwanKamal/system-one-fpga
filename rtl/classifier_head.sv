// DIMENSION -> HIDDEN -> CLASS_NUMBER head: two dense_engines, two requantisers, argmax.
//
// This is the RTL side of steps 3 to 6 of QuantModel._forward_int_block:
//     hidden_accumulator = pooled @ W1                          hidden dense_engine
//     hidden = clamp((hidden_accumulator * M1 + B1) >> 20, 0, 127)   channel_requantizer
//     output_accumulator = hidden @ W2                          output dense_engine
//     logit = clamp((output_accumulator * M2 + B2) >> 20, +-32767)   channel_requantizer
//
// Both engines run PIPELINED = 1 (one input per clock). W1 is 131 Kbit and goes to
// LUTRAM (ROM_STYLE = "distributed") so that block RAM fits: the embedding table
// already takes 114 of the 135 RAMB36. W2 stays in BRAM.
//
// The engine bias ROMs are all zero; the biases are applied in the requantisers,
// after the multiplier, which is where this model defines them.
//
// Accumulator widths from worst-case bounds: |hidden_accumulator| <= 225 * 127 * 64
// and |output_accumulator| <= 127 * 127 * 256 are both below 2^22, so 25 bits (the
// DSP48E1 A port) is safe for both.
module classifier_head #(
    parameter integer DIMENSION    = 64,
    parameter integer HIDDEN       = 256,
    parameter integer CLASS_NUMBER = 151,
    parameter integer MAC_LANES    = 64,
    parameter integer ACC_WIDTH    = 25,

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
    input logic start,

    input logic signed [9:0] pooled_data
        [0:DIMENSION-1],

    output logic busy,

    // every logit, in class order
    output logic logit_valid,
    output logic [7:0] logit_class,
    output logic signed [15:0] logit_value,

    // the decision, two clocks after the last logit
    output logic decision_valid,
    output logic [7:0] decision_class,
    output logic signed [15:0] top_logit,
    output logic signed [15:0] second_logit
);

    typedef enum logic [2:0] {
        IDLE,
        HIDDEN_LAYER,
        HIDDEN_REQUANT,
        OUTPUT_LAYER,
        OUTPUT_REQUANT,
        DECISION
    } state_t;

    state_t state_reg, state_next;

    logic hidden_engine_start_reg, hidden_engine_start_next;
    logic hidden_requant_start_reg, hidden_requant_start_next;
    logic output_engine_start_reg, output_engine_start_next;
    logic output_requant_start_reg, output_requant_start_next;
    logic decision_valid_reg, decision_valid_next;

    logic signed [7:0] hidden_data_reg [0:HIDDEN-1];
    logic signed [7:0] hidden_data_next [0:HIDDEN-1];

    logic signed [ACC_WIDTH-1:0] hidden_accumulator [0:HIDDEN-1];
    logic signed [ACC_WIDTH-1:0] output_accumulator [0:CLASS_NUMBER-1];

    logic hidden_engine_busy, hidden_engine_done;
    logic output_engine_busy, output_engine_done;

    logic hidden_requant_busy, hidden_requant_done;
    logic hidden_requant_valid;
    logic [$clog2(HIDDEN)-1:0] hidden_requant_index;
    logic signed [7:0] hidden_requant_data;

    logic output_requant_busy, output_requant_done;
    logic output_requant_valid;
    logic [$clog2(CLASS_NUMBER)-1:0] output_requant_index;
    logic signed [15:0] output_requant_data;


    dense_engine #(
        .INPUT_NUMBER (DIMENSION),
        .OUTPUT_NUMBER(HIDDEN),
        .MAC_LANES    (MAC_LANES),

        .INPUT_WIDTH (10),
        .WEIGHT_WIDTH(8),
        .ACC_WIDTH   (ACC_WIDTH),

        .WEIGHT_FILE(HIDDEN_WEIGHT_FILE),
        .BIAS_FILE  (HIDDEN_BIAS_FILE),
        .ROM_STYLE  ("distributed"),
        .PIPELINED  (1)
    ) hidden_dense_engine_inst (
        .clk        (clk),
        .reset      (reset),
        .start      (hidden_engine_start_reg),
        .input_data (pooled_data),
        .busy       (hidden_engine_busy),
        .done       (hidden_engine_done),
        .output_data(hidden_accumulator)
    );


    channel_requantizer #(
        .DATA_NUMBER     (HIDDEN),
        .INPUT_WIDTH     (ACC_WIDTH),
        .OUTPUT_WIDTH    (8),
        .OUTPUT_MINIMUM  (0),
        .OUTPUT_MAXIMUM  (127),
        .MULTIPLIER_SHIFT(20),

        .MULTIPLIER_FILE(HIDDEN_MULTIPLIER_FILE),
        .BIAS_FILE      (HIDDEN_REQUANT_FILE)
    ) hidden_requantizer_inst (
        .clk       (clk),
        .reset     (reset),
        .start     (hidden_requant_start_reg),
        .input_data(hidden_accumulator),
        .busy      (hidden_requant_busy),
        .done      (hidden_requant_done),
        .valid_out (hidden_requant_valid),
        .index_out (hidden_requant_index),
        .data_out  (hidden_requant_data)
    );


    dense_engine #(
        .INPUT_NUMBER (HIDDEN),
        .OUTPUT_NUMBER(CLASS_NUMBER),
        .MAC_LANES    (MAC_LANES),

        .INPUT_WIDTH (8),
        .WEIGHT_WIDTH(8),
        .ACC_WIDTH   (ACC_WIDTH),

        .WEIGHT_FILE(OUTPUT_WEIGHT_FILE),
        .BIAS_FILE  (OUTPUT_BIAS_FILE),
        .ROM_STYLE  ("block"),
        .PIPELINED  (1)
    ) output_dense_engine_inst (
        .clk        (clk),
        .reset      (reset),
        .start      (output_engine_start_reg),
        .input_data (hidden_data_reg),
        .busy       (output_engine_busy),
        .done       (output_engine_done),
        .output_data(output_accumulator)
    );


    channel_requantizer #(
        .DATA_NUMBER     (CLASS_NUMBER),
        .INPUT_WIDTH     (ACC_WIDTH),
        .OUTPUT_WIDTH    (16),
        .OUTPUT_MINIMUM  (-32767),
        .OUTPUT_MAXIMUM  (32767),
        .MULTIPLIER_SHIFT(20),

        .MULTIPLIER_FILE(OUTPUT_MULTIPLIER_FILE),
        .BIAS_FILE      (OUTPUT_REQUANT_FILE)
    ) output_requantizer_inst (
        .clk       (clk),
        .reset     (reset),
        .start     (output_requant_start_reg),
        .input_data(output_accumulator),
        .busy      (output_requant_busy),
        .done      (output_requant_done),
        .valid_out (output_requant_valid),
        .index_out (output_requant_index),
        .data_out  (output_requant_data)
    );


    logit_argmax #(
        .CLASS_WIDTH(8),
        .LOGIT_WIDTH(16)
    ) logit_argmax_inst (
        .clk         (clk),
        .reset       (reset),
        .clear       (output_requant_start_reg),
        .valid_in    (output_requant_valid),
        .class_in    (8'(output_requant_index)),
        .logit_in    (output_requant_data),
        .best_class  (decision_class),
        .best_logit  (top_logit),
        .second_logit(second_logit)
    );


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            hidden_engine_start_reg <= 1'b0;
            hidden_requant_start_reg <= 1'b0;
            output_engine_start_reg <= 1'b0;
            output_requant_start_reg <= 1'b0;
            decision_valid_reg <= 1'b0;
            for (int i = 0; i < HIDDEN; i++) begin
                hidden_data_reg[i] <= '0;
            end
        end else begin
            state_reg <= state_next;
            hidden_engine_start_reg <= hidden_engine_start_next;
            hidden_requant_start_reg <= hidden_requant_start_next;
            output_engine_start_reg <= output_engine_start_next;
            output_requant_start_reg <= output_requant_start_next;
            decision_valid_reg <= decision_valid_next;
            hidden_data_reg <= hidden_data_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        hidden_engine_start_next = 1'b0;
        hidden_requant_start_next = 1'b0;
        output_engine_start_next = 1'b0;
        output_requant_start_next = 1'b0;
        decision_valid_next = 1'b0;
        hidden_data_next = hidden_data_reg;

        // The hidden activations arrive one per clock and become the second layer's input
        if (hidden_requant_valid) begin
            hidden_data_next[hidden_requant_index] = hidden_requant_data;
        end

        case (state_reg)
            IDLE: begin
                if (start) begin
                    hidden_engine_start_next = 1'b1;
                    state_next = HIDDEN_LAYER;
                end
            end

            HIDDEN_LAYER: begin
                if (hidden_engine_done) begin
                    hidden_requant_start_next = 1'b1;
                    state_next = HIDDEN_REQUANT;
                end
            end

            HIDDEN_REQUANT: begin
                // The last activation is written on the same edge that starts the engine
                if (hidden_requant_done) begin
                    output_engine_start_next = 1'b1;
                    state_next = OUTPUT_LAYER;
                end
            end

            OUTPUT_LAYER: begin
                if (output_engine_done) begin
                    output_requant_start_next = 1'b1;
                    state_next = OUTPUT_REQUANT;
                end
            end

            OUTPUT_REQUANT: begin
                // logit_argmax takes the last logit on this edge, so the decision is ready next clock
                if (output_requant_done) begin
                    state_next = DECISION;
                end
            end

            DECISION: begin
                decision_valid_next = 1'b1;
                state_next = IDLE;
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign busy = (state_reg != IDLE);
    assign logit_valid = output_requant_valid;
    assign logit_class = 8'(output_requant_index);
    assign logit_value = output_requant_data;
    assign decision_valid = decision_valid_reg;

endmodule
