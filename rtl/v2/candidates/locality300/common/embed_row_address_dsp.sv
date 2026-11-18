// Private ID_WAIT input capture -> ROW_ADDRESS result, exact modular addressing.
// No public parameter or hardware qualification is implied by this prototype.
(* use_dsp="yes" *)
module embed_row_address_dsp #(parameter integer ADDRESS_WIDTH=32)(
    input logic clk,reset,input_capture,output_capture,
    input logic [15:0] id,stride,
    input logic [ADDRESS_WIDTH-1:0] base,
    output logic [ADDRESS_WIDTH-1:0] address);
    logic signed [16:0] id_reg,stride_reg;
    logic signed [47:0] base_reg;
    always_ff @(posedge clk) begin
        if(reset) begin id_reg<=0;stride_reg<=0;base_reg<=0;address<=0;end
        else begin
            if(input_capture) begin
                id_reg<=$signed({1'b0,id});stride_reg<=$signed({1'b0,stride});
                base_reg<=48'({1'b0,base});
            end
            if(output_capture) address<=ADDRESS_WIDTH'(id_reg*stride_reg+base_reg);
        end
    end
endmodule
