// Experimental raw signed INT8 x signed INT4 dot primitive, not in v2 executor.
// Consecutive weights occupy low then high nibbles, matching int4_reference.pack.
// Five registered arithmetic stages; global elastic stall preserves packet order.
// Model-specific calibration/requantization and matrix accumulation are separate.
module int4_dot16 (
    input logic clk,reset,
    input logic in_valid,
    output logic in_ready,
    input logic [127:0] activations,
    input logic [63:0] packed_weights,
    output logic out_valid,
    input logic out_ready,
    output logic signed [15:0] out_sum
);
    logic [4:0] valid_reg;
    logic advance;
    (* use_dsp="no" *) logic signed [11:0] products [0:15];
    logic signed [12:0] pairs [0:7];
    logic signed [13:0] quads [0:3];
    logic signed [14:0] octets [0:1];
    assign advance=!out_valid || out_ready;
    assign in_ready=!reset && advance;
    assign out_valid=valid_reg[4];
    always_ff @(posedge clk or posedge reset) begin
        if(reset)valid_reg<=0;
        else if(advance)valid_reg<={valid_reg[3:0],in_valid};
    end
    always_ff @(posedge clk) begin
        if(!reset && advance)begin
            for(int i=0;i<16;i++)
                products[i]<=12'($signed(activations[8*i+:8])) *
                             12'($signed(packed_weights[4*i+:4]));
            for(int i=0;i<8;i++)pairs[i]<=13'(products[2*i])+13'(products[2*i+1]);
            for(int i=0;i<4;i++)quads[i]<=14'(pairs[2*i])+14'(pairs[2*i+1]);
            for(int i=0;i<2;i++)octets[i]<=15'(quads[2*i])+15'(quads[2*i+1]);
            out_sum<=16'(octets[0])+16'(octets[1]);
        end
    end
endmodule
