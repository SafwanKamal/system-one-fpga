`timescale 1ns/1ps
module relative_chunk_retire_tb;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,operation_valid=0,operation_ready;
 logic [39:0] model_base=40'h800000000,descriptor_model_base;
 logic [32:0] model_bytes=33'd65536,operation_bytes=0;
 logic [31:0] operation_offset=0,descriptor_offset;
 logic [32:0] descriptor_model_bytes,descriptor_bytes,completed_bytes;
 logic descriptor_valid,descriptor_ready,completion_valid,completion_ready;
 logic [1:0] completion_code,done_code;
 logic done_valid,done_ready=0,poisoned;
 logic memory_valid,memory_ready,memory_read_valid,memory_read_ready;
 logic [39:0] memory_address;
 logic [7:0] memory_beats;
 logic [127:0] memory_read_data,read_data;
 logic memory_read_last,memory_response_error=0,read_valid,read_ready,read_last;
 int cycle=0,descriptors=0,data_beats=0,active_beats=0,index=0,fault_descriptor=-1;
 logic [39:0] active_address,expected_address;
 assign memory_ready=active_beats==0 && cycle%5!=0;
 assign memory_read_valid=active_beats>0 && cycle%7!=0;
 assign memory_read_last=index==active_beats-1;
 assign memory_read_data=128'(active_address+40'(index*16));
 assign read_ready=cycle%11!=0 && cycle%11!=1;
 relative_read_chunker #(.BEATS_WIDTH(8)) chunker(.*);
 relative_read_retire #(.BEATS_WIDTH(8)) retire(
  .clk,.reset,.model_base(descriptor_model_base),.model_bytes(descriptor_model_bytes),
  .request_valid(descriptor_valid),.request_ready(descriptor_ready),
  .request_offset(descriptor_offset),.request_bytes(descriptor_bytes),
  .memory_valid,.memory_ready,.memory_address,.memory_beats,
  .memory_read_valid,.memory_read_ready,.memory_read_data,.memory_read_last,.memory_response_error,
  .read_valid,.read_ready,.read_data,.read_last,.completion_valid,.completion_ready,.completion_code,.poisoned);
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(reset)begin active_beats<=0;index<=0;memory_response_error<=0;end
  else begin
   if(memory_valid && memory_ready)begin
    if(active_beats!=0 || memory_address!==expected_address || memory_beats==0)
     $fatal(1,"Memory descriptor order/address mismatch");
    expected_address=expected_address+40'(memory_beats)*16;
    descriptors=descriptors+1;active_beats<=int'(memory_beats);active_address<=memory_address;index<=0;
   end
   if(read_valid && read_ready)begin
    if(read_data!==128'(active_address+40'(index*16)) || read_last!==memory_read_last)
     $fatal(1,"Data/chunk last mismatch");
    data_beats=data_beats+1;
   end
   if(memory_read_valid && memory_read_ready)begin
    // Sticky status asserted on the last beat must be seen by retirement.
    if(descriptors==fault_descriptor && memory_read_last)memory_response_error<=1;
    if(memory_read_last)begin active_beats<=0;index<=0;end
    else index<=index+1;
   end
   if(done_valid && active_beats!=0)$fatal(1,"Operation completed before data drained");
  end
  if(cycle>100000)$fatal(1,"watchdog");
 end
 task automatic run(input logic [31:0] offset,input logic [32:0] bytes,
  input int count,input int beats,input logic [1:0] code,input logic [32:0] successful);
  @(negedge clk);descriptors=0;data_beats=0;expected_address=model_base+40'(offset);
  operation_offset=offset;operation_bytes=bytes;operation_valid=1;
  do @(posedge clk);while(!operation_ready);
  @(negedge clk);operation_valid=0;
  while(!done_valid)@(negedge clk);
  repeat(16)begin
   if(done_code!==code || completed_bytes!==successful || descriptors!=count || data_beats!=beats
     || descriptor_valid || operation_ready)$fatal(1,"Whole operation result mismatch");
   @(negedge clk);
  end
  done_ready=1;@(posedge clk);@(negedge clk);done_ready=0;
 endtask
 initial begin
  repeat(3)@(negedge clk);reset=0;
  run(0,65536,17,4096,0,65536);
  run(65520,32,0,0,1,0);
  fault_descriptor=3;run(0,16320,3,765,3,8160);
  if(!poisoned)$fatal(1,"Missing retirement poison after response fault");
  repeat(8)@(negedge clk);
  reset=1;repeat(3)@(negedge clk);reset=0;fault_descriptor=-1;
  run(65520,16,1,1,0,16);
  $display("PASS chunker+retire:4 operations,17-chunk4096-beat transfer, whole-range rejection, last-edge fault/drain/progress, coordinated reset");
  $finish;
 end
endmodule
