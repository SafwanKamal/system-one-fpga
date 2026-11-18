`timescale 1ns/1ps
module signed_int8_dot16_v1_tb;
    parameter integer BITS=7;
    logic clk=0,reset=1,in_valid=0,in_ready,out_valid,out_ready=0;
    logic [127:0] activations=0,weights=0;
    logic signed [19:0] out_sum;
    reg [571:0] vectors[0:4095];
    reg [19:0] held;
    reg [31:0] rng=32'h91a427d3;
    string vector_path;
    integer count,sent=0,received=0,cycles=0,stalls=0,replacements=0;
    reg take_in,take_out,was_stalled;
    signed_int8_dot16_v1 dut(.*);
    always #5 clk=~clk;
    initial begin
        if(!$value$plusargs("vectors=%s",vector_path) || !$value$plusargs("count=%d",count))
            $fatal(1,"missing vectors");
        $readmemh(vector_path,vectors,0,count-1);
        repeat(3) @(negedge clk);reset=0;
        // Fill all five stages, stall, then reset. No packet may survive.
        in_valid=1;activations=vectors[0][571:444];weights=vectors[0][423:296];
        repeat(8) @(negedge clk);
        if(!out_valid || in_ready) $fatal(1,"pipeline stall setup");
        reset=1;in_valid=0;@(negedge clk);
        if(out_valid || in_ready) $fatal(1,"reset flush");reset=0;
        while(received<count) begin
            rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            out_ready=(cycles<64)||rng[0]||rng[4];
            if(!in_valid && sent<count && ((cycles<64)||rng[3])) begin
                in_valid=1;activations=vectors[sent][571:444];weights=vectors[sent][423:296];
            end
            @(posedge clk);
            take_in=in_valid && in_ready;take_out=out_valid && out_ready;
            was_stalled=out_valid && !out_ready;held=out_sum;
            if(take_out) begin
                if(out_sum!==vectors[received][443:424]) $fatal(1,"dot mismatch index=%0d",received);
                received=received+1;
            end
            if(take_in) sent=sent+1;
            if(take_in && take_out) replacements=replacements+1;
            if(was_stalled) stalls=stalls+1;
            #1;if(was_stalled && (!out_valid || out_sum!==held)) $fatal(1,"dot stall instability");
            @(negedge clk);if(take_in) in_valid=0;
            cycles=cycles+1;if(cycles>20000) $fatal(1,"timeout");
        end
        in_valid=0;out_ready=1;@(negedge clk);
        if(out_valid || sent!=count || stalls==0 || replacements<32) $fatal(1,"dot coverage/duplicate");
        $display("PASS bits=%0d pipeline_rows=%0d stalls=%0d simultaneous=%0d",BITS,received,stalls,replacements);
        $finish;
    end
endmodule
