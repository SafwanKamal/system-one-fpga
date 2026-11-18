// Independent deadline outcome channel. Never gates/aborts outstanding AXI.
// At a sampled start edge age=0. By edge budget (inclusive) produce success,
// hardware fault, or deadline exceeded. Completion exactly at budget succeeds.
// Timeout permanently quarantines this instance until a safe SYSTEM reset;
// acknowledging a result cannot recycle buffers still owned by a late engine.
module deadline_supervisor (
    input logic clk, reset, start, ack, core_done, core_fault,
    input logic [31:0] budget_cycles,
    output logic ready, active, result_valid, quarantined,
    output logic [2:0] outcome,
    output logic [31:0] elapsed
);
    localparam logic [2:0] NONE=0, ACCEPTED=1, DEADLINE_EXCEEDED=2,
                           INVALID_INPUT=3, HARDWARE_FAULT=4;
    logic [31:0] limit_reg;
    assign ready = !active && !result_valid && !quarantined;
    always_ff @(posedge clk) begin
        if (reset) begin
            active <= 0; result_valid <= 0; quarantined <= 0;
            outcome <= NONE; elapsed <= 0; limit_reg <= 0;
        end else begin
            if (ack && result_valid && !quarantined) begin
                result_valid <= 0;
                outcome <= NONE;
            end
            if (start && ready) begin
                elapsed <= 0;
                limit_reg <= budget_cycles;
                if (budget_cycles == 0) begin
                    outcome <= INVALID_INPUT;
                    result_valid <= 1;
                end else active <= 1;
            end else if (active) begin
                elapsed <= elapsed + 1'b1;
                if (core_done) begin
                    outcome <= core_fault ? HARDWARE_FAULT : ACCEPTED;
                    result_valid <= 1;
                    active <= 0;
                end else if (elapsed == limit_reg - 1'b1) begin
                    outcome <= DEADLINE_EXCEEDED;
                    result_valid <= 1;
                    active <= 0;
                    quarantined <= 1;
                end
            end
        end
    end
endmodule
