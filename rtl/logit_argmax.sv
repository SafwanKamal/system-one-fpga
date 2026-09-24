// Running argmax over a stream of logits, plus the runner-up value.
//
// Strict ">" means the first maximum wins, which matches numpy.argmax. The two
// largest logits give the margin the cascade threshold uses.
module logit_argmax #(
    parameter integer CLASS_WIDTH = 8,
    parameter integer LOGIT_WIDTH = 16
) (
    input logic clk,
    input logic reset,
    input logic clear,

    input logic valid_in,
    input logic [CLASS_WIDTH-1:0] class_in,
    input logic signed [LOGIT_WIDTH-1:0] logit_in,

    output logic [CLASS_WIDTH-1:0] best_class,
    output logic signed [LOGIT_WIDTH-1:0] best_logit,
    output logic signed [LOGIT_WIDTH-1:0] second_logit
);

    // Below every clamped logit, so the first value always replaces it
    localparam logic signed [LOGIT_WIDTH-1:0] MINIMUM_LOGIT = {1'b1, {(LOGIT_WIDTH-1){1'b0}}};

    logic [CLASS_WIDTH-1:0] best_class_reg, best_class_next;
    logic signed [LOGIT_WIDTH-1:0] best_logit_reg, best_logit_next;
    logic signed [LOGIT_WIDTH-1:0] second_logit_reg, second_logit_next;

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            best_class_reg <= '0;
            best_logit_reg <= MINIMUM_LOGIT;
            second_logit_reg <= MINIMUM_LOGIT;
        end else begin
            best_class_reg <= best_class_next;
            best_logit_reg <= best_logit_next;
            second_logit_reg <= second_logit_next;
        end
    end

    always_comb begin
        best_class_next = best_class_reg;
        best_logit_next = best_logit_reg;
        second_logit_next = second_logit_reg;

        if (clear) begin
            best_class_next = '0;
            best_logit_next = MINIMUM_LOGIT;
            second_logit_next = MINIMUM_LOGIT;
        end else if (valid_in) begin
            if (logit_in > best_logit_reg) begin
                second_logit_next = best_logit_reg;
                best_logit_next = logit_in;
                best_class_next = class_in;
            end else if (logit_in > second_logit_reg) begin
                second_logit_next = logit_in;
            end
        end
    end

    assign best_class = best_class_reg;
    assign best_logit = best_logit_reg;
    assign second_logit = second_logit_reg;

endmodule
