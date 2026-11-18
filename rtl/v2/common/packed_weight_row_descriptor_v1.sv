// Candidate descriptor contract, separate from deployed firmware/image ABIs.
// Python PackedWeights layout: tiles [ceil(rows/32),ceil(columns/16),32,16].
// Region includes any alignment padding actually read by 128-bit DDR beats.
// All sizes are bytes. Region extent may be exactly 2^40 only at base zero.
// A registered result (including rejection) remains stable under backpressure.
// Error precedence:1 zero dimensions,2 row index,3 input tile,4 address overflow,
// 5 complete serialized matrix outside region,6 aligned fetch outside region.
module packed_weight_row_descriptor_v1 #(
    parameter integer BITS=7
) (
    input logic clk,reset,in_valid,
    output logic in_ready,
    input logic [39:0] matrix_base,region_base,
    input logic [40:0] region_bytes,
    input logic [31:0] rows,columns,row_index,input_tile,
    output logic out_valid,
    input logic out_ready,
    output logic [39:0] row_address,
    output logic [3:0] out_error
);
    logic [65:0] output_tiles,input_tiles,matrix_bytes,offset,physical;
    logic [65:0] region_end,matrix_end,beat_start,beat_end;
    logic [3:0] error_next;
    always_comb begin
        // 66 bits cover worst-case products of two 32-bit dimensions plus
        // tile scaling. Invalid huge descriptors cannot wrap into valid ones.
        output_tiles=(66'(rows)+31)>>5;
        input_tiles=(66'(columns)+15)>>4;
        matrix_bytes=output_tiles*input_tiles*(64*BITS);
        offset=(((66'(row_index)>>5)*input_tiles)+66'(input_tile))*(64*BITS)
               +(66'(row_index[4:0])*(2*BITS));
        physical=66'(matrix_base)+offset;
        region_end=66'(region_base)+66'(region_bytes);
        matrix_end=66'(matrix_base)+matrix_bytes;
        beat_start=(physical>>4)<<4;
        beat_end=((physical+(2*BITS)+15)>>4)<<4;
        error_next=0;
        if(rows==0 || columns==0) error_next=1;
        else if(row_index>=rows) error_next=2;
        else if(66'(input_tile)>=input_tiles) error_next=3;
        else if(region_bytes==0 || region_end>66'h10000000000 ||
                matrix_end>66'h10000000000 || physical>=66'h10000000000 ||
                physical+(2*BITS)>66'h10000000000) error_next=4;
        else if(matrix_base<region_base || matrix_end>region_end) error_next=5;
        else if(beat_start<66'(region_base) || beat_end>region_end) error_next=6;
    end
    assign in_ready=!reset && (!out_valid || out_ready);
    always_ff @(posedge clk) begin
        if(reset) begin out_valid<=0;row_address<=0;out_error<=0;end
        else if(in_ready) begin
            out_valid<=in_valid;
            if(in_valid) begin row_address<=physical[39:0];out_error<=error_next;end
        end
    end
`ifndef SYNTHESIS
    initial if(BITS!=6 && BITS!=7 && BITS!=8) $fatal(1,"unsupported BITS");
`endif
endmodule
