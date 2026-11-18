`timescale 1ns/1ps
module performance_telemetry_tb;
    logic clk=0, reset=1, clear=0, busy=0;
    always #5 clk=~clk;
    logic arvalid=0, arready=0, rvalid=0, rready=0;
    logic [7:0] arlen=0;
    logic wvalid=0,wready=0,write_request_valid=0,write_request_ready=0;
    logic [15:0] write_request_beats=0;
    logic write_valid=0,write_ready=0;
    logic [3:0] core_events=0;
    wire [31:0] counts[0:9];
    wire pending,snapshot_ready;
    performance_telemetry dut(.*);
    logic [31:0] rd=0,wd=0,ref_counts[0:9],expected[0:9],expected_rd=0,expected_wd=0;
    logic [9:0] events;
    integer checked=0;
    always_comb begin
        events={wd!=0 && write_ready && !write_valid, arvalid && arready,
            wvalid && wready,core_events[0],core_events[1],core_events[3],core_events[2],
            rvalid && !rready,rd!=0 && rready && !rvalid,rvalid && rready};
    end
    // Independent original equations, with only the expected observation delayed.
    always @(posedge clk) begin
        if(reset || clear) begin
            rd<=0;wd<=0;expected_rd<=0;expected_wd<=0;
            for(int c=0;c<10;c++) begin ref_counts[c]<=0;expected[c]<=0;end
        end else begin
            expected_rd<=rd;expected_wd<=wd;
            for(int c=0;c<10;c++) expected[c]<=ref_counts[c];
            if(busy) begin
                rd<=rd+((arvalid && arready)?32'(arlen)+1:0)-((rvalid && rready)?1:0);
                wd<=wd+((write_request_valid && write_request_ready)?32'(write_request_beats):0)
                      -((write_valid && write_ready)?1:0);
                for(int c=0;c<10;c++) if(events[c]) ref_counts[c]<=ref_counts[c]+1;
            end
        end
        #1;
        assert(dut.read_due===expected_rd && dut.write_due===expected_wd)
            else $fatal(1,"Outstanding-beat lag/equivalence mismatch");
        for(int c=0;c<10;c++) assert(counts[c]===expected[c])
            else $fatal(1,"Counter %0d expected %h got %h",c,expected[c],counts[c]);
        if(snapshot_ready) for(int c=0;c<10;c++) assert(counts[c]===ref_counts[c])
            else $fatal(1,"Snapshot not exact");
        checked++;
    end
    task tick;
        @(posedge clk); #2; @(negedge clk);
    endtask
    initial begin
        tick();reset=0;
        // Simultaneous max burst + receive and maximum write burst.
        busy=1;arvalid=1;arready=1;arlen=255;rvalid=1;rready=1;
        write_request_valid=1;write_request_ready=1;write_request_beats=65535;
        write_valid=1;write_ready=1;wvalid=1;wready=1;core_events=15;
        repeat(4) tick();
        busy=0;tick();tick();
        // Seed modulo-2^32 rollover, without adding synthesis-only debug ports.
        rd=32'hffffffff;wd=32'hffffffff;
        dut.read_due=32'hffffffff;dut.write_due=32'hffffffff;
        for(int c=0;c<10;c++) begin ref_counts[c]=32'hffffffff;dut.counts[c]=32'hffffffff;end
        busy=1;arlen=1;write_request_beats=2;
        tick();tick();busy=0;tick();tick();
        clear=1;tick();clear=0;
        for(int i=0;i<12000;i++) begin
            busy=($urandom_range(0,7)!=0);
            clear=($urandom_range(0,199)==0);
            reset=($urandom_range(0,499)==0);
            {arvalid,arready,rvalid,rready,wvalid,wready,write_request_valid,
             write_request_ready,write_valid,write_ready,core_events}=14'($urandom());
            arlen=8'($urandom());write_request_beats=16'($urandom());
            tick();
        end
        reset=0;clear=0;busy=0;tick();tick();
        assert(snapshot_ready && !pending);
        $display("PASS telemetry exact counts, delayed due, drain, restart, modulo rollover: %0d edges",checked);
        $finish;
    end
endmodule
