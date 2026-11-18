// Experimental drain-only two-stage selection cut, not in the v2 linear engine.
// Stage 1 selects channels separately beside each accumulator bank. Stage 2
// selects the bank before the following DSP operand stage. No whole-row copies.
// Integration adds one drain cycle and must delay all tags/multipliers/flushes.
module linear_drain_select #(
    parameter integer ROW_CHANNELS=32,
    parameter integer LANES=4,
    parameter integer COLUMN_WIDTH=$clog2(ROW_CHANNELS+1)
) (
    input logic clk,reset,advance,
    input logic in_valid,
    input logic [32*ROW_CHANNELS-1:0] row0,row1,
    input logic bank,
    input logic [COLUMN_WIDTH-1:0] column,
    input logic [LANES-1:0] lane_mask,
    input logic [17*LANES-1:0] multipliers,
    input logic [31:0] tag,
    output logic out_valid,
    output logic [32*LANES-1:0] selected,
    output logic [LANES-1:0] out_lane_mask,
    output logic [17*LANES-1:0] out_multipliers,
    output logic [31:0] out_tag
);
    logic first_valid,first_bank;
    logic [32*LANES-1:0] bank0_selected,bank1_selected;
    logic [LANES-1:0] first_mask;
    logic [17*LANES-1:0] first_multipliers;
    logic [31:0] first_tag;
    always_ff @(posedge clk or posedge reset)begin
        if(reset)begin first_valid<=0;out_valid<=0;end
        else if(advance)begin first_valid<=in_valid;out_valid<=first_valid;end
    end
    always_ff @(posedge clk)begin
        if(!reset && advance)begin
            first_bank<=bank;first_tag<=tag;first_multipliers<=multipliers;
            for(int l=0;l<LANES;l++)begin
                first_mask[l]<=lane_mask[l] && int'(column)+l<ROW_CHANNELS;
                if(int'(column)+l<ROW_CHANNELS)begin
                    bank0_selected[32*l+:32]<=row0[32*(int'(column)+l)+:32];
                    bank1_selected[32*l+:32]<=row1[32*(int'(column)+l)+:32];
                end else begin bank0_selected[32*l+:32]<=0;bank1_selected[32*l+:32]<=0;end
                selected[32*l+:32]<=first_mask[l] ?
                    (first_bank ? bank1_selected[32*l+:32] : bank0_selected[32*l+:32]) : 32'd0;
            end
            out_lane_mask<=first_mask;out_tag<=first_tag;out_multipliers<=first_multipliers;
        end
    end
endmodule
