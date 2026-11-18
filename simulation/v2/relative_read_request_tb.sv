module relative_read_request_tb #(parameter integer BEATS_WIDTH=16);
    localparam logic [32:0] MAX_BYTES=33'(((64'd1<<BEATS_WIDTH)-1)*16);
    logic clk=0;
    always #5 clk=~clk;
    logic reset=1;
    logic [39:0] model_base=40'h800000000, memory_address;
    logic [32:0] model_bytes=33'h100000000, request_bytes;
    logic [31:0] request_offset;
    logic request_valid=0, request_ready, memory_valid, memory_ready=0;
    logic error_valid, error_ready=0;
    logic [BEATS_WIDTH-1:0] memory_beats;
    logic [1:0] error_code;
    int cases=0;
    relative_read_request #(.BEATS_WIDTH(BEATS_WIDTH)) dut(.*);

    task automatic check(input logic [39:0] base, input logic [32:0] size,
        input logic [31:0] off, input logic [32:0] count, input logic [1:0] expected_error);
        @(negedge clk);
        model_base=base;model_bytes=size;request_offset=off;request_bytes=count;
        request_valid=1;memory_ready=0;error_ready=0;
        if(!request_ready) $fatal(1,"Unexpected descriptor blockage");
        @(posedge clk);#1;
        @(negedge clk);request_valid=0;
        // Accepted model configuration and tuple must survive input changes/stalls.
        model_base=0;model_bytes=0;request_offset=0;request_bytes=0;
        repeat(4) begin
            @(posedge clk);#1;
            if(request_ready || memory_valid !== (expected_error==0) ||
               error_valid !== (expected_error!=0) || error_code!==expected_error)
                $fatal(1,"Descriptor status/valid changed or error reached memory");
            if(expected_error==0 && (memory_address!==40'(base+off) || memory_beats!==BEATS_WIDTH'(count>>4)))
                $fatal(1,"High address or beat count truncated");
        end
        @(negedge clk);memory_ready=1;error_ready=1;
        @(posedge clk);#1;
        if(memory_valid || error_valid) $fatal(1,"Consumed descriptor stayed valid");
        cases++;
    endtask

    initial begin
        repeat(2) @(posedge clk);
        @(negedge clk);reset=0;
        check(40'h800000000,33'h100000000,32'h1230,16,0);
        check(40'h800000000,33'h100000000,4080,8192,8192>MAX_BYTES ? 2 : 0);
        check(40'h800000000,33'h100000000,0,MAX_BYTES,0);
        check(40'h800000000,33'h100000000,0,MAX_BYTES+16,2); // excess beat count must not become zero
        check(40'h800000000,33'h100000000,0,33'h100000000,2);
        check(40'h800000000,33'h100000000,32'hfffffff0,16,0);
        check(40'h800000000,33'h100000000,32'hfffffff0,32,1);
        check(40'h800000000,4096,4080,32,1);
        check(40'h800000000,4096,1,16,1);
        check(40'h800000000,4096,0,15,1);
        check(40'h800000000,4096,0,0,1);
        check(40'h800000001,4096,0,16,1);
        check(40'hfffffffc00,1024,1008,16,0);
        check(40'hfffffffc00,2048,0,16,1);
        // Reset drops a stalled completion; no memory/error handshake in reset.
        @(negedge clk);model_base=40'h800000000;model_bytes=4096;
        request_offset=0;request_bytes=16;request_valid=1;memory_ready=0;error_ready=0;
        @(posedge clk);#1;if(!memory_valid)$fatal(1,"Missing pending request");
        @(negedge clk);reset=1;
        @(posedge clk);#1;
        if(memory_valid || error_valid || request_ready)$fatal(1,"Reset left request live");
        @(negedge clk);request_valid=0;reset=0;
        check(40'h800000000,4096,0,16,0);
        // A consumed tuple and the next descriptor can share a clock, including
        // transitions between the independent memory and error consumers.
        for(int n=0;n<256;n++) begin
            @(negedge clk);
            model_base=40'h800000000+40'(1024*n);model_bytes=33'h100000000;
            request_offset=32'(16*n+(n%3==1 ? 1 : 0));
            request_bytes=n%3==2 ? MAX_BYTES+16 : 33'd16;
            request_valid=1;memory_ready=1;error_ready=1;
            #1;if(!request_ready)$fatal(1,"Back-to-back descriptor stalled");
            @(posedge clk);#1;
            if(error_code!==2'(n%3) || error_valid!==(n%3!=0) || memory_valid!==(n%3==0))
                $fatal(1,"Back-to-back completion misclassified");
            if(n%3==0 && (memory_address!==model_base+40'(request_offset) || memory_beats!==BEATS_WIDTH'(1)))
                $fatal(1,"Back-to-back descriptor address/count changed");
            cases++;
        end
        @(negedge clk);request_valid=0;
        @(posedge clk);#1;
        if(memory_valid || error_valid)$fatal(1,"Final streamed descriptor did not drain");
        $display("PASS relative read descriptor: %0d cases, BEATS_WIDTH=%0d; high addresses, capacity rejection, stalls and reset",cases,BEATS_WIDTH);
        $finish;
    end
endmodule
