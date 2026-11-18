`timescale 1ns/1ps
module rope_pair_int8_tb;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,in_valid=0,in_ready,out_valid,out_ready,out_error;
 logic signed [7:0] low=0,high=0,out_low,out_high;
 logic signed [16:0] cosine=0,sine=0;
 logic [4:0] fraction=1;logic [31:0] in_tag=0,out_tag;
 int want_low[0:65535],want_high[0:65535],want_error[0:65535];
 int queue_tag[0:65535],queue_low[0:65535],queue_high[0:65535],queue_error[0:65535];
 int head=0,tail=0,cycle=0,accepted=0,compared=0,cancelled=0,invalid=0;
 logic held=0;logic [48:0] held_tuple;
 assign out_ready=cycle%7>1 && cycle%1000>=60;
 rope_pair_int8 dut(.*);
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(reset)begin cancelled=cancelled+tail-head;head=0;tail=0;held=0;end
  else begin
   if(held && (!out_valid || {out_error,out_tag,out_low,out_high}!==held_tuple))$fatal(1,"RoPE output unstable under stall");
   held=out_valid && !out_ready;held_tuple={out_error,out_tag,out_low,out_high};
   if(in_valid && in_ready)begin
    queue_tag[tail]=int'(in_tag);queue_low[tail]=want_low[in_tag];queue_high[tail]=want_high[in_tag];queue_error[tail]=want_error[in_tag];
    tail++;accepted++;
   end
   if(out_valid && out_ready)begin
    if(head>=tail || out_tag!==32'(queue_tag[head]) || int'(out_low)!=queue_low[head] || int'(out_high)!=queue_high[head] || int'(out_error)!=queue_error[head])
     $fatal(1,"RoPE reference/tag/error mismatch tag=%0d got%0d,%0d expected%0d,%0d",out_tag,out_low,out_high,queue_low[head],queue_high[head]);
    if(out_error)invalid++;
    head++;compared++;
   end
  end
  if(cycle>300000)$fatal(1,"RoPE watchdog");
 end
 initial begin
  int fd,code,lo,hi,c,s,f,ylo,yhi,err,index;
  fd=$fopen("vectors.txt","r");if(!fd)$fatal(1,"Missing RoPE vectors");
  repeat(3)@(negedge clk);reset=0;index=0;
  while(!$feof(fd))begin
   code=$fscanf(fd,"%d %d %d %d %d %d %d %d",lo,hi,c,s,f,ylo,yhi,err);
   if(code!=8)break;
   @(negedge clk);
   if(index==8192 || index==24576)begin reset=1;repeat(2)@(negedge clk);reset=0;end
   if(index%13==0)@(negedge clk);
   want_low[index]=ylo;want_high[index]=yhi;want_error[index]=err;
   low=8'(lo);high=8'(hi);cosine=17'(c);sine=17'(s);fraction=5'(f);in_tag=32'(index);in_valid=1;
   do @(posedge clk);while(!in_ready);
   @(negedge clk);in_valid=0;index++;
  end
  while(head!=tail || out_valid)@(negedge clk);
  if(index!=49101 || accepted!=index || compared+cancelled!=accepted || invalid!=6)$fatal(1,"Incomplete RoPE coverage");
  $display("PASS RoPE: accepted%0d compared%0d reset-cancelled%0d invalid%0d, fractions1..15, corner/random, stalls/tags",accepted,compared,cancelled,invalid);$finish;
 end
endmodule
