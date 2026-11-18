module model_address_window_tb;
    logic clk=0;
    always #5 clk=~clk;
    logic reset=1;
    logic [39:0] model_base;
    logic [32:0] model_bytes,bytes,length;
    logic [31:0] offset;
    logic in_valid=0,out_ready=0,in_ready,out_valid,out_error;
    logic [39:0] address;
    model_address_window dut(.*);
    task automatic check(input logic [39:0] base,
        input logic [32:0] size,input logic [31:0] off,
        input logic [32:0] count,input logic error_expected);
        @(negedge clk);
        model_base=base;model_bytes=size;offset=off;bytes=count;in_valid=1;out_ready=0;
        @(posedge clk);#1;
        if (!out_valid || out_error!==error_expected || length!==count)
            $fatal(1,"Address window status mismatch");
        if (!error_expected && address!==40'(base+off))
            $fatal(1,"High address truncation");
        @(negedge clk);in_valid=0;
        // Vary inputs while stalled: an accepted tuple must not change.
        model_base=0;model_bytes=0;offset=0;bytes=0;
        repeat(3) begin
            @(posedge clk);#1;
            if (!out_valid || out_error!==error_expected || length!==count || in_ready)
                $fatal(1,"Backpressure changed output tuple");
            if (!error_expected && address!==40'(base+off)) $fatal(1,"Address changed while stalled");
        end
        @(negedge clk);out_ready=1;
        @(posedge clk);#1;
        if(out_valid) $fatal(1,"Consumed request remained valid");
    endtask
    initial begin
        repeat(2) @(posedge clk);
        @(negedge clk);reset=0;
        check(40'h800000000,33'h40000000,32'h1230,16,0);
        check(40'h800000000,4096,4080,16,0);
        check(40'h800000000,4096,4080,32,1);
        check(40'h800000000,4096,4096,16,1);
        check(40'h800000000,4096,1,16,1);
        check(40'h800000000,4096,0,15,1);
        check(40'h800000001,4096,0,16,1);
        check(40'h800000000,0,0,16,1);
        check(40'h800000000,33'h100000001,0,16,1);
        check(40'h800000000,4096,0,0,1);
        check(40'hfffffffc00,2048,0,16,1);
        check(40'hfffffffc00,1024,1008,16,0);
        check(40'h800000000,33'h100000000,32'hfffffff0,16,0);
        check(40'h800000000,33'h100000000,32'hfffffff0,32,1);
        // Reset must invalidate a pending transfer.
        @(negedge clk);model_base=40'h800000000;model_bytes=4096;offset=0;bytes=16;in_valid=1;out_ready=0;
        @(posedge clk);#1;if(!out_valid)$fatal(1,"Pending transfer missing");
        @(negedge clk);reset=1;
        @(posedge clk);#1;if(out_valid)$fatal(1,"Reset did not invalidate pending transfer");
        $display("PASS: model address window high DDR, overflow, region limits, stalls and reset");
        $finish;
    end
endmodule
