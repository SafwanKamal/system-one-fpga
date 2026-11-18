`timescale 1ns/1ps
module attention_probability_input_tb;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,in_valid=0,out_valid;
 logic [15:0] exponent=0;logic [8:0] reciprocal=0,probability;
 logic old_valid=0,older_valid=0;integer old_expected=0,older_expected=0,comparisons=0;
 attention_probability_input dut(.*);
 task automatic tick(input bit rst,input bit valid,input int e,input int r);
  integer value;
  @(negedge clk);reset=rst;in_valid=valid;exponent=16'(e);reciprocal=9'(r);
  @(posedge clk);#1;
  if(out_valid!==(!rst && older_valid))$fatal(1,"Probability valid alignment mismatch");
  if(out_valid)begin
   if(probability!==9'(older_expected))$fatal(1,"Probability arithmetic mismatch");
   comparisons++;
  end
  value=((e*r)+32768)>>16;
  older_expected=old_expected;older_valid=!rst && old_valid;old_expected=value>255 ? 255 : value;old_valid=!rst && valid;
 endtask
 initial begin
  tick(1,0,0,0);
  // Exhaust every UINT16 exponent and UINT9 reciprocal, including hardware
  // row-valid range0..256 and values257..511 for truncation/saturation edges.
  for(int r=0;r<512;r++)for(int e=0;e<65536;e++)tick(0,1,e,r);
  tick(0,0,0,0);tick(0,0,0,0);
  for(int i=0;i<4096;i++)tick(i%101==0,i%7!=0,$urandom_range(0,65535),$urandom_range(0,511));
  tick(1,0,0,0);tick(0,0,0,0);
  $display("PASS probability: %0d comparisons, all UINT16*UINT9 pairs, bubbles/reset, exact rounded saturation",comparisons);$finish;
 end
endmodule
