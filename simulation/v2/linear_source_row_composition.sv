// Focused composition of token/stride/tile registers and the registered buffer
// read address. Mirrors the proposed row recurrence; not a deployed engine.
module linear_source_row_probe #(parameter integer INCREMENTAL=0)(
 input logic clk,reset,clear,advance,
 input logic [15:0] row_input,
 input logic [7:0] tile_input,
 input logic select_linear,
 input logic [13:0] other_address_input,
 output logic [13:0] address,
 output logic [7:0] token);
 logic select_reg;
 logic [13:0] other_address;
 logic [15:0] row;
 logic [7:0] tile;
 logic [13:0] base;
 always_ff @(posedge clk)begin
  if(reset)begin select_reg<=0;other_address<=0;row<=0;tile<=0;token<=0;base<=0;address<=0;end
  else begin
   tile<=tile_input;select_reg<=select_linear;other_address<=other_address_input;
   if(clear)begin row<=row_input;token<=0;base<=0;end
   else if(advance)begin token<=token+1'b1;base<=&token ? 0 : base+14'(row);end
   address<=select_reg ? (INCREMENTAL!=0 ? 14'(base+tile) : 14'(token*row+tile)) : other_address;
  end
 end
endmodule
