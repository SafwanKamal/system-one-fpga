// Candidate raw dot product; 20 signed bits cover all 16 INT8 products,
// including 16*(-128)*(-128)=262144. No scaling, saturation or accumulation.
// Five registered stages. One global elastic stall keeps every payload stable.
module signed_int8_dot16_v1 (
    input logic clk,reset,in_valid,
    output logic in_ready,
    input logic [127:0] activations,weights,
    output logic out_valid,
    input logic out_ready,
    output logic signed [19:0] out_sum
);
    logic [4:0] valid_reg;
    (* use_dsp="yes" *) logic signed [15:0] products [0:15];
    logic signed [16:0] pairs [0:7];
    logic signed [17:0] quads [0:3];
    logic signed [18:0] octets [0:1];
    wire advance=!out_valid || out_ready;
    assign in_ready=!reset && advance;
    assign out_valid=!reset && valid_reg[4];
    always_ff @(posedge clk) begin
        if(reset) valid_reg<=0;
        else if(advance) begin
            valid_reg<={valid_reg[3:0],in_valid};
            for(integer i=0;i<16;i=i+1)
                products[i]<=16'($signed(activations[8*i+:8])) * 16'($signed(weights[8*i+:8]));
            for(integer i=0;i<8;i=i+1) pairs[i]<=17'(products[2*i])+17'(products[2*i+1]);
            for(integer i=0;i<4;i=i+1) quads[i]<=18'(pairs[2*i])+18'(pairs[2*i+1]);
            for(integer i=0;i<2;i=i+1) octets[i]<=19'(quads[2*i])+19'(quads[2*i+1]);
            out_sum<=20'(octets[0])+20'(octets[1]);
        end
    end
endmodule
