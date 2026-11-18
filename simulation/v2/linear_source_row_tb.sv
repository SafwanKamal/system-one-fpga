module linear_source_row_tb;
 logic clk=0;always #5 clk=~clk;
 logic reset=1,clear=0,advance=0;
 logic [15:0] row_input=0;
 logic [7:0] tile_input=0,token[0:1];
 logic [13:0] address[0:1];
 int comparisons=0;
 for(genvar i=0;i<2;i++)linear_source_row_probe #(.INCREMENTAL(i))dut(.clk,.reset,.clear,.advance,.row_input,.tile_input,.address(address[i]),.token(token[i]));
 task automatic tick;
  @(posedge clk);@(negedge clk);
  if(!reset)begin
   if(address[0]!==address[1] || token[0]!==token[1])$fatal(1,"Row recurrence mismatch stride%0d token%0d",row_input,token[0]);
   comparisons++;
  end
 endtask
 initial begin
  repeat(2)tick();reset=0;
  for(int row=0;row<65536;row++)begin
   row_input=16'(row);clear=1;advance=0;tick();clear=0;
   for(int t=0;t<256;t++)begin
    advance=1;tile_input=8'((row+t*31)^19);tick();
    if(t==1 || t==127)begin advance=0;tile_input=tile_input+1;tick();end
   end
  end
  for(int i=0;i<10000;i++)begin
   clear=$urandom_range(0,15)==0;advance=$urandom_range(0,2)!=0;
   row_input=16'($urandom);tile_input=8'($urandom);
   reset=i%997==0;tick();reset=0;
  end
  $display("PASS linear source row: %0d comparisons,all65536 strides/256tokens,wrap,bubbles,clear/reset",comparisons);
  $finish;
 end
endmodule
