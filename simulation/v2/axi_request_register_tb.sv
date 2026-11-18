`timescale 1ns/1ps
module axi_request_register_tb;
    logic clk=0,reset=1;
    always #5 clk=~clk;
    logic rv=0,rr,wv=0,wr,read_valid,read_ready,read_last,write_ready;
    logic [39:0] ra,wa,araddr,awaddr;
    logic [7:0] arlen,awlen;
    logic [2:0] arsize,awsize;
    logic [1:0] arburst,awburst;
    logic arvalid,arready,awvalid,awready,rready,wvalid,wready,wlast,bready,error;
    logic [127:0] read_data,wdata;
    logic [15:0] wstrb;
    integer cycle=0,release_bus=100000;
    integer accepted_r=0,accepted_w=0,ars=0,aws=0,ws=0,rs=0,bs=0;
    integer pending_r=0,pending_b=0,read_stalls=0,write_stalls=0;
    logic bus_rvalid,bus_bvalid;
    localparam logic [39:0] RBASE=40'h800000ff0,WBASE=40'h800010ff0;
    assign arready=cycle>=release_bus && cycle%5!=0;
    assign awready=cycle>=release_bus && cycle%6!=0;
    assign wready=cycle%3!=0;
    assign read_ready=cycle>=release_bus+60 && cycle%7!=0;
    assign bus_rvalid=pending_r>0 && cycle%3!=0;
    assign bus_bvalid=pending_b>0 && cycle%4!=0;
    axi_memory_port #(.REGISTERED_REQUESTS(1)) dut(
        .clk(clk),.reset(reset),.read_request_valid(rv),.read_request_ready(rr),
        .read_request_address(ra),.read_request_beats(16'd1),
        .read_valid(read_valid),.read_ready(read_ready),.read_data(read_data),.read_last(read_last),
        .write_request_valid(wv),.write_request_ready(wr),.write_request_address(wa),.write_request_beats(16'd1),
        .write_valid(1'b1),.write_ready(write_ready),.write_data(128'h1234),
        .m_axi_araddr(araddr),.m_axi_arlen(arlen),.m_axi_arsize(arsize),.m_axi_arburst(arburst),
        .m_axi_arvalid(arvalid),.m_axi_arready(arready),.m_axi_rdata(128'h5678),
        .m_axi_rresp(2'd0),.m_axi_rlast(1'b1),.m_axi_rvalid(bus_rvalid),.m_axi_rready(rready),
        .m_axi_awaddr(awaddr),.m_axi_awlen(awlen),.m_axi_awsize(awsize),.m_axi_awburst(awburst),
        .m_axi_awvalid(awvalid),.m_axi_awready(awready),.m_axi_wdata(wdata),.m_axi_wstrb(wstrb),
        .m_axi_wlast(wlast),.m_axi_wvalid(wvalid),.m_axi_wready(wready),
        .m_axi_bresp(2'd0),.m_axi_bvalid(bus_bvalid),.m_axi_bready(bready),.response_error(error)
    );
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(reset) begin
            accepted_r<=0;accepted_w<=0;ars<=0;aws<=0;ws<=0;rs<=0;bs<=0;
            pending_r<=0;pending_b<=0;read_stalls<=0;write_stalls<=0;
        end else begin
            if(rv && rr) accepted_r<=accepted_r+1;
            if(wv && wr) accepted_w<=accepted_w+1;
            if(rv && !rr) read_stalls<=read_stalls+1;
            if(wv && !wr) write_stalls<=write_stalls+1;
            pending_r<=pending_r+int'(arvalid && arready)-int'(bus_rvalid && rready);
            pending_b<=pending_b+int'(wvalid && wready)-int'(bus_bvalid && bready);
            if(arvalid && arready) begin
                if(araddr!=RBASE+40'(ars*16) || arlen!=0 || arsize!=4 || arburst!=1)
                    $fatal(1,"Read descriptor lost, duplicated or reordered");
                ars<=ars+1;
            end
            if(awvalid && awready) begin
                if(awaddr!=WBASE+40'(aws*16) || awlen!=0 || awsize!=4 || awburst!=1)
                    $fatal(1,"Write descriptor lost, duplicated or reordered");
                aws<=aws+1;
            end
            if(wvalid && wready) begin
                if(!wlast || wdata!=128'h1234 || wstrb!=16'hffff) $fatal(1,"Write stream corrupted");
                ws<=ws+1;
            end
            if(read_valid && read_ready) begin
                if(!read_last || read_data!=128'h5678) $fatal(1,"Read framing corrupted");
                rs<=rs+1;
            end
            if(bus_bvalid && bready) bs<=bs+1;
            if(error) $fatal(1,"Unexpected AXI response error");
        end
    end
    initial begin
        ra=RBASE;wa=WBASE;
        repeat(3) @(negedge clk);reset=0;
        // Source-valid changes cannot combinationally change write admission.
        #1;rv=1;#1;if(!wr || !rr) $fatal(1,"Request valid still drives upstream readiness");
        wv=1;@(negedge clk);rv=0;wv=0;
        repeat(3) @(negedge clk);
        if(wr) $fatal(1,"Full pending write descriptor did not backpressure");
        // Cancel queued work before any bus acceptance, then check no stale work.
        reset=1;repeat(2) @(negedge clk);reset=0;
        repeat(3) @(negedge clk);
        if(arvalid || awvalid) $fatal(1,"Reset left a stale request");
        release_bus=cycle+12;
        while(rs<32 || bs<32) begin
            rv=accepted_r<32;wv=accepted_w<32;
            ra=RBASE+40'(accepted_r*16);wa=WBASE+40'(accepted_w*16);
            @(negedge clk);
            if(cycle>10000) $fatal(1,"Simultaneous traffic deadlocked");
        end
        rv=0;wv=0;
        repeat(3) @(negedge clk);
        if(accepted_r!=32 || accepted_w!=32 || ars!=32 || aws!=32 || ws!=32 || rs!=32 || bs!=32)
            $fatal(1,"Request or response count mismatch");
        if(!read_stalls || !write_stalls) $fatal(1,"Backpressure coverage missing");
        $display("PASS: simultaneous32reads/32writes, descriptor replacement/backpressure, high addresses, reset cancellation, ordered framing and no combinational valid-to-ready dependency");
        $finish;
    end
endmodule
