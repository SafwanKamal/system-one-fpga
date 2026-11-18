// Experimental context controller under configuration changes and ordered
// controlled completions; no AXI data, decoder or deployed executor integration.
module kv_read_command_tb;
    logic clk=0; always #5 clk=~clk;
    logic reset=1,in_valid=0,in_ready,span_valid,span_ready;
    logic [32:0] window_bytes,span_bytes;
    logic [31:0] cache_offset,row_stride,capacity,first_token,token_count,span_offset;
    logic [15:0] layers,layer;
    logic value_matrix;
    logic [1:0] span_error;
    logic [39:0] model_base,held_base,descriptor_model_base;
    logic [32:0] held_bytes,descriptor_model_bytes,descriptor_bytes,completed_bytes;
    logic [31:0] descriptor_offset;
    logic descriptor_valid,descriptor_ready=0,completion_valid=0,completion_ready;
    logic done_valid,done_ready=0,operation_ready;
    logic [1:0] completion_code=0,done_code;
    logic done_local_error;
    kv_read_command dut(.clk,.reset,.in_valid,.in_ready,.model_base,.window_bytes,
        .cache_offset,.row_stride,.capacity,.layers,.layer,.value_matrix,.first_token,.token_count,
        .descriptor_valid,.descriptor_ready,.descriptor_model_base,.descriptor_model_bytes,
        .descriptor_offset,.descriptor_bytes,.completion_valid,.completion_ready,.completion_code,
        .done_valid,.done_ready,.done_code,.done_local_error,.completed_bytes);
    assign span_valid=dut.span_valid;
    assign span_error=dut.span_error;
    assign span_offset=dut.span_offset;
    assign span_bytes=dut.span_bytes;
    int descriptors=0,operations=0;
    task automatic scenario(input int variant, input bit first_operation);
        logic [31:0] expected_offset;
        logic [32:0] expected_bytes,cursor,remaining,successful,issued_bytes;
        logic [1:0] expected_error;
        logic [39:0] expected_base;
        bit pending;
        int issued,cycles,failed_chunk;
        @(negedge clk);in_valid=0;completion_valid=0;descriptor_ready=0;
        if(first_operation) reset=1;
        else begin done_ready=1; repeat(2) @(posedge clk); @(negedge clk); end
        done_ready=0;
        repeat(2)@(posedge clk);
        @(negedge clk);reset=0;
        window_bytes=33'h100000000;cache_offset=0;row_stride=16;capacity=65536;
        layers=1;layer=0;value_matrix=0;first_token=0;token_count=65536;
        expected_offset=0;expected_bytes=1048576;expected_error=0;failed_chunk=0;
        model_base=40'h0800000400;
        case(variant)
            0: begin
                capacity=32'h08000000;value_matrix=1;first_token=capacity-1;token_count=1;
                expected_offset=32'hfffffff0;expected_bytes=16;model_base=40'hff00000000;
            end
            2: begin
                row_stride=256;capacity=8192;layers=4;layer=3;value_matrix=1;token_count=8192;
                expected_offset=14680064;expected_bytes=2097152;
            end
            3: begin layer=1;expected_error=2;end
            4: begin row_stride=65536;capacity=32'hffffffff;layers=65535;expected_error=1;end
            5: failed_chunk=2;
            6: begin capacity=32'h08000000;value_matrix=1;token_count=capacity;expected_offset=32'h80000000;expected_bytes=33'h80000000;end
        endcase
        expected_base=model_base;held_base=model_base;held_bytes=window_bytes;
        in_valid=1;do @(posedge clk);while(!in_ready);
        @(negedge clk);in_valid=0;
        // Alter the caller's configuration; accepted metadata must remain valid.
        window_bytes=16;row_stride=0;layers=0;cache_offset=1;model_base=0;
        do @(posedge clk);while(!span_valid);
        if(span_error!=expected_error)$fatal(1,"Local code variant%0d",variant);
        if(expected_error!=0)begin
            if(span_offset!=0 || span_bytes!=0)$fatal(1,"Errored span not zero");
            repeat(8)begin @(posedge clk);if(descriptor_valid)$fatal(1,"Local fault reached memory");end
            if(!done_valid || !done_local_error || done_code!=expected_error || completed_bytes!=0)
                $fatal(1,"Local fault completion/context mismatch");
        end else begin
            if(span_offset!=expected_offset || span_bytes!=expected_bytes)$fatal(1,"Logical span mismatch");
            cursor={1'b0,expected_offset};remaining=expected_bytes;successful=0;pending=0;issued=0;cycles=0;
            while(!done_valid)begin
                @(negedge clk);
                descriptor_ready=$urandom_range(0,2)!=0;
                completion_valid=pending && $urandom_range(0,3)==0;
                completion_code=failed_chunk!=0 && issued==failed_chunk ? 3 : 0;
                @(posedge clk);
                if(descriptor_valid && descriptor_ready)begin
                    if(pending || descriptor_model_base!=expected_base || descriptor_model_bytes!=held_bytes ||
                       descriptor_offset!=cursor[31:0] || descriptor_bytes!=(remaining>1048560 ? 33'd1048560 : remaining))
                        $fatal(1,"Descriptor mismatch variant%0d chunk%0d",variant,issued);
                    issued_bytes=descriptor_bytes;pending=1;issued++;descriptors++;
                end
                if(completion_valid && completion_ready)begin
                    pending=0;
                    if(completion_code==0)begin successful+=issued_bytes;cursor+=issued_bytes;remaining-=issued_bytes;end
                end
                cycles++;if(cycles>100000)$fatal(1,"Timeout");
            end
            if(done_local_error || done_code!=(failed_chunk!=0 ? 3 : 0) || completed_bytes!=successful ||
                (failed_chunk==0 && successful!=expected_bytes) || (failed_chunk!=0 && issued!=failed_chunk))
                $fatal(1,"Whole operation completion mismatch");
            repeat(5)begin @(posedge clk);if(!done_valid || descriptor_valid || completed_bytes!=successful)$fatal(1,"Completion stall");end
        end
        operations++;
    endtask
    task automatic reset_cancel(input bit after_issue);
        @(negedge clk);done_ready=1;completion_valid=0;descriptor_ready=0;
        repeat(2) @(posedge clk);
        @(negedge clk);done_ready=0;model_base=40'h800000000;
        window_bytes=4096;cache_offset=0;row_stride=16;capacity=2;
        layers=1;layer=0;value_matrix=0;first_token=0;token_count=1;
        in_valid=1;do @(posedge clk);while(!in_ready);
        @(negedge clk);in_valid=0;
        if(after_issue) begin
            do @(posedge clk);while(!descriptor_valid);
            @(negedge clk);descriptor_ready=1;
            @(posedge clk);
            @(negedge clk);descriptor_ready=0;
        end
        reset=1;
        repeat(2) begin
            @(posedge clk);
            if(in_ready || descriptor_valid || completion_ready || done_valid)
                $fatal(1,"Reset exposed cancelled command");
        end
        @(negedge clk);reset=0;completion_valid=1;completion_code=3;
        repeat(8) begin
            @(posedge clk);
            if(!in_ready || descriptor_valid || completion_ready || done_valid)
                $fatal(1,"Cancelled command/late completion leaked after reset");
        end
        @(negedge clk);completion_valid=0;
    endtask
    initial begin
        for(int variant=0;variant<7;variant++)scenario(variant,variant==0);
        reset_cancel(0);
        reset_cancel(1);
        scenario(0,0);
        $display("PASS command reset: before descriptor and after issue cancelled; late completions blocked; new command succeeds");
        $display("PASS KV read command: %0d operations,%0d descriptors,local faults gated,2GiB prefix,40bit endpoint,completion backpressure/fault",operations,descriptors);
        $finish;
    end
endmodule
