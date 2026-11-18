`timescale 1ns/1ps
// Standalone experimental translator -> frozen AXI port test. No executor/PS mapping.
module relative_retire_axi_tb #(parameter integer REGISTERED_REQUESTS=1);
    logic clk=0,reset=1;
    always #5 clk=~clk;
    logic [39:0] model_base, memory_address;
    logic [32:0] model_bytes,request_bytes;
    logic [31:0] request_offset;
    logic request_valid=0,request_ready,memory_valid,memory_ready;
    logic [15:0] memory_beats;
    logic completion_valid,completion_ready=0;
    logic [1:0] completion_code;
    logic read_valid,read_ready,read_last,response_error;
    logic [127:0] read_data,rdata;
    logic [39:0] araddr;
    logic [7:0] arlen;
    logic [2:0] arsize;
    logic [1:0] arburst,rresp;
    logic arvalid,arready,rvalid,rready,rlast;
    logic hold_bus=0,hold_response=0,active=0,poisoned;
    logic [1:0] inject_fault=0;
    logic port_read_valid,port_read_ready,port_read_last;
    logic [127:0] port_read_data;
    int cycle=0,head=0,tail=0,beat_index=0,received=0;
    int total_beats=0,remaining_ar=0,ar_count=0,cases=0;
    logic [39:0] expected_start,next_ar;
    logic [39:0] queued_address [0:2047];
    int queued_beats [0:2047];
    assign arready=!hold_bus && cycle%5!=0;
    assign read_ready=cycle%7!=0;
    assign rvalid=head<tail && !hold_response;
    assign rdata=128'(queued_address[head]+40'(beat_index*16));
    assign rlast=rvalid && beat_index==queued_beats[head]-1;
    assign rresp=((inject_fault==1 && received==0) ||
        (inject_fault==2 && remaining_ar==0 && head==tail-1 && rlast)) ? 2'd2 : 2'd0;

    relative_read_retire adapter(.clk,.reset,.model_base,.model_bytes,
        .request_valid,.request_ready,.request_offset,.request_bytes,
        .memory_valid,.memory_ready,.memory_address,.memory_beats,
        .memory_read_valid(port_read_valid),.memory_read_ready(port_read_ready),
        .memory_read_data(port_read_data),.memory_read_last(port_read_last),
        .memory_response_error(response_error),.read_valid,.read_ready,.read_data,.read_last,
        .completion_valid,.completion_ready,.completion_code,.poisoned);
    axi_memory_port #(.REGISTERED_REQUESTS(REGISTERED_REQUESTS)) port_inst(
        .clk,.reset,.read_request_valid(memory_valid),.read_request_ready(memory_ready),
        .read_request_address(memory_address),.read_request_beats(memory_beats),
        .read_valid(port_read_valid),.read_ready(port_read_ready),
        .read_data(port_read_data),.read_last(port_read_last),
        .write_request_valid(1'b0),.write_request_ready(),.write_request_address(40'd0),
        .write_request_beats(16'd0),.write_valid(1'b0),.write_ready(),.write_data(128'd0),
        .m_axi_araddr(araddr),.m_axi_arlen(arlen),.m_axi_arsize(arsize),.m_axi_arburst(arburst),
        .m_axi_arvalid(arvalid),.m_axi_arready(arready),.m_axi_rdata(rdata),.m_axi_rresp(rresp),
        .m_axi_rlast(rlast),.m_axi_rvalid(rvalid),.m_axi_rready(rready),
        .m_axi_awaddr(),.m_axi_awlen(),.m_axi_awsize(),.m_axi_awburst(),
        .m_axi_awvalid(),.m_axi_awready(1'b0),.m_axi_wdata(),.m_axi_wstrb(),
        .m_axi_wlast(),.m_axi_wvalid(),.m_axi_wready(1'b0),.m_axi_bresp(2'd0),
        .m_axi_bvalid(1'b0),.m_axi_bready(),.response_error
    );

    always @(posedge clk) begin
        cycle<=cycle+1;
        if(reset) begin
            head<=0;tail<=0;beat_index<=0;received<=0;ar_count<=0;
        end else begin
            if(arvalid && arready) begin
                int expected_count;
                expected_count=remaining_ar;
                if(expected_count>256)expected_count=256;
                if(expected_count>(4096-int'(next_ar[11:0]))/16)
                    expected_count=(4096-int'(next_ar[11:0]))/16;
                if(!active || remaining_ar<=0 || araddr!==next_ar ||
                   int'(arlen)+1!=expected_count || arsize!=4 || arburst!=1)
                    $fatal(1,"Wrong high-DDR/page/burst descriptor address=%h len=%0d",araddr,arlen);
                if(tail>=2048)$fatal(1,"Slave queue overflow");
                queued_address[tail]<=araddr;queued_beats[tail]<=int'(arlen)+1;
                tail<=tail+1;ar_count<=ar_count+1;
                remaining_ar=remaining_ar-expected_count;
                next_ar=next_ar+40'(expected_count*16);
            end
            if(rvalid && rready) begin
                if(rlast)begin head<=head+1;beat_index<=0;end
                else beat_index<=beat_index+1;
            end
            if(read_valid && read_ready) begin
                if(!active || read_data!==128'(expected_start+40'(received*16)) ||
                   read_last!==(received==total_beats-1))
                    $fatal(1,"Descriptor read data/framing mismatch beat=%0d",received);
                received<=received+1;
            end
        end
        if(cycle>400000)$fatal(1,"High-DDR adapter/AXI test timed out");
    end

    task automatic run_request(input logic [39:0] base,input logic [32:0] size,
        input logic [31:0] off,input logic [32:0] count,input logic [1:0] expected_error);
        int before_ar,start_cycle;
        @(negedge clk);
        model_base=base;model_bytes=size;request_offset=off;request_bytes=count;
        expected_start=base+40'(off);next_ar=expected_start;
        total_beats=int'(count>>4);remaining_ar=(expected_error==0 || expected_error==3) ? total_beats : 0;
        received=0;active=expected_error==0 || expected_error==3;before_ar=ar_count;start_cycle=cycle;
        request_valid=1;completion_ready=0;
        do @(posedge clk);while(!request_ready);
        @(negedge clk);request_valid=0;
        model_base=0;model_bytes=0;request_offset=0;request_bytes=0;
        if(expected_error==0 || expected_error==3) begin
            while(received<total_beats)@(negedge clk);
            if(remaining_ar!=0 || head!=tail)$fatal(1,"Descriptor did not fully drain");
            if(response_error!==(inject_fault!=0))$fatal(1,"AXI response error status lost");
        end
        while(!completion_valid)@(negedge clk);
        repeat(6)begin
            if(completion_code!==expected_error || request_ready ||
                ((expected_error==1 || expected_error==2) && (memory_valid || ar_count!=before_ar)))
                $fatal(1,"Completion order/status/AXI rejection mismatch");
            @(negedge clk);
        end
        completion_ready=1;@(posedge clk);@(negedge clk);completion_ready=0;
        active=0;cases++;
    endtask

    initial begin
        int before_ar;
        repeat(3)@(negedge clk);reset=0;
        run_request(40'h800000000,33'h100000000,4080,8192,0);
        run_request(40'h800000000,33'h100000000,4080,1048560,0);
        run_request(40'h800000000,33'h100000000,0,1048576,2);
        run_request(40'h800000000,4096,4080,32,1);
        run_request(40'h800000000,4096,1,16,1);
        run_request(40'h800000000,33'h100000000,32'hfffffff0,16,0);
        run_request(40'h800000000,33'h100000000,32'hfffffff0,32,1);
        run_request(40'hfffffffc00,1024,1008,16,0);
        // A later local error must stay unaccepted until the DDR read retires.
        @(negedge clk);hold_response=1;
        model_base=40'h800000000;model_bytes=4096;request_offset=0;request_bytes=16;
        expected_start=model_base;next_ar=model_base;total_beats=1;remaining_ar=1;
        received=0;active=1;before_ar=ar_count;request_valid=1;
        do @(posedge clk);while(!request_ready);
        @(negedge clk);request_valid=0;
        while(ar_count==before_ar)@(negedge clk);
        request_offset=4080;request_bytes=32;request_valid=1;
        repeat(6)begin
            @(negedge clk);
            if(request_ready || completion_valid || received!=0 || ar_count!=before_ar+1)
                $fatal(1,"Local fault overtook outstanding DDR read");
        end
        hold_response=0;
        while(!completion_valid)@(negedge clk);
        if(received!=1 || completion_code!=0 || head!=tail || remaining_ar!=0)
            $fatal(1,"Outstanding valid read lost");
        completion_ready=1;@(posedge clk);@(negedge clk);completion_ready=0;request_valid=0;
        active=0;cases++;
        run_request(40'h800000000,4096,4080,32,1);
        // Cancel translated/queued work before any slave accepts an AR burst.
        @(negedge clk);hold_bus=1;model_base=40'h800000000;model_bytes=4096;
        request_offset=0;request_bytes=16;request_valid=1;
        do @(posedge clk);while(!request_ready);
        @(negedge clk);request_valid=0;
        repeat(8)@(negedge clk);
        reset=1;active=0;repeat(3)@(negedge clk);reset=0;hold_bus=0;
        repeat(8)begin @(negedge clk);if(arvalid || rvalid || completion_valid)$fatal(1,"Reset leaked a stale descriptor");end
        inject_fault=1;
        run_request(40'h800000000,4096,0,48,3);
        if(!poisoned || request_ready)$fatal(1,"Early RRESP did not poison after drain");
        @(negedge clk);reset=1;repeat(3)@(negedge clk);reset=0;inject_fault=0;
        inject_fault=2;
        run_request(40'h800000000,16384,4080,8224,3);
        if(!poisoned || request_ready)$fatal(1,"Last AXI RRESP did not poison");
        @(negedge clk);reset=1;repeat(3)@(negedge clk);reset=0;inject_fault=0;
        run_request(40'h800000000,4096,0,16,0);
        $display("PASS serialized retirement + AXI: %0d cases, REGISTERED_REQUESTS=%0d; high addresses, max-beat/page splits, ordered completions, reset, early/last RRESP drain/poison",cases,REGISTERED_REQUESTS);
        $finish;
    end
endmodule
