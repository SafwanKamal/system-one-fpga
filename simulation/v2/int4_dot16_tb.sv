`timescale 1ns/1ps
module int4_dot16_tb;
    logic clk=0,reset=1;
    always #5 clk=~clk;
    logic in_valid=0,in_ready,out_valid,out_ready;
    logic [127:0] activations;
    logic [63:0] packed_weights;
    logic signed [15:0] out_sum;
    logic hold_output=1,held=0;
    logic signed [15:0] held_sum;
    logic [207:0] vectors [0:8191];
    logic signed [15:0] expected [0:8191];
    int cycle=0,head=0,tail=0,count=0,in_stalls=0,out_stalls=0;
    int accept_run=0,max_accept_run=0;
    logic signed [15:0] offered_sum;
    string vector_file;
    assign out_ready=!hold_output && cycle%7!=0 && cycle%11!=0;
    int4_dot16 dut(.*);
    always @(posedge clk)begin
        cycle<=cycle+1;
        if(reset)begin head<=0;tail<=0;held<=0;in_stalls<=0;out_stalls<=0;accept_run<=0;max_accept_run<=0;end
        else begin
            if(held && (!out_valid || out_sum!==held_sum))$fatal(1,"Stalled dot result changed");
            held<=out_valid && !out_ready;held_sum<=out_sum;
            if(in_valid && in_ready)begin
                expected[tail]<=offered_sum;tail<=tail+1;accept_run<=accept_run+1;
                if(accept_run+1>max_accept_run)max_accept_run<=accept_run+1;
            end else accept_run<=0;
            if(in_valid && !in_ready)in_stalls<=in_stalls+1;
            if(out_valid && !out_ready)out_stalls<=out_stalls+1;
            if(out_valid && out_ready)begin
                if(head>=tail || out_sum!==expected[head])$fatal(1,"Dot mismatch/order loss at %0d: got %0d expected %0d",head,out_sum,expected[head]);
                head<=head+1;
            end
        end
        if(cycle>100000)$fatal(1,"INT4 dot stream timed out");
    end
    task automatic send(input int index);
        {offered_sum,activations,packed_weights}=vectors[index];in_valid=1;
        do @(posedge clk);while(!in_ready);
        @(negedge clk);in_valid=0;
    endtask
    initial begin
        if(!$value$plusargs("VECTORS=%s",vector_file) || !$value$plusargs("COUNT=%d",count))
            $fatal(1,"Independent vector path and count required");
        $readmemh(vector_file,vectors);
        if(count!=6145 || vectors[0][207:192]!=16'd3)$fatal(1,"Wrong vector contract");
        repeat(3)@(negedge clk);reset=0;
        send(0);send(1);send(2);
        repeat(8)@(negedge clk);
        if(!out_valid)$fatal(1,"Missing stalled pre-reset result");
        reset=1;repeat(3)@(negedge clk);reset=0;hold_output=0;
        if(out_valid)$fatal(1,"Reset left a stale result");
        for(int n=0;n<count;n++)begin
            send(n);
            if(n%17==0)repeat(2)@(negedge clk);
        end
        while(head<count)@(negedge clk);
        repeat(8)@(negedge clk);
        if(head!=count || tail!=count || out_valid || !in_stalls || !out_stalls || max_accept_run<5)
            $fatal(1,"Incomplete stream/stall coverage");
        $display("PASS INT4 dot16: %0d independent vectors, max consecutive accepts %0d, packed nibble order, signed growth, stalls and reset cancellation",count,max_accept_run);
        $finish;
    end
endmodule
