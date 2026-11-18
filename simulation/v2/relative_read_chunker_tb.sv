`timescale 1ns/1ps
module relative_read_chunker_tb #(parameter int BEATS_WIDTH=16);
    localparam logic [32:0] MAX_BYTES=33'(((64'd1<<BEATS_WIDTH)-1)*16);
    logic clk=0;always #5 clk=~clk;
    logic reset=1,operation_valid=0,operation_ready;
    logic [39:0] model_base=40'h800000000,descriptor_model_base;
    logic [32:0] model_bytes=33'h100000000,operation_bytes=0;
    logic [31:0] operation_offset=0,descriptor_offset;
    logic [32:0] descriptor_model_bytes,descriptor_bytes,completed_bytes;
    logic descriptor_valid,descriptor_ready,completion_valid=0,completion_ready;
    logic [1:0] completion_code=0,done_code;
    logic done_valid,done_ready=0;
    int cycle=0,accepted=0,countdown=0,fail_at=-1;
    logic [32:0] expected_cursor,expected_remaining;
    logic [39:0] expected_base;
    logic [32:0] expected_window;
    logic [32:0] held_offset,held_bytes;
    bit held=0;
    assign descriptor_ready=cycle%7!=0 && cycle%7!=1;
    relative_read_chunker #(.BEATS_WIDTH(BEATS_WIDTH)) dut(.*);
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(reset) begin completion_valid<=0;countdown<=0;held<=0;end
        else begin
            if(held && (!descriptor_valid || descriptor_offset!==held_offset[31:0] || descriptor_bytes!==held_bytes))
                $fatal(1,"Descriptor unstable under stall");
            held<=descriptor_valid && !descriptor_ready;
            held_offset<=33'(descriptor_offset);held_bytes<=descriptor_bytes;
            if(descriptor_valid && descriptor_ready)begin
                logic [32:0] expected_size;
                expected_size=expected_remaining>MAX_BYTES ? MAX_BYTES : expected_remaining;
                if(countdown || completion_valid || descriptor_offset!==expected_cursor[31:0]
                    || descriptor_bytes!==expected_size || descriptor_model_base!==expected_base
                    || descriptor_model_bytes!==expected_window)
                    $fatal(1,"Chunk/configuration/order mismatch");
                completion_code<=accepted==fail_at ? 2'd3 : 2'd0;
                accepted=accepted+1;
                expected_cursor=expected_cursor+expected_size;
                expected_remaining=expected_remaining-expected_size;
                countdown<=4;
            end
            if(countdown>0)begin
                countdown<=countdown-1;
                if(countdown==1)completion_valid<=1;
            end
            if(completion_valid && completion_ready)completion_valid<=0;
        end
        if(cycle>200000)$fatal(1,"Chunker watchdog");
    end
    task automatic operation(input logic [39:0] base,input logic [32:0] window_size,
        input logic [31:0] offset,input logic [32:0] bytes,input int expected_chunks,
        input logic [1:0] code,input logic [32:0] successful_bytes,input int fault=-1);
        @(negedge clk);accepted=0;fail_at=fault;
        expected_base=base;expected_window=window_size;
        expected_cursor=33'(offset);expected_remaining=bytes;
        model_base=base;model_bytes=window_size;operation_offset=offset;operation_bytes=bytes;
        operation_valid=1;
        do @(posedge clk);while(!operation_ready);
        @(negedge clk);operation_valid=0;
        // A later reconfiguration must not move any in-progress descriptor.
        model_base=0;model_bytes=0;operation_offset=0;operation_bytes=0;
        while(!done_valid)@(negedge clk);
        repeat(12)begin
            if(done_code!==code || completed_bytes!==successful_bytes || accepted!=expected_chunks
                || operation_ready || descriptor_valid)
                $fatal(1,"Operation completion/progress mismatch accepted=%0d",accepted);
            @(negedge clk);
        end
        done_ready=1;@(posedge clk);@(negedge clk);done_ready=0;
    endtask
    initial begin
        repeat(3)@(negedge clk);reset=0;
        if(BEATS_WIDTH==16)
            operation(40'h800000000,33'h100000000,0,33'h100000000,4097,0,33'h100000000);
        else operation(40'h800000000,65536,0,65536,17,0,65536);
        operation(40'h800000000,33'h100000000,32'hfffffff0,16,1,0,16);
        operation(40'h800000000,8192,4080,8224,0,1,0);
        operation(40'h800000000,8192,1,16,0,1,0);
        operation(40'h800000000,8192,0,0,0,1,0);
        operation(40'hfffffffc00,1024,1008,16,1,0,16);
        operation(40'h800000000,33'h100000000,0,8*MAX_BYTES,3,3,2*MAX_BYTES,2);
        operation(40'h800000000,8192,0,16,1,0,16);
        $display("PASS relative chunker width%0d:8operations, full-window coverage, stable config/stalls, whole-range rejection, mid-operation abort",BEATS_WIDTH);
        $finish;
    end
endmodule
