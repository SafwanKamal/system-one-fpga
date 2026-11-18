`timescale 1ns/1ps
module packed_weight_fetch16_axi_v1_tb;
    parameter integer BITS=7;
    parameter integer WITH_DOT=0;
    logic clk=0,reset=1,row_valid=0,row_ready,out_valid,out_ready=0,fault;
    logic [39:0] row_address=0,read_request_address;
    logic [127:0] signed_bytes,read_data;
    logic read_request_valid,read_request_ready,read_valid,read_ready,read_last,response_error;
    logic [15:0] read_request_beats;
    logic [39:0] m_axi_araddr;
    logic [7:0] m_axi_arlen;
    logic [2:0] m_axi_arsize;
    logic [1:0] m_axi_arburst;
    logic m_axi_arvalid,m_axi_arready=0,m_axi_rvalid=0,m_axi_rready,m_axi_rlast=0;
    logic [127:0] m_axi_rdata=0;
    logic [1:0] m_axi_rresp=0;
    logic m_axi_awvalid,m_axi_wvalid;
    reg [571:0] vectors[0:4095];
    logic [127:0] activations;
    logic signed [19:0] out_sum;
    reg [19:0] expected_sum,held_sum;
    reg [255:0] memory_bytes;
    reg [127:0] expected,held;
    reg [39:0] base,slave_address;
    integer slave_left=0,count,index,cycles=0,stalls=0,requests=0,beats=0,bursts=0,page_splits=0;
    integer expected_beats,expected_bursts,received=0,offset_bytes;
    reg accepted,done,take_ar,take_r,stalled;
    reg [31:0] rng=32'h6a47d192;
    string vector_path;
    if(WITH_DOT==0) begin: plain
        packed_weight_fetch16_v1 #(.BITS(BITS)) dut(.*);
    end else begin: dot
        packed_weight_fetch_dot16_v1 #(.BITS(BITS)) dut(.*);
    end
    axi_memory_port #(.ADDRESS_WIDTH(40),.DATA_WIDTH(128)) memory_port (
        .clk(clk),.reset(reset),
        .read_request_valid(read_request_valid),.read_request_ready(read_request_ready),
        .read_request_address(read_request_address),.read_request_beats(read_request_beats),
        .read_valid(read_valid),.read_ready(read_ready),.read_data(read_data),.read_last(read_last),
        .write_request_valid(1'b0),.write_request_ready(),.write_request_address(40'b0),
        .write_request_beats(16'b0),.write_valid(1'b0),.write_ready(),.write_data(128'b0),
        .m_axi_araddr(m_axi_araddr),.m_axi_arlen(m_axi_arlen),.m_axi_arsize(m_axi_arsize),
        .m_axi_arburst(m_axi_arburst),.m_axi_arvalid(m_axi_arvalid),.m_axi_arready(m_axi_arready),
        .m_axi_rdata(m_axi_rdata),.m_axi_rresp(m_axi_rresp),.m_axi_rlast(m_axi_rlast),
        .m_axi_rvalid(m_axi_rvalid),.m_axi_rready(m_axi_rready),
        .m_axi_awaddr(),.m_axi_awlen(),.m_axi_awsize(),.m_axi_awburst(),
        .m_axi_awvalid(m_axi_awvalid),.m_axi_awready(1'b0),.m_axi_wdata(),.m_axi_wstrb(),
        .m_axi_wlast(),.m_axi_wvalid(m_axi_wvalid),.m_axi_wready(1'b0),
        .m_axi_bresp(2'b0),.m_axi_bvalid(1'b0),.m_axi_bready(),.response_error(response_error)
    );
    always #5 clk=~clk;
    initial begin
        if(!$value$plusargs("vectors=%s",vector_path) || !$value$plusargs("count=%d",count))
            $fatal(1,"missing vectors");
        $readmemh(vector_path,vectors,0,count-1);
        repeat(3) @(negedge clk);
        reset=0;
        for(index=0;index<count;index=index+1) begin
            row_address=vectors[index][39:0];
            base={row_address[39:4],4'b0};
            memory_bytes=vectors[index][295:40]; expected=vectors[index][423:296];
            expected_sum=vectors[index][443:424];activations=vectors[index][571:444];
            expected_beats=(row_address[3:0]+2*BITS>16)?2:1;
            expected_bursts=(base[11:0]==4080 && expected_beats==2)?2:1;
            if(expected_bursts==2) page_splits=page_splits+1;
            requests=0; beats=0; bursts=0; accepted=0; done=0; row_valid=1;
            while(!done) begin
                rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
                out_ready=rng[4] && rng[8];
                m_axi_arready=(slave_left==0 && !m_axi_rvalid && rng[0]);
                if(slave_left>0 && !m_axi_rvalid && rng[2]) begin
                    offset_bytes=slave_address-base;
                    if(offset_bytes!=0 && offset_bytes!=16) $fatal(1,"read beyond row beat extent");
                    m_axi_rdata=memory_bytes>>(offset_bytes*8);
                    m_axi_rvalid=1; m_axi_rlast=(slave_left==1);
                end
                @(posedge clk);
                if(fault || response_error || m_axi_awvalid || m_axi_wvalid) $fatal(1,"unexpected fault/write");
                if(row_valid && row_ready) accepted=1;
                if(read_request_valid && read_request_ready) begin
                    if(read_request_address!==base || read_request_beats!=expected_beats)
                        $fatal(1,"memory descriptor mismatch index=%0d",index);
                    requests=requests+1;
                end
                take_ar=m_axi_arvalid && m_axi_arready;
                take_r=m_axi_rvalid && m_axi_rready;
                if(take_ar) begin
                    if(m_axi_arsize!=4 || m_axi_arburst!=1 || m_axi_araddr[3:0]!=0 ||
                       m_axi_araddr[11:0]+16*(m_axi_arlen+1)>4096)
                        $fatal(1,"AXI alignment/page rule");
                    if(m_axi_araddr!==base+16*beats) $fatal(1,"AXI address sequence");
                    slave_address=m_axi_araddr; slave_left=m_axi_arlen+1; bursts=bursts+1;
                end
                if(take_r) begin slave_left=slave_left-1; slave_address=slave_address+16; beats=beats+1; end
                stalled=out_valid && !out_ready; held=signed_bytes;
                held_sum=out_sum;
                if(stalled) stalls=stalls+1;
                if(out_valid && out_ready) begin
                    if((WITH_DOT==0 && signed_bytes!==expected) ||
                       (WITH_DOT!=0 && out_sum!==expected_sum) ||
                       requests!=1 || beats!=expected_beats || bursts!=expected_bursts)
                        $fatal(1,"result/count mismatch bits=%0d index=%0d",BITS,index);
                    done=1; received=received+1;
                end
                #1;
                if(stalled && (!out_valid || (WITH_DOT==0 && signed_bytes!==held) ||
                   (WITH_DOT!=0 && out_sum!==held_sum))) $fatal(1,"result stall instability");
                @(negedge clk);
                if(accepted) row_valid=0;
                if(take_r) m_axi_rvalid=0;
                cycles=cycles+1;
                if(cycles>count*150) $fatal(1,"timeout");
            end
        end
        repeat(5) @(negedge clk);
        if(out_valid || stalls==0 || page_splits==0) $fatal(1,"coverage/duplicate");
        $display("PASS bits=%0d dot=%0d rows=%0d stalls=%0d page_splits=%0d cycles=%0d",BITS,WITH_DOT,received,stalls,page_splits,cycles);
        $finish;
    end
endmodule
