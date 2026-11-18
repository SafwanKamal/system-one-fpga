// Experimental two-stage unsigned exponent*reciprocal probability kernel.
// Continuous throughput; reset cancels valid entries. Caller must align tags
// and fetch exponent rows one clock earlier than the existing one-stage kernel.
module attention_probability(input logic clk,reset,in_valid,
 input logic [15:0] exponent,input logic [8:0] reciprocal,
 output logic out_valid,output logic [8:0] probability);
 (* use_dsp="yes" *) logic [24:0] product;
 logic product_valid;
 logic [9:0] rounded;
 assign rounded={1'b0,product[24:16]}+10'(product[15]);
 always_ff @(posedge clk)begin
  product<=exponent*reciprocal;
  probability<=rounded>255 ? 9'd255 : {1'b0,rounded[7:0]};
  if(reset)begin product_valid<=0;out_valid<=0;end
  else begin product_valid<=in_valid;out_valid<=product_valid;end
 end
endmodule
