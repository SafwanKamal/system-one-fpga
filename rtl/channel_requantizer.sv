// Per-channel requantiser: one value per clock, streamed out in channel order.
//
//     out[k] = clamp((data[k] * multiplier[k] + bias[k] + 2^(SHIFT-1)) >>> SHIFT,
//                    OUTPUT_MINIMUM, OUTPUT_MAXIMUM)
//
// ReLU_quantizer is a single power-of-two shift. This model needs a multiplier per
// channel (per-channel weight scales, the activation scale and, for the logits, the
// folded temperature) and its bias is in post-multiplier units: B = b / s * 2^20,
// which is not divisible by M, so it cannot be preloaded into the dense_engine
// accumulator. The dense_engine bias ROMs are all zero and the bias is added here.
//
// The hidden layer uses OUTPUT_MINIMUM = 0 (ReLU) and OUTPUT_MAXIMUM = 127; the logits
// use +-32767.
//
// multiplier[k] must be unsigned and below 2^17 and |bias[k]| below 2^31, so the
// multiply is 25 x 18 signed (one DSP48E1). scripts/rtl_pack.py checks this.
module channel_requantizer #(
    parameter integer DATA_NUMBER      = 256,
    parameter integer INPUT_WIDTH      = 25,
    parameter integer OUTPUT_WIDTH     = 8,
    parameter integer OUTPUT_MINIMUM   = 0,
    parameter integer OUTPUT_MAXIMUM   = 127,
    parameter integer MULTIPLIER_SHIFT = 20,

    parameter string MULTIPLIER_FILE = "requant_multipliers.mem",
    parameter string BIAS_FILE       = "requant_biases.mem"
) (
    input logic clk,
    input logic reset,
    input logic start,

    input logic signed [INPUT_WIDTH-1:0] input_data
        [0:DATA_NUMBER-1],

    output logic busy,
    output logic done,

    output logic valid_out,
    output logic [$clog2(DATA_NUMBER)-1:0] index_out,
    output logic signed [OUTPUT_WIDTH-1:0] data_out
);

    localparam integer INDEX_WIDTH = (DATA_NUMBER <= 1) ? 1 : $clog2(DATA_NUMBER);
    localparam integer PRODUCT_WIDTH = 48;

    typedef enum logic [1:0] {
        IDLE,
        REQUANT,
        OUTPUT
    } state_t;

    state_t state_reg, state_next;

    logic [31:0] multiplier_ROM [0:DATA_NUMBER-1];
    logic [31:0] bias_ROM [0:DATA_NUMBER-1];

    initial begin
        $readmemh(MULTIPLIER_FILE, multiplier_ROM);
        $readmemh(BIAS_FILE, bias_ROM);
    end

    logic [INDEX_WIDTH-1:0] index_reg, index_next;
    logic valid_reg, valid_next;
    logic [INDEX_WIDTH-1:0] index_out_reg, index_out_next;
    logic signed [OUTPUT_WIDTH-1:0] data_reg, data_next;

    logic signed [17:0] multiplier;
    logic signed [31:0] bias;
    logic signed [PRODUCT_WIDTH-1:0] product;
    logic signed [PRODUCT_WIDTH-1:0] rounded;
    logic signed [PRODUCT_WIDTH-1:0] shifted;
    logic signed [OUTPUT_WIDTH-1:0] clamped;


    always_comb begin
        multiplier = {1'b0, multiplier_ROM[index_reg][16:0]};
        bias = bias_ROM[index_reg];

        product = input_data[index_reg] * multiplier;
        rounded = product + PRODUCT_WIDTH'(bias) + (PRODUCT_WIDTH'(1) <<< (MULTIPLIER_SHIFT - 1));
        shifted = rounded >>> MULTIPLIER_SHIFT;

        if (shifted < OUTPUT_MINIMUM) begin
            clamped = OUTPUT_WIDTH'(OUTPUT_MINIMUM);
        end else if (shifted > OUTPUT_MAXIMUM) begin
            clamped = OUTPUT_WIDTH'(OUTPUT_MAXIMUM);
        end else begin
            clamped = shifted[OUTPUT_WIDTH-1:0];
        end
    end


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            index_reg <= '0;
            valid_reg <= 1'b0;
            index_out_reg <= '0;
            data_reg <= '0;
        end else begin
            state_reg <= state_next;
            index_reg <= index_next;
            valid_reg <= valid_next;
            index_out_reg <= index_out_next;
            data_reg <= data_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        index_next = index_reg;
        valid_next = 1'b0;
        index_out_next = index_out_reg;
        data_next = data_reg;

        case (state_reg)
            IDLE: begin
                if (start) begin
                    index_next = '0;
                    state_next = REQUANT;
                end
            end

            REQUANT: begin
                valid_next = 1'b1;
                index_out_next = index_reg;
                data_next = clamped;

                if (index_reg == DATA_NUMBER - 1) begin
                    state_next = OUTPUT;
                end else begin
                    index_next = index_reg + 1'b1;
                end
            end

            // The last value is on data_out in this state, alongside done
            OUTPUT: begin
                state_next = IDLE;
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign busy = (state_reg != IDLE);
    assign done = (state_reg == OUTPUT);
    assign valid_out = valid_reg;
    assign index_out = index_out_reg;
    assign data_out = data_reg;

endmodule
