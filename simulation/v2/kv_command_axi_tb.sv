`timescale 1ns/1ps
// Experimental logical KV command/context -> retirement -> frozen AXI port.
// Simulated data path only; no deployed executor, PS mapping or hardware integration.
module kv_command_axi_tb #(parameter integer REGISTERED_REQUESTS=1, parameter integer REGISTERED_FIFO_FLAGS=0);
    logic clk=0,reset=1;
    always #5 clk=~clk;
    logic [39:0] model_base, memory_address;
    logic [32:0] model_bytes,request_bytes;
    logic [31:0] request_offset;
    logic request_valid=0,request_ready,memory_valid,memory_ready;
    logic descriptor_valid,descriptor_ready,done_valid,done_ready=0;
    logic [39:0] descriptor_model_base;
    logic [32:0] descriptor_model_bytes,descriptor_bytes,completed_bytes;
    logic [31:0] descriptor_offset;
    logic [1:0] done_code;
    int chunks=0,operation_received=0,fault_chunk=-1;
    logic [39:0] operation_start;
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

    logic [31:0] cache_offset,row_stride,capacity;
    logic value_matrix,done_local_error;
    kv_read_command command(.clk,.reset,.model_base,.window_bytes(model_bytes),
        .in_valid(request_valid),.in_ready(request_ready),
        .cache_offset,.row_stride,.capacity,.layers(16'd1),.layer(16'd0),
        .value_matrix,.first_token(32'd0),.token_count(capacity),
        .descriptor_valid,.descriptor_ready,.descriptor_model_base,.descriptor_model_bytes,
        .descriptor_offset,.descriptor_bytes,.completion_valid,.completion_ready,.completion_code,
        .done_valid,.done_ready,.done_code,.done_local_error,.completed_bytes);
    relative_read_retire adapter(.clk,.reset,.model_base(descriptor_model_base),.model_bytes(descriptor_model_bytes),
        .request_valid(descriptor_valid),.request_ready(descriptor_ready),
        .request_offset(descriptor_offset),.request_bytes(descriptor_bytes),
        .memory_valid,.memory_ready,.memory_address,.memory_beats,
        .memory_read_valid(port_read_valid),.memory_read_ready(port_read_ready),
        .memory_read_data(port_read_data),.memory_read_last(port_read_last),
        .memory_response_error(response_error),.read_valid,.read_ready,.read_data,.read_last,
        .completion_valid,.completion_ready,.completion_code,.poisoned);
    axi_memory_port #(.REGISTERED_REQUESTS(REGISTERED_REQUESTS),.REGISTERED_FIFO_FLAGS(REGISTERED_FIFO_FLAGS)) port_inst(
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
            if(memory_valid && memory_ready) begin
                if(head!=tail || remaining_ar!=0) $fatal(1,"Chunk overtook prior retirement");
                chunks=chunks+1;
                expected_start=memory_address;next_ar=memory_address;
                total_beats=int'(memory_beats);remaining_ar=total_beats;received=0;
                inject_fault=chunks==fault_chunk ? 2 : 0;
                if(memory_address!==operation_start+40'(operation_received*16))
                    $fatal(1,"Whole-operation address discontinuity");
            end
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
                received<=received+1;operation_received=operation_received+1;
            end
        end
        if(cycle>800000)$fatal(1,"High-DDR adapter/AXI test timed out");
    end


    task automatic run_operation(input logic [39:0] base,input logic [32:0] window_size,
        input logic [31:0] offset,input logic [32:0] bytes,input int expected_chunks,
        input int expected_beats,input logic [1:0] error,input logic [32:0] successful);
        int before_ar;
        @(negedge clk);model_base=base;model_bytes=window_size;request_offset=offset;request_bytes=bytes;
        row_stride=16;capacity=32'(bytes>>4);value_matrix=33'(offset)>=bytes;
        cache_offset=value_matrix ? offset-32'(bytes) : offset;
        operation_start=base+40'(offset);chunks=0;operation_received=0;received=0;remaining_ar=0;
        active=1;before_ar=ar_count;request_valid=1;
        do @(posedge clk);while(!request_ready);
        @(negedge clk);request_valid=0;model_base=0;model_bytes=0;request_offset=0;request_bytes=0;cache_offset=1;row_stride=0;capacity=0;value_matrix=0;
        while(!done_valid)@(negedge clk);
        repeat(12)begin
            if(done_code!==error || completed_bytes!==successful || chunks!=expected_chunks
                || operation_received!=expected_beats || request_ready || descriptor_valid
                || remaining_ar!=0 || head!=tail || (expected_chunks==0 && ar_count!=before_ar))
                $fatal(1,"Whole operation/AXI completion mismatch chunks=%0d beats=%0d",chunks,operation_received);
            @(negedge clk);
        end
        done_ready=1;@(posedge clk);@(negedge clk);done_ready=0;active=0;cases++;
    endtask
    initial begin
        repeat(3)@(negedge clk);reset=0;
        run_operation(40'h800000000,33'h100000000,4080,1048576,2,65536,0,1048576);
        run_operation(40'h800000000,4096,4080,32,0,0,1,0);
        run_operation(40'h800000000,33'h100000000,32'hfff00000,1048576,2,65536,0,1048576);
        run_operation(40'hfffffffc00,1024,1008,16,1,1,0,16);
        fault_chunk=2;
        run_operation(40'h800000000,33'h100000000,4080,1048592,2,65537,3,1048560);
        if(!poisoned)$fatal(1,"AXI failure did not poison retirement");
        @(negedge clk);reset=1;repeat(3)@(negedge clk);reset=0;inject_fault=0;fault_chunk=-1;
        run_operation(40'h800000000,4096,0,16,1,1,0,16);
        $display("PASS KV command+retire+AXI: %0d operations REGISTERED_REQUESTS=%0d FIFO_FLAGS=%0d; chunk/page/burst splitting, DDR endpoints, ordered data, fault drain/progress/reset",cases,REGISTERED_REQUESTS,REGISTERED_FIFO_FLAGS);
        $finish;
    end
endmodule
