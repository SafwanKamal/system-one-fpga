// Three-stage unsigned exponent*reciprocal probability kernel: operands,
// DSP product, then rounded/clamped output.
// Continuous throughput; reset cancels valid entries. Caller must align tags
// and fetch exponent rows two clocks earlier than the legacy one-stage kernel.
module attention_probability_input(input logic clk,reset,in_valid,
 input logic [15:0] exponent,input logic [8:0] reciprocal,
 output logic out_valid,output logic [8:0] probability);
 (* use_dsp="yes" *) logic [24:0] product;
 logic product_valid,operand_valid;
 logic [15:0] exponent_operand;logic [8:0] reciprocal_operand;
 logic [9:0] rounded;
 assign rounded={1'b0,product[24:16]}+10'(product[15]);
 always_ff @(posedge clk)begin
  exponent_operand<=exponent;reciprocal_operand<=reciprocal;
  product<=exponent_operand*reciprocal_operand;
  probability<=rounded>255 ? 9'd255 : {1'b0,rounded[7:0]};
  if(reset)begin operand_valid<=0;product_valid<=0;out_valid<=0;end
  else begin operand_valid<=in_valid;product_valid<=operand_valid;out_valid<=product_valid;end
 end
endmodule
