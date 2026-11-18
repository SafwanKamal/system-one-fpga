// Isolated inference composition of LINEAR's two128x1024 synchronous banks.
// Registered controls/data represent the existing upstream pipeline. This is
// resource/read-mode evidence only, not whole-engine timing or closure.
module linear_accumulator_probe #(parameter integer USE_BRAM=0)(
 input logic clk,
 input logic [6:0] read_address0,read_address1,write_address,
 input logic write_valid,write_bank,
 input logic [1023:0] write_data,
 output logic [1023:0] read_data0,read_data1);
 logic [6:0] ra[0:1],wa;
 logic wv,wb;
 logic [1023:0] wd,rd[0:1];
 always_ff @(posedge clk)begin
  ra[0]<=read_address0;ra[1]<=read_address1;wa<=write_address;
  wv<=write_valid;wb<=write_bank;wd<=write_data;
 end
 assign read_data0=rd[0];assign read_data1=rd[1];
 for(genvar bank=0;bank<2;bank++)begin : gen_bank
  if(USE_BRAM!=0)begin : gen_block
   (* ram_style="block" *) logic [1023:0] memory[0:127];
   always_ff @(posedge clk)begin
    rd[bank]<=memory[ra[bank]];
    if(wv && wb==1'(bank))memory[wa]<=wd;
   end
  end else begin : gen_lut
   (* ram_style="distributed" *) logic [1023:0] memory[0:127];
   always_ff @(posedge clk)begin
    rd[bank]<=memory[ra[bank]];
    if(wv && wb==1'(bank))memory[wa]<=wd;
   end
  end
 end
endmodule
