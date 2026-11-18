`timescale 1ns/1ps
// Nonzero recurrent data against the frozen dual-read engine, including
// non-power-of-two heads and transitions across query groups and heads.
module attention_probability_input_engine_tb;
    logic clk=0,reset=1,start=0;
    always #5 clk=~clk;
    logic [15:0] heads,head_dim;
    logic [7:0] token_count;
    logic signed [16:0] products [0:3][0:15];
    logic signed [23:0] dots [0:3];
    wire [1:0] busy,done,request_valid,read_ready,write_valid;
    wire [26:0] request_address [0:1];
    wire [15:0] request_beats [0:1],enables [0:1];
    wire [13:0] qa [0:1],ka [0:1],va [0:1],out_address [0:1];
    wire [127:0] out_data [0:1];
    integer remaining [0:1];
    integer cycle=0,writes=0,profiles=0;
    wire request_ready=cycle%5!=0;
    wire [1:0] read_valid={remaining[1]>0 && cycle%3!=0,remaining[0]>0 && cycle%3!=0};
    wire [1:0] read_last={remaining[1]==1,remaining[0]==1};
    for(genvar c=0;c<4;c++) assign dots[c]=0;
    logic signed [8:0] old_a[0:3][0:15],new_a[0:3][0:15];
    wire [1:0] mac_issues;
    attention_legacy #(.LANES(4),.READ_LATENCY(5),.MAC_LATENCY(2),.PIPELINED_DOT(1),.LOCAL_QUERY_REGISTERS(1),.LOCAL_ACCUMULATOR_CONTROLS(3),.EXP_TABLE_IN_BRAM(1)) old_engine(
        .clk(clk),.reset(reset),.start(start),.busy(busy[0]),.done(done[0]),.mac_issue(mac_issues[0]),
        .heads(heads),.head_dim(head_dim),.token_count(token_count),
        .softmax_multiplier(17'd1),.softmax_shift(6'd1),.context_multiplier(17'd1),.context_shift(6'd3),.exp_address(27'd0),
        .read_request_valid(request_valid[0]),.read_request_ready(request_ready),.read_request_address(request_address[0]),.read_request_beats(request_beats[0]),
        .read_valid(read_valid[0]),.read_ready(read_ready[0]),.read_data({8{16'hffff}}),.read_last(read_last[0]),
        .q_address(qa[0]),.q_data(128'd0),.k_address(ka[0]),.k_data(128'd0),.v_address(va[0]),.v_data(128'd0),
        .mac_a(old_a),.mac_b(),.mac_product(products),.mac_dot(dots),.destination_write(write_valid[0]),.destination_address(out_address[0]),.destination_data(out_data[0]),.destination_enable(enables[0]));
    attention_engine #(.PROBABILITY_PIPELINE(1),.LANES(4),.READ_LATENCY(5),.MAC_LATENCY(2),.PIPELINED_DOT(1),.LOCAL_QUERY_REGISTERS(1),.LOCAL_ACCUMULATOR_CONTROLS(3),.EXP_TABLE_IN_BRAM(1)) new_engine(
        .clk(clk),.reset(reset),.start(start),.busy(busy[1]),.done(done[1]),.mac_issue(mac_issues[1]),
        .heads(heads),.head_dim(head_dim),.token_count(token_count),
        .softmax_multiplier(17'd1),.softmax_shift(6'd1),.context_multiplier(17'd1),.context_shift(6'd3),.exp_address(27'd0),
        .read_request_valid(request_valid[1]),.read_request_ready(request_ready),.read_request_address(request_address[1]),.read_request_beats(request_beats[1]),
        .read_valid(read_valid[1]),.read_ready(read_ready[1]),.read_data({8{16'hffff}}),.read_last(read_last[1]),
        .q_address(qa[1]),.q_data(128'd0),.k_address(ka[1]),.k_data(128'd0),.v_address(va[1]),.v_data(128'd0),
        .mac_a(new_a),.mac_b(),.mac_product(products),.mac_dot(dots),.destination_write(write_valid[1]),.destination_address(out_address[1]),.destination_data(out_data[1]),.destination_enable(enables[1]));
    always @(negedge clk)
        for(int c=0;c<4;c++) for(int r=0;r<16;r++) products[c][r]=17'(int'($urandom_range(0,62))-31);
    always @(posedge clk) begin
        cycle<=cycle+1;
        for(int engine=0;engine<2;engine++) begin
            if(reset) remaining[engine]<=0;
            else if(request_valid[engine] && request_ready) remaining[engine]<=int'(request_beats[engine]);
            else if(read_valid[engine] && read_ready[engine]) remaining[engine]<=remaining[engine]-1;
        end
        #1;
        if(!reset) begin
            if(busy[0]!==busy[1] || done[0]!==done[1] || request_valid[0]!==request_valid[1] || read_ready[0]!==read_ready[1] || write_valid[0]!==write_valid[1])
                $fatal(1,"Attention control mismatch cycle=%0d",cycle);
            if(qa[0]!==qa[1] || ka[0]!==ka[1] || va[0]!==va[1]) $fatal(1,"Attention input address mismatch");
            if(request_valid[0] && (request_address[0]!==request_address[1] || request_beats[0]!==request_beats[1])) $fatal(1,"Attention DDR descriptor mismatch");
            if(mac_issues[0]!==mac_issues[1])$fatal(1,"MAC issue alignment mismatch");
            if(mac_issues[0])for(int c=0;c<4;c++)for(int r=0;r<16;r++)
                if(old_a[c][r]!==new_a[c][r])$fatal(1,"Probability/query operand alignment mismatch");
            if(write_valid[0]) begin
                writes++;
                if(out_data[0]!==out_data[1] || out_address[0]!==out_address[1] || enables[0]!==enables[1])
                    $fatal(1,"Shared accumulator value/address mismatch cycle=%0d",cycle);
            end
        end
    end
    task automatic run_case(input integer n,h,d);
        integer before_writes,deadline;
        @(negedge clk); token_count=8'(n);heads=16'(h);head_dim=16'(d);
        before_writes=writes;deadline=cycle+2000000;start=1;
        @(negedge clk);start=0;
        while(!done[1]) begin
            @(negedge clk);
            if(cycle>deadline) $fatal(1,"Attention timeout");
        end
        if(writes-before_writes!=h*n*(d/16)) $fatal(1,"Attention output coverage incomplete");
        profiles++;
        $display("PASS shared-read case: tokens=%0d heads=%0d dim=%0d words=%0d",n,h,d,writes-before_writes);
        @(negedge clk);
    endtask
    initial begin
        heads=1;head_dim=16;token_count=1;remaining[0]=0;remaining[1]=0;
        repeat(3) @(negedge clk);reset=0;
        run_case(1,3,48);run_case(2,16,16);run_case(3,64,16);run_case(5,5,48);
        run_case(31,8,64);run_case(33,16,64);run_case(127,8,48);run_case(128,16,64);
        run_case(1,1,16);run_case(12,3,48);
        // Cancel in the weighted phase, then restart with different geometry.
        @(negedge clk);token_count=33;heads=5;head_dim=48;start=1;
        @(negedge clk);start=0;
        wait(new_engine.state_reg==12); // WEIGHTED_SUM
        repeat(12) @(negedge clk);
        reset=1;repeat(2) @(negedge clk);
        if(busy!='0 || write_valid!='0) $fatal(1,"Attention reset cancellation failed");
        reset=0;run_case(3,3,48);
        if(profiles!=11) $fatal(1,"Profile coverage incomplete");
        $display("PASS: probability pipeline frozen equivalence 11 profiles, nonzero recurrent data, stalls, head/group transitions, reset/restart");
        $finish;
    end
endmodule
