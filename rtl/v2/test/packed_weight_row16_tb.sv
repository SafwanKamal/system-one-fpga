`timescale 1ns/1ps
module packed_weight_row16_tb;
    parameter integer BITS=7;
    logic clk=0, reset=1, in_valid=0, out_ready=0;
    logic in_ready, out_valid;
    logic [127:0] packed_row=0, signed_bytes;
    reg [255:0] vectors [0:4095];
    reg [127:0] held;
    string vector_path;
    integer count, sent=0, received=0, cycles=0, stalls=0, replacements=0;
    reg [31:0] random_state=32'h491ab32f;
    reg take_in, take_out, was_stalled;
    packed_weight_row16 #(.BITS(BITS)) dut(.*);
    always #5 clk=~clk;
    initial begin
        if (!$value$plusargs("vectors=%s", vector_path) ||
            !$value$plusargs("count=%d", count)) $fatal(1,"missing vectors/count");
        if (count<1 || count>4096) $fatal(1,"vector count");
        $readmemh(vector_path, vectors, 0, count-1);
        repeat(3) @(negedge clk);
        // Reset must discard a pending row and block acceptance while asserted.
        if (in_ready) $fatal(1,"ready during reset");
        reset=0; in_valid=1; packed_row=vectors[0][127:0];
        @(negedge clk); in_valid=0;
        if (!out_valid || signed_bytes!==vectors[0][255:128]) $fatal(1,"first row");
        held=signed_bytes;
        repeat(3) begin
            @(negedge clk);
            if (!out_valid || signed_bytes!==held || in_ready) $fatal(1,"held row");
        end
        reset=1;
        @(negedge clk);
        if (out_valid || in_ready) $fatal(1,"reset did not flush");
        reset=0;
        while (received<count) begin
            // Long initial full-rate segment followed by randomized backpressure
            // and input bubbles. A pending source row is held until acceptance.
            random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
            out_ready=(cycles<64) || random_state[0] || random_state[3];
            if (!in_valid && sent<count && ((cycles<64) || random_state[5])) begin
                in_valid=1; packed_row=vectors[sent][127:0];
            end
            @(posedge clk);
            take_in=in_valid && in_ready; take_out=out_valid && out_ready;
            was_stalled=out_valid && !out_ready; held=signed_bytes;
            if (take_out) begin
                if (signed_bytes!==vectors[received][255:128])
                    $fatal(1,"row mismatch width=%0d index=%0d",BITS,received);
                received=received+1;
            end
            if (take_in) sent=sent+1;
            if (take_in && take_out) replacements=replacements+1;
            if (was_stalled) stalls=stalls+1;
            #1;
            if (was_stalled && (!out_valid || signed_bytes!==held)) $fatal(1,"stall instability");
            @(negedge clk);
            if (take_in) in_valid=0;
            cycles=cycles+1;
            if (cycles>20000) $fatal(1,"timeout");
        end
        if (sent!=count || stalls==0 || replacements<32) $fatal(1,"coverage/count");
        out_ready=1; in_valid=0;
        @(negedge clk);
        if (out_valid) $fatal(1,"duplicate trailing row");
        $display("PASS bits=%0d rows=%0d stalls=%0d replacements=%0d cycles=%0d",BITS,count,stalls,replacements,cycles);
        $finish;
    end
endmodule
