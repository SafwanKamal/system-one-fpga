`timescale 1ns/1ps
module typed200_flush_tb;
    logic clk=0;
    always #5 clk=~clk;
    for(genvar g=0;g<3;g++)begin:latency
        localparam int L=3+g;
        logic reset=1,start=0,ready=0,valid,ref_valid;
        logic [14:0] first=0,address,ref_address;
        logic [15:0] words=0;
        logic [127:0] data,ref_data,pipe[0:L-1];
        int accepted=0,compared=0,aborted=0;
        bit done=0;
        function automatic logic [127:0] pattern(input logic [14:0] a);
            return {32'(a)^32'h19283746,32'(a)*7,32'(a)*3,32'(a)};
        endfunction
        always @(posedge clk)begin
            pipe[0]<=pattern(address);
            for(int i=1;i<L;i++)pipe[i]<=pipe[i-1];
            if(!reset && !start && valid && ready)begin
                assert(data===pattern(first+15'(accepted))) else $fatal(1,"order L%0d",L);
                accepted++;
            end
        end
        result_streamer #(.READ_LATENCY(L)) dut(
            .clk(clk),.reset(reset),.start(start),.first_address(first),.words(words),
            .read_address(address),.read_data(pipe[L-1]),.valid(valid),.ready(ready),.data(data));
        reference_result_streamer #(.READ_LATENCY(L)) reference_inst(
            .clk(clk),.reset(reset),.start(start),.first_address(first),.words(words),
            .read_address(ref_address),.read_data(pipe[L-1]),.valid(ref_valid),.ready(ready),.data(ref_data));
        always @(posedge clk)begin
            #0.001;
            if(!reset && !start)begin
                assert(address==ref_address && valid==ref_valid) else $fatal(1,"cycle/address mismatch L%0d",L);
                if(valid)assert(data===ref_data) else $fatal(1,"data mismatch L%0d",L);
                compared++;
            end
        end
        task launch(input int n,input int a);
            @(negedge clk);first=15'(a);words=16'(n);start=1;ready=0;accepted=0;
            #0.001;assert(!valid) else $fatal(1,"stale valid during START");
            @(negedge clk);start=0;
        endtask
        initial begin
            int lengths[9]='{0,1,2,7,8,9,63,129,1024};
            repeat(4)@(negedge clk);reset=0;
            for(int t=0;t<54;t++)begin
                launch(lengths[t%9],t*79);
                if(t%6==3)begin
                    // Fill and hold unread output, then replace the descriptor.
                    repeat(80)@(negedge clk);
                    if(words!=0)assert(valid) else $fatal(1,"expected stalled output");
                    launch(17,t*79+33);aborted++;
                end
                if(t%6==4)begin
                    // Reset while activation reads and/or buffered data are live.
                    repeat(6)@(negedge clk);reset=1;
                    repeat(3)@(negedge clk);reset=0;aborted++;
                    launch(13,t*79+19);
                end
                for(int c=0;c<20000 && accepted<words;c++)begin
                    ready=c>80 && $urandom_range(0,99)<43;
                    @(negedge clk);
                end
                assert(accepted==words) else $fatal(1,"drain timeout L%0d",L);
                ready=0;repeat(8)@(negedge clk);
                assert(!valid) else $fatal(1,"duplicate result after drain");
            end
            $display("MATCH synchronous flush L%0d: %0d cycles, %0d abort/reset cases",L,compared,aborted);
            done=1;
        end
    end
    // A subcycle clear pulse must not asynchronously reset FIFO pointer state.
    logic fr=1,fc=0,fw=0,rd=0,full,empty;
    logic [7:0] din=8'h71,dout;
    logic [2:0] count;
    bit fifo_done=0;
    stream_fifo_sync_clear #(.WIDTH(8),.DEPTH(4)) fifo(
        .clk(clk),.reset(fr),.clear(fc),.write_enable(fw),.write_data(din),
        .full(full),.read_enable(rd),.read_data(dout),.empty(empty),.count(count));
    initial begin
        repeat(3)@(negedge clk);fr=0;fw=1;
        @(negedge clk);fw=0;
        assert(count==1 && dout==8'h71);
        #1;fc=1;#1;
        assert(count==1 && !empty) else $fatal(1,"clear affected state between clock edges");
        fc=0;
        @(negedge clk);assert(count==1 && dout==8'h71);
        fc=1;fw=1;rd=1;
        @(negedge clk);fc=0;fw=0;rd=0;
        assert(count==0 && empty && !full) else $fatal(1,"sampled clear lost priority");
        fifo_done=1;
    end
    initial begin
        wait(latency[0].done && latency[1].done && latency[2].done && fifo_done);
        $display("PASS synchronous result FIFO: exact streamer cycles/data, stalls, descriptor replacement, reset, subcycle clear");
        $finish;
    end
    initial begin #3000000;$fatal(1,"test timeout");end
endmodule
