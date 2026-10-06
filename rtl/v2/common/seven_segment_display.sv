// Eight-digit multiplexed seven-segment display showing two 4-digit decimal numbers.
//
// left_value goes on digits 7..4, right_value on digits 3..0; values above 9999
// show as 9999. Binary to BCD is done by iterative double dabble, one bit per
// clock, restarted whenever it finishes, so the display follows its inputs within
// a few microseconds without a combinational converter.
//
// Nexys 4 DDR: segments and anodes are active low.
module seven_segment_display #(
    parameter integer CLOCK_HZ = 75_000_000,
    parameter integer REFRESH_HZ = 1000           // per digit
) (
    input logic clk,
    input logic reset,
    input logic [13:0] left_value,
    input logic [13:0] right_value,
    output logic [6:0] segments_n,                // {g, f, e, d, c, b, a}
    output logic decimal_point_n,
    output logic [7:0] anodes_n
);

    localparam integer DIVIDE = CLOCK_HZ / REFRESH_HZ;

    // ---- double dabble over both values at once (28 input bits -> 8 digits)
    logic [27:0] shift_reg, shift_next;
    logic [31:0] bcd_reg, bcd_next;
    logic [31:0] shown_reg, shown_next;
    logic [4:0] step_reg, step_next;
    logic [31:0] adjusted;

    // ---- digit scan
    logic [$clog2(DIVIDE)-1:0] tick_reg, tick_next;
    logic [2:0] digit_reg, digit_next;
    logic [3:0] nibble;


    function automatic logic [15:0] dabble_add3(input logic [15:0] b);
        logic [15:0] r;
        for (int k = 0; k < 4; k++) begin
            r[4*k +: 4] = (b[4*k +: 4] >= 5) ? b[4*k +: 4] + 4'd3 : b[4*k +: 4];
        end
        return r;
    endfunction


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            shift_reg <= '0;
            bcd_reg <= '0;
            shown_reg <= '0;
            step_reg <= '0;
            tick_reg <= '0;
            digit_reg <= '0;
        end else begin
            shift_reg <= shift_next;
            bcd_reg <= bcd_next;
            shown_reg <= shown_next;
            step_reg <= step_next;
            tick_reg <= tick_next;
            digit_reg <= digit_next;
        end
    end


    always_comb begin
        shift_next = shift_reg;
        bcd_next = bcd_reg;
        shown_next = shown_reg;
        step_next = step_reg;
        adjusted = '0;

        if (step_reg == 0) begin
            shift_next = {(left_value > 14'd9999) ? 14'd9999 : left_value,
                          (right_value > 14'd9999) ? 14'd9999 : right_value};
            bcd_next = '0;
            step_next = 5'd1;
        end else begin
            // two independent 14-bit conversions packed side by side
            adjusted = {dabble_add3(bcd_reg[31:16]), dabble_add3(bcd_reg[15:0])};
            bcd_next = {adjusted[30:16], shift_reg[27], adjusted[14:0], shift_reg[13]};
            shift_next = {shift_reg[26:14], 1'b0, shift_reg[12:0], 1'b0};
            if (step_reg == 5'd14) begin
                shown_next = {adjusted[30:16], shift_reg[27], adjusted[14:0], shift_reg[13]};
                step_next = '0;
            end else begin
                step_next = step_reg + 1'b1;
            end
        end
    end


    always_comb begin
        tick_next = tick_reg + 1'b1;
        digit_next = digit_reg;
        if (tick_reg == DIVIDE - 1) begin
            tick_next = '0;
            digit_next = digit_reg + 1'b1;
        end
        nibble = shown_reg[4*digit_reg +: 4];
        case (nibble)
            4'd0: segments_n = ~7'b0111111;
            4'd1: segments_n = ~7'b0000110;
            4'd2: segments_n = ~7'b1011011;
            4'd3: segments_n = ~7'b1001111;
            4'd4: segments_n = ~7'b1100110;
            4'd5: segments_n = ~7'b1101101;
            4'd6: segments_n = ~7'b1111101;
            4'd7: segments_n = ~7'b0000111;
            4'd8: segments_n = ~7'b1111111;
            4'd9: segments_n = ~7'b1101111;
            default: segments_n = ~7'b1000000;     // dash
        endcase
        anodes_n = ~(8'b1 << digit_reg);
        decimal_point_n = 1'b1;
    end

endmodule
