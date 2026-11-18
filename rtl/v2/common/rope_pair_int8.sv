// Experimental half-split RoPE pair; no decoder/model integration.
// Signed17-bit tables cover +32768 at fraction15. The entire three-stage
// pipeline stalls with output backpressure. Invalid code/table/fraction inputs
// retire with error and zero data; caller owns positions/table calibration.
module rope_pair_int8(input logic clk,reset,in_valid,output logic in_ready,
 input logic signed [7:0] low,high,input logic signed [16:0] cosine,sine,
 input logic [4:0] fraction,input logic [31:0] in_tag,
 output logic out_valid,input logic out_ready,output logic out_error,
 output logic signed [7:0] out_low,out_high,output logic [31:0] out_tag);
 logic advance;logic [2:0] valid,error_pipe;
 logic [4:0] fractions[0:1];logic [31:0] tags[0:2];
 logic signed [24:0] lc,hs,hc,ls;
 logic signed [26:0] rounded_low,rounded_high;
 logic signed [26:0] shifted_low,shifted_high;
 logic input_error;logic signed [17:0] table_limit;
 assign table_limit=18'sd1 <<< fraction;
 assign input_error=fraction<1 || fraction>15 || low==-128 || high==-128
  || 18'(cosine)>table_limit || 18'(cosine)<-table_limit
  || 18'(sine)>table_limit || 18'(sine)<-table_limit;
 assign advance=!valid[2] || out_ready;
 assign in_ready=!reset && advance;assign out_valid=!reset && valid[2];
 assign out_tag=tags[2];assign out_error=error_pipe[2];
 assign shifted_low=rounded_low >>> fractions[1];
 assign shifted_high=rounded_high >>> fractions[1];
 always_ff @(posedge clk)begin
  if(reset)begin valid<=0;error_pipe<=0;end
  else if(advance)begin
   valid<={valid[1:0],in_valid};error_pipe<={error_pipe[1:0],input_error};
   lc<=low*cosine;hs<=high*sine;hc<=high*cosine;ls<=low*sine;
   fractions[0]<=fraction;fractions[1]<=fractions[0];
   tags[0]<=in_tag;tags[1]<=tags[0];tags[2]<=tags[1];
   if(fractions[0]>=1 && fractions[0]<=15)begin
    rounded_low<=27'(lc)-27'(hs)+(27'sd1 <<< (fractions[0]-1));
    rounded_high<=27'(hc)+27'(ls)+(27'sd1 <<< (fractions[0]-1));
   end else begin rounded_low<=0;rounded_high<=0;end
   out_low<=error_pipe[1] ? 8'sd0 : shifted_low>127 ? 8'sd127 : shifted_low< -127 ? -8'sd127 : 8'(shifted_low);
   out_high<=error_pipe[1] ? 8'sd0 : shifted_high>127 ? 8'sd127 : shifted_high< -127 ? -8'sd127 : 8'(shifted_high);
  end
 end
endmodule
