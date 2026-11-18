module kv_cache_span_tb;
    logic clk=0; always #5 clk=~clk;
    logic reset=1,in_valid,in_ready,out_valid,out_ready;
    logic [32:0] window_bytes,bytes;
    logic [31:0] cache_offset,row_stride,capacity,first_token,token_count,offset;
    logic [15:0] layers,layer;
    logic value_matrix;
    logic [1:0] error_code;
    kv_cache_span dut(.*);
    logic [292:0] vectors[0:11000];
    logic [66:0] unused,held;
    int count,sent=0,received=0,compared=0,cancelled=0,cycles=0;
    bit stalled=0,reset_tested=0;
    initial begin
        int file_id;
        file_id=$fopen("count.txt","r");
        if(!$fscanf(file_id,"%d",count) || count>11001)$fatal(1,"Invalid count");
        $fclose(file_id);
        $readmemh("vectors.hex",vectors,0,count-1);
        in_valid=0;out_ready=0;
        repeat(3)@(posedge clk);
        @(negedge clk);reset=0;
        while(received<count) begin
            @(negedge clk);
            in_valid=sent<count && $urandom_range(0,4)!=0;
            if(sent<count)
                {window_bytes,cache_offset,row_stride,capacity,layers,layer,value_matrix,first_token,token_count,unused}=vectors[sent];
            out_ready=$urandom_range(0,3)==0 || cycles%31==0;
            if(!reset_tested && sent>=1024 && sent>received) begin
                reset=1;in_valid=0;cancelled+=sent-received;received=sent;
                stalled=0;reset_tested=1;
                @(posedge clk);@(negedge clk);reset=0;
            end
            @(posedge clk);
            if(stalled && {offset,bytes,error_code}!==held)$fatal(1,"Stalled metadata changed");
            if(out_valid && out_ready)begin
                if({offset,bytes,error_code}!==vectors[received][66:0])
                    $fatal(1,"KV span mismatch case%0d: got%h expected%h",received,{offset,bytes,error_code},vectors[received][66:0]);
                received++;compared++;
            end
            stalled=out_valid && !out_ready;held={offset,bytes,error_code};
            if(in_valid && in_ready)sent++;
            cycles++;
            if(cycles>200000)$fatal(1,"Timeout");
        end
        if(!reset_tested || cancelled==0 || compared+cancelled!=count)$fatal(1,"Reset proof missing");
        $display("PASS KV span: %0d packets,%0d compared,%0d reset-cancelled; backpressure/config/range/overflow",count,compared,cancelled);
        $finish;
    end
endmodule
