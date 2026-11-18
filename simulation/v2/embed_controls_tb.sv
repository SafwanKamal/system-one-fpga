`timescale 1ns/1ps
module embed_controls_tb;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,start=0;logic [5:0] word_shift=0,position_shift=0;
 logic [15:0] width=16;logic [7:0] token_count=1;
 wire [1:0] busy,done,request_valid,read_ready,write_valid;
 wire [26:0] request_address[0:1];wire [15:0] request_beats[0:1],enables[0:1];
 wire [13:0] source_address[0:1],destination_address[0:1];
 wire [127:0] destination_data[0:1],read_data[0:1];
 logic [26:0] address[0:1];int remaining[0:1];int cycle=0,profiles=0,writes=0;
 wire request_ready=cycle%5!=0;
 wire [1:0] read_valid={remaining[1]>0 && cycle%3!=0,remaining[0]>0 && cycle%3!=0};
 wire [1:0] read_last={remaining[1]==1,remaining[0]==1};
 function automatic logic [127:0] word(input logic [26:0] a);
  logic [127:0] result;
  for(int j=0;j<4;j++)begin
   int k;k=(int'(a/4)+j)%8;
   if(a>=27'h1000 && a<27'h2000)case(k)
    0:result[32*j+:32]=32'h80000000;1:result[32*j+:32]=32'h7fffffff;
    2:result[32*j+:32]=32'hffff7fff;3:result[32*j+:32]=32'd32768;
    default:result[32*j+:32]=32'(k*19191-50000);
   endcase
   else if(a<27'h4000)case(k%4)
    0:result[32*j+:32]=0;1:result[32*j+:32]=131071;
    2:result[32*j+:32]=1;3:result[32*j+:32]=65535;
   endcase
   else for(int e=0;e<4;e++)result[32*j+8*e+:8]=8'(int'(a)+j*37+e*83);
  end
  return result;
 endfunction
 for(genvar i=0;i<2;i++)assign read_data[i]=word(address[i]);
 embed_legacy #(.MAX_WIDTH(128),.READ_LATENCY(5)) old_engine(
  .clk,.reset,.start,.busy(busy[0]),.done(done[0]),.word_address(27'h4000),.word_stride(16'd512),
  .position_address(27'h8000),.position_stride(16'd512),.type_address(27'h1000),
  .word_multiplier_address(27'h2000),.position_multiplier_address(27'h3000),.word_shift,.position_shift,
  .width,.token_count,.read_request_valid(request_valid[0]),.read_request_ready(request_ready),
  .read_request_address(request_address[0]),.read_request_beats(request_beats[0]),
  .read_valid(read_valid[0]),.read_ready(read_ready[0]),.read_data(read_data[0]),.read_last(read_last[0]),
  .source_address(source_address[0]),.source_data(128'h00070006000500040003000200010000),
  .destination_write(write_valid[0]),.destination_address(destination_address[0]),
  .destination_data(destination_data[0]),.destination_enable(enables[0]));
 embed_engine #(.MAX_WIDTH(128),.READ_LATENCY(5)) new_engine(
  .clk,.reset,.start,.busy(busy[1]),.done(done[1]),.word_address(27'h4000),.word_stride(16'd512),
  .position_address(27'h8000),.position_stride(16'd512),.type_address(27'h1000),
  .word_multiplier_address(27'h2000),.position_multiplier_address(27'h3000),.word_shift,.position_shift,
  .width,.token_count,.read_request_valid(request_valid[1]),.read_request_ready(request_ready),
  .read_request_address(request_address[1]),.read_request_beats(request_beats[1]),
  .read_valid(read_valid[1]),.read_ready(read_ready[1]),.read_data(read_data[1]),.read_last(read_last[1]),
  .source_address(source_address[1]),.source_data(128'h00070006000500040003000200010000),
  .destination_write(write_valid[1]),.destination_address(destination_address[1]),
  .destination_data(destination_data[1]),.destination_enable(enables[1]));
 always @(posedge clk)begin
  cycle<=cycle+1;
  for(int i=0;i<2;i++)begin
   if(reset)remaining[i]<=0;
   else if(request_valid[i] && request_ready)begin remaining[i]<=int'(request_beats[i]);address[i]<=request_address[i];end
   else if(read_valid[i] && read_ready[i])begin remaining[i]<=remaining[i]-1;address[i]<=address[i]+16;end
  end
  #1;
  if(!reset)begin
   if(busy[0]!==busy[1] || done[0]!==done[1] || request_valid[0]!==request_valid[1] || read_ready[0]!==read_ready[1] || write_valid[0]!==write_valid[1] || source_address[0]!==source_address[1])$fatal(1,"Embed control/tag timing mismatch");
   if(request_valid[0] && (request_address[0]!==request_address[1] || request_beats[0]!==request_beats[1]))$fatal(1,"Embed DDR request mismatch");
   if(write_valid[0])begin
    writes++;
    if(destination_address[0]!==destination_address[1] || enables[0]!==enables[1] || destination_data[0]!==destination_data[1])$fatal(1,"Embed output/mask mismatch ws%0d ps%0d",word_shift,position_shift);
   end
  end
  if(cycle>8000000)$fatal(1,"Embed watchdog");
 end
 task automatic run_case(input int w,p,h,n);
  int before_writes;
  @(negedge clk);word_shift=6'(w);position_shift=6'(p);width=16'(h);token_count=8'(n);before_writes=writes;start=1;
  @(negedge clk);start=0;
  while(!done[1])@(negedge clk);
  if(writes-before_writes!=h*n/2)$fatal(1,"Incomplete embedding write coverage");
  profiles++;@(negedge clk);
 endtask
 initial begin
  remaining[0]=0;remaining[1]=0;repeat(3)@(negedge clk);reset=0;
  for(int w=0;w<64;w++)for(int p=0;p<64;p++)run_case(w,p,(w+p)%3==0 ? 16 : (w+p)%3==1 ? 48 :128,(w+p)%2==0 ? 1:3);
  @(negedge clk);width=128;token_count=3;start=1;@(negedge clk);start=0;
  wait(new_engine.state_reg==10);repeat(3)@(negedge clk);reset=1;repeat(2)@(negedge clk);
  if(busy!=0 || write_valid!=0)$fatal(1,"Embed reset cancellation failed");
  reset=0;run_case(26,63,48,3);
  $display("PASS embed controls: %0d profiles,%0d writes, all64x64 shifts,widths16/48/128,tokens1/3,INT32types,stalls,reset/restart",profiles,writes);$finish;
 end
endmodule
