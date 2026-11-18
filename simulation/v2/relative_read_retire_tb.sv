`timescale 1ns/1ps
module relative_read_retire_tb;
    logic clk=0;
    always #5 clk=~clk;
    logic reset=1,request_valid=0,request_ready;
    logic [39:0] model_base=40'h800000000, memory_address;
    logic [32:0] model_bytes=33'h10000, request_bytes=0;
    logic [31:0] request_offset=0;
    logic memory_valid,memory_ready=0,memory_read_valid=0,memory_read_ready;
    logic [7:0] memory_beats;
    logic [127:0] memory_read_data=0,read_data;
    logic memory_read_last=0,memory_response_error=0,read_valid,read_ready=0,read_last;
    logic completion_valid,completion_ready=0,poisoned;
    logic [1:0] completion_code;
    int descriptors=0,completions=0;
    relative_read_retire #(.BEATS_WIDTH(8)) dut (.*);
    always @(posedge clk) begin
        if (!reset && memory_valid && memory_ready) descriptors++;
        if (!reset && completion_valid && completion_ready) completions++;
    end
    task automatic request(input logic [31:0] offset,input logic [32:0] length);
        @(negedge clk); request_offset=offset;request_bytes=length;request_valid=1;
        do @(posedge clk); while (!request_ready);
        @(negedge clk); request_valid=0;
    endtask
    task automatic finish(input logic [1:0] expected);
        int waited=0;
        completion_ready=0;
        while (!completion_valid) begin
            @(negedge clk); waited++;
            if(waited>50) $fatal(1,"completion timeout");
        end
        for(int i=0;i<16;i++) begin
            if(completion_code !== expected || request_ready)
                $fatal(1,"retirement unstable or accepted overlapping request");
            @(negedge clk);
        end
        completion_ready=1;@(posedge clk);@(negedge clk);completion_ready=0;
    endtask
    initial begin
        repeat(4) @(negedge clk);reset=0;
        for(int test_index=0;test_index<32;test_index++) begin
            request(32'(test_index*16),33'd32);
            // Offer a later invalid request while an earlier read is blocked.
            // It must remain unaccepted, unlike the unscheduled raw adapter.
            request_valid=1;request_offset=32'hfffffff0;request_bytes=16;
            repeat(8) begin
                @(negedge clk);
                if(request_ready || completion_valid) $fatal(1,"request/error overtook memory");
            end
            if(!memory_valid || memory_address !== 40'h800000000+40'(test_index*16)
                || memory_beats !== 2) $fatal(1,"descriptor changed under stall");
            memory_ready=1;@(posedge clk);@(negedge clk);memory_ready=0;
            for(int beat=0;beat<2;beat++) begin
                memory_read_valid=1;memory_read_data=128'(test_index*2+beat);memory_read_last=beat==1;
                read_ready=0;
                repeat(7) begin
                    @(negedge clk);
                    if(!read_valid || read_data !== 128'(test_index*2+beat) || completion_valid || request_ready)
                        $fatal(1,"read stalled data/retirement mismatch");
                end
                read_ready=1;@(posedge clk);@(negedge clk);read_ready=0;memory_read_valid=0;
            end
            finish(0); request_valid=0;
            request(32'hfffffff0,33'd16);finish(1);
            request(0,33'd4096);finish(2);
        end
        // An error on the first beat must not retire before draining later data.
        request(0,33'd48);
        wait(memory_valid);@(negedge clk);memory_ready=1;
        @(posedge clk);@(negedge clk);memory_ready=0;
        for(int beat=0;beat<3;beat++) begin
            memory_read_valid=1;memory_read_last=beat==2;memory_read_data=128'(beat+900);
            read_ready=0;
            repeat(5) begin
                @(negedge clk);
                if(completion_valid || !read_valid || request_ready)
                    $fatal(1,"early response fault retired before drain");
            end
            read_ready=1;@(posedge clk);#1;
            if(beat==0) memory_response_error=1;
            @(negedge clk);memory_read_valid=0;read_ready=0;
        end
        finish(3);
        if(!poisoned) $fatal(1,"early error did not poison");
        reset=1;memory_response_error=0;repeat(3) @(negedge clk);reset=0;
        request(0,33'd16);
        wait(memory_valid);@(negedge clk);memory_ready=1;
        @(posedge clk);@(negedge clk);memory_ready=0;
        memory_read_valid=1;memory_read_last=1;read_ready=1;
        // Error status becomes visible only after the last handshake edge.
        @(posedge clk); #1;memory_response_error=1;
        @(negedge clk);memory_read_valid=0;read_ready=0;
        finish(3);
        repeat(8) begin @(negedge clk);if(!poisoned || request_ready) $fatal(1,"fault was not sticky/serialized");end
        reset=1;memory_response_error=0;repeat(3) @(negedge clk);reset=0;
        request(32'hfffffff0,16);finish(1);
        if(descriptors!=34 || completions!=99) $fatal(1,"duplicate/missing descriptor/completion %0d/%0d",descriptors,completions);
        $display("PASS: serialized retirement99requests, stalled data/completions, early/late RRESP drain/poison/reset");
        $finish;
    end
    initial begin repeat(20000) @(posedge clk);$fatal(1,"test watchdog");end
endmodule
