// Observational only: registered event controls, exact current-edge count.
// Pending clear dominates increment. Unsigned arithmetic wraps modulo 2**WIDTH.
// Never use this module as a delayed deadline or as proof of bus quiescence.
module observed_cycle_counter #(parameter integer WIDTH=32)(
    input logic clk, reset, clear, increment,
    output wire [WIDTH-1:0] count
);
    logic pending_clear, pending_increment;
    logic [WIDTH-1:0] bank;
    always_ff @(posedge clk or posedge reset) begin
        if(reset) begin
            pending_clear <= 0;
            pending_increment <= 0;
            bank <= 0;
        end else begin
            pending_clear <= clear;
            pending_increment <= increment;
            if(pending_clear) bank <= 0;
            else if(pending_increment) bank <= bank + 1'b1;
        end
    end
    assign count = pending_clear ? {WIDTH{1'b0}} : bank + {{(WIDTH-1){1'b0}}, pending_increment};
endmodule
