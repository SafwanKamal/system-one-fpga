// Unsigned restoring divider, one quotient bit per clock.
//
// For status values that change rarely (bandwidth readouts), where a
// combinational divider would only cost area and timing.
module sequential_divider #(
    parameter integer WIDTH = 40
) (
    input logic clk,
    input logic reset,

    input logic start,
    input logic [WIDTH-1:0] dividend,
    input logic [WIDTH-1:0] divisor,

    output logic busy,
    output logic done,                   // one-clock pulse
    output logic [WIDTH-1:0] quotient
);

    logic [WIDTH-1:0] quotient_reg, quotient_next;
    logic [WIDTH-1:0] remainder_reg, remainder_next;
    logic [WIDTH-1:0] divisor_reg, divisor_next;
    logic [$clog2(WIDTH+1)-1:0] bit_reg, bit_next;
    logic busy_reg, busy_next;
    logic done_reg, done_next;
    logic [WIDTH:0] trial;


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            quotient_reg <= '0;
            remainder_reg <= '0;
            divisor_reg <= '0;
            bit_reg <= '0;
            busy_reg <= 1'b0;
            done_reg <= 1'b0;
        end else begin
            quotient_reg <= quotient_next;
            remainder_reg <= remainder_next;
            divisor_reg <= divisor_next;
            bit_reg <= bit_next;
            busy_reg <= busy_next;
            done_reg <= done_next;
        end
    end


    always_comb begin
        quotient_next = quotient_reg;
        remainder_next = remainder_reg;
        divisor_next = divisor_reg;
        bit_next = bit_reg;
        busy_next = busy_reg;
        done_next = 1'b0;
        trial = '0;

        if (!busy_reg) begin
            if (start) begin
                quotient_next = dividend;          // shifted out MSB first
                remainder_next = '0;
                divisor_next = (divisor == '0) ? WIDTH'(1) : divisor;
                bit_next = WIDTH[$clog2(WIDTH+1)-1:0];
                busy_next = 1'b1;
            end
        end else begin
            trial = {remainder_reg, quotient_reg[WIDTH-1]} - {1'b0, divisor_reg};
            if (!trial[WIDTH]) begin
                remainder_next = trial[WIDTH-1:0];
                quotient_next = {quotient_reg[WIDTH-2:0], 1'b1};
            end else begin
                remainder_next = {remainder_reg[WIDTH-2:0], quotient_reg[WIDTH-1]};
                quotient_next = {quotient_reg[WIDTH-2:0], 1'b0};
            end
            bit_next = bit_reg - 1'b1;
            if (bit_reg == 1) begin
                busy_next = 1'b0;
                done_next = 1'b1;
            end
        end
    end

    assign busy = busy_reg;
    assign done = done_reg;
    assign quotient = quotient_reg;

endmodule
