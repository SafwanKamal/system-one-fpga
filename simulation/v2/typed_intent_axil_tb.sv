`timescale 1ns/1ps
module typed_intent_axil_tb;
    logic clk=0,reset=1;
    always #5 clk=~clk;
    logic [7:0] s_awaddr=0,s_araddr=0;
    logic s_awvalid=0,s_wvalid=0,s_bready=0,s_arvalid=0,s_rready=0;
    wire s_awready,s_wready,s_bvalid,s_arready,s_rvalid;
    logic [31:0] s_wdata=0;
    logic [3:0] s_wstrb=15;
    wire [1:0] s_bresp,s_rresp;
    wire [31:0] s_rdata;
    logic core_complete=1,core_success=1,live_quiet=1;
    logic [63:0] core_session=64'h12345678,core_request_id=1;
    wire admitted;
    wire [63:0] admitted_session,admitted_request_id;
    localparam logic [255:0] CONTRACT=256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2;
    typed_intent_axil dut(.*);
    int admissions=0,reads=0,writes=0;
    always @(posedge clk) if(!reset && admitted) begin
        admissions++;
        assert(admitted_session==64'h12345678 && admitted_request_id>0);
    end
    task tick; @(posedge clk);#1;@(negedge clk);endtask
    task put(input logic [7:0] a,input logic [31:0] d,
             input logic [3:0] strobe=15,input int order=0,input bit fail=0);
        assert(!s_bvalid);s_awaddr=a;s_wdata=d;s_wstrb=strobe;
        if(order==1) begin
            s_awvalid=1;do tick();while(!dut.aw_full);s_awvalid=0;
            repeat(3)tick();s_wvalid=1;do tick();while(!dut.w_full);s_wvalid=0;
        end else if(order==2) begin
            s_wvalid=1;do tick();while(!dut.w_full);s_wvalid=0;
            repeat(2)tick();s_awvalid=1;do tick();while(!dut.aw_full);s_awvalid=0;
        end else begin
            s_awvalid=1;s_wvalid=1;tick();s_awvalid=0;s_wvalid=0;
        end
        while(!s_bvalid)tick();
        assert(s_bresp==(fail?2:0));
        // Hold response while addresses/data mutate: no duplicate side effect.
        s_awaddr=8'hff;s_wdata=32'hffffffff;
        repeat(3)begin tick();assert(s_bvalid && s_bresp==(fail?2:0));end
        s_bready=1;tick();s_bready=0;writes++;
    endtask
    task get(input logic [7:0] a,output logic [31:0] d,input bit fail=0);
        s_araddr=a;s_arvalid=1;tick();s_arvalid=0;
        assert(s_rvalid && s_rresp==(fail?2:0));d=s_rdata;
        s_araddr=8'hff;
        repeat(4)begin tick();assert(s_rvalid && s_rdata==d && s_rresp==(fail?2:0));end
        s_rready=1;tick();s_rready=0;reads++;
    endtask
    task provision;
        reset=1;tick();reset=0;
        core_complete=1;core_success=1;live_quiet=1;core_session=64'h12345678;core_request_id=1;
        put(8'h08,32'h12345678,15,1);put(8'h0c,0,15,2);put(0,1);
    endtask
    task request_frame(input int id=1,input int budget=500,input bit wrong_profile=0,input bit partial=0);
        if(!partial)put(8'h10,32'(id));put(8'h14,0);put(8'h18,32'(budget));
        for(int i=0;i<8;i++)put(8'(32+4*i),CONTRACT[32*i+:32] ^ ((wrong_profile && i==0)?32'd1:32'd0));
    endtask
    task proposal_frame(input int id=1,input int label=17,input int outcome=1,
                        input bit old_session=0,input int reserved=0);
        put(8'h40,old_session?32'h12345679:32'h12345678);put(8'h44,0);
        put(8'h48,32'(id));put(8'h4c,0);
        for(int i=0;i<8;i++)put(8'(80+4*i),CONTRACT[32*i+:32]);
        put(8'h70,(32'(label)<<16)|32'(outcome));put(8'h74,32'(reserved));
    endtask
    task check_result(input int expected_outcome,input int expected_label,input bit q);
        logic [31:0] d;
        get(4,d);assert(d[2] && !d[1] && d[3]==q);
        get(8'hb0,d);assert(d==((32'(expected_label)<<16)|32'(expected_outcome)));
        get(8'hb4,d);assert(d==0);
    endtask
    logic [31:0] data,age;
    initial begin
        tick();reset=0;put(0,2,15,0,1); // no session/frame
        provision();put(0,1,15,0,1); // locked session
        put(8'hff,0,15,0,1);get(8'hff,data,1);
        put(0,3,15,0,1);put(0,8,15,0,1);
        // Byte strobes accumulate; zero-strobe write must not complete frame.
        request_frame();put(0,2,1,0,1);put(0,2);
        assert(dut.active && admissions==1);
        proposal_frame();put(0,4);
        check_result(1,17,0);get(8'hb8,age);assert(age>0 && age<500);
        repeat(4)begin get(8'hb8,data);assert(data==age);end
        put(0,8);put(0,2,15,0,1); // request shadow must be rewritten
        request_frame(2);core_request_id=2;put(0,2);
        // A proposal frame missing score is rejected; no stale word reuse.
        for(int i=14;i<27;i++)put(8'(8+4*i),0);
        put(0,4,15,0,1);assert(dut.active);
        proposal_frame(2,5);put(0,4);check_result(1,5,0);put(0,8);
        request_frame(2);put(0,2);check_result(6,0,0);put(0,8); // replay
        // Every acceptance precondition must be enforced in hardware.
        for(int mode=0;mode<8;mode++)begin
            provision();request_frame();put(0,2);proposal_frame(1,mode==0?18:4,1,0,mode==1?1:0);
            if(mode==2)core_complete=0;
            if(mode==3)core_success=0;
            if(mode==4)live_quiet=0;
            if(mode==5)core_session++;
            if(mode==6)core_request_id++;
            if(mode==7)put(8'h70,32'h00040009); // reserved tag bits cannot alias ACCEPTED
            put(0,4);check_result(4,0,1);put(0,8,15,0,1);
        end
        // Wrong session cannot complete a current request; PL expires independently.
        provision();request_frame(1,200);put(0,2);proposal_frame(1,4,1,1);put(0,4);
        while(!dut.valid)tick();check_result(5,0,1);
        get(8'hb8,data);assert(data==200);put(0,8,15,0,1);
        // Host read AND write responses can remain blocked across the deadline.
        provision();request_frame(1,16);put(0,2);
        s_araddr=4;s_arvalid=1;tick();s_arvalid=0;data=s_rdata;
        s_awaddr=8'hff;s_wdata=0;s_wstrb=15;s_awvalid=1;s_wvalid=1;
        tick();s_awvalid=0;s_wvalid=0;tick();
        repeat(32)begin
            tick();assert(s_bvalid && s_bresp==2 && s_rvalid && s_rdata==data);
        end
        assert(dut.valid && dut.quarantine && dut.outcome==5 && dut.elapsed==16);
        s_bready=1;s_rready=1;tick();s_bready=0;s_rready=0;
        check_result(5,0,1);
        proposal_frame();put(0,4,15,0,1);check_result(5,0,1);
        // Contract mismatch and zero budget produce canonical INVALID immediately.
        provision();request_frame(1,500,1);put(0,2);check_result(6,0,0);
        put(0,8);request_frame(1);put(0,2);check_result(6,0,0); // INVALID still consumes ID
        provision();request_frame(1,0);put(0,2);check_result(6,0,0);
        // Partial writes require all bytes before control succeeds.
        provision();request_frame(1,500,0,1);
        put(8'h10,32'h00000001,1,1);put(8'h10,0,0,2);put(0,2,15,0,1);
        put(8'h10,0,14,2);put(0,2);assert(dut.active);
        $display("PASS typed intent AXI-Lite: %0d writes, %0d reads, %0d admissions",writes,reads,admissions);
        $finish;
    end
    initial begin #1000000;$fatal(1,"timeout");end
endmodule
