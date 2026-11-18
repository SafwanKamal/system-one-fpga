`timescale 1ns/1ps
module attention_address_cursor_tb;
    logic clk=0,reset=1,start=0,busy,done;
    always #5 clk=~clk;
    logic [15:0] heads,head_dim;
    logic [7:0] token_count;
    logic request_valid,request_ready,read_valid,read_ready,read_last;
    logic [26:0] request_address;
    logic [15:0] request_beats;
    logic [13:0] q_address,k_address,v_address,destination_address;
    logic destination_write;
    logic [127:0] destination_data;
    logic [15:0] destination_enable;
    logic signed [16:0] products[0:3][0:15];
    logic signed [23:0] dots[0:3];
    integer remaining=0,cycle=0,q_reads=0,k_reads=0,v_reads=0,writes=0;
    assign request_ready=cycle%5!=0;
    assign read_valid=remaining>0 && cycle%3!=0;
    assign read_last=remaining==1;
    for(genvar c=0;c<4;c++) begin
        assign dots[c]='0;
        for(genvar r=0;r<16;r++) assign products[c][r]='0;
    end
    attention_engine #(.LANES(4),.PIPELINED_DOT(1)) dut(
        .clk(clk),.reset(reset),.start(start),.busy(busy),.done(done),.mac_issue(),
        .heads(heads),.head_dim(head_dim),.token_count(token_count),
        .softmax_multiplier(17'd1),.softmax_shift(6'd1),
        .context_multiplier(17'd1),.context_shift(6'd1),.exp_address(27'd0),
        .read_request_valid(request_valid),.read_request_ready(request_ready),
        .read_request_address(request_address),.read_request_beats(request_beats),
        .read_valid(read_valid),.read_ready(read_ready),.read_data({8{16'hffff}}),.read_last(read_last),
        .q_address(q_address),.q_data(128'd0),.k_address(k_address),.k_data(128'd0),
        .v_address(v_address),.v_data(128'd0),.mac_a(),.mac_b(),.mac_product(products),.mac_dot(dots),
        .destination_write(destination_write),.destination_address(destination_address),
        .destination_data(destination_data),.destination_enable(destination_enable)
    );
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(reset) remaining<=0;
        else begin
            if(request_valid && request_ready) remaining<=int'(request_beats);
            else if(read_valid && read_ready) remaining<=remaining-1;
            if(dut.issue_q) q_reads<=q_reads+1;
            if(dut.issue_k) k_reads<=k_reads+1;
            if(dut.issue_v) v_reads<=v_reads+1;
            if(destination_write) begin
                writes<=writes+1;
                if(destination_data!='0 || destination_enable!=16'hffff)
                    $fatal(1,"Zero-input output corrupted");
                if(int'(destination_address)>=int'(heads)*int'(token_count)*(int'(head_dim)/16))
                    $fatal(1,"Context output address exceeds active tensor");
            end
        end
    end
    task automatic run_case(input integer n,h,d);
        integer started,qr,kr,vr,wr;
        wait(!busy); @(negedge clk);
        qr=q_reads;kr=k_reads;vr=v_reads;wr=writes;
        heads=16'(h);head_dim=16'(d);token_count=8'(n);start=1;
        @(negedge clk);start=0;started=cycle;
        while(!done) begin
            @(negedge clk);
            if(cycle-started>2000000) $fatal(1,"Attention cursor test timed out");
        end
        if(q_reads-qr!=h*n*(d/16) || writes-wr!=h*n*(d/16)
           || k_reads-kr!=h*((n+3)/4)*n*(d/16) || v_reads-vr!=k_reads-kr)
            $fatal(1,"Missing/repeated tensor addresses n=%0d heads=%0d dim=%0d",n,h,d);
        $display("PASS cursor case: tokens=%0d heads=%0d dim=%0d Q=%0d K=%0d V=%0d out=%0d",n,h,d,q_reads-qr,k_reads-kr,v_reads-vr,writes-wr);
        @(negedge clk);
    endtask
    initial begin
        heads=1;head_dim=16;token_count=1;
        repeat(3) @(negedge clk);reset=0;
        run_case(1,3,48);run_case(2,16,16);run_case(3,64,16);
        run_case(5,5,48);run_case(31,8,64);run_case(33,16,64);
        run_case(127,8,48);run_case(128,16,64);
        // Repeat smaller dimensions after larger tensors without a reset.
        run_case(1,1,16);run_case(12,3,48);
        $display("PASS: ten attention cursor profiles; exact per-cycle address assertions enabled");
        $finish;
    end
endmodule
