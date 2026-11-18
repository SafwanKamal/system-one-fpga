`timescale 1ns/1ps
module activation_capture_memory_tb;
    localparam int SMALL = 8192;
    localparam int AW = 14;
    logic clk = 0;
    always #5 clk = ~clk;
    logic [AW-1:0] ra [0:6], wa;
    logic [2:0] sel [0:3];
    logic [6:0] we;
    logic [127:0] wd, baseline [0:3], captured [0:3];
    logic [15:0] be;
    logic [127:0] reference [0:6][0:2*SMALL-1];
    logic [AW-1:0] old_address [0:6];
    logic [2:0] s1 [0:3], s2 [0:3], s3 [0:3];
    logic [127:0] m1 [0:6], m2 [0:6], expected [0:3], delayed [0:3];
    activation_capture_probe #(.CAPTURE(0)) old_inst (.clk(clk), .read_address(ra),
        .physical_select(sel), .write_enable(we), .write_address(wa),
        .write_data(wd), .write_byte_enable(be), .port_data(baseline));
    activation_capture_probe #(.CAPTURE(1)) new_inst (.clk(clk), .read_address(ra),
        .physical_select(sel), .write_enable(we), .write_address(wa),
        .write_data(wd), .write_byte_enable(be), .port_data(captured));
    // Independent read-first word model, including address and selector stages.
    always_ff @(posedge clk) begin
        for (int b = 0; b < 7; b++) begin
            old_address[b] <= ra[b];
            m1[b] <= reference[b][old_address[b]];
            m2[b] <= m1[b];
            if (we[b]) for (int byte_index = 0; byte_index < 16; byte_index++)
                if (be[byte_index])
                    reference[b][wa][byte_index*8 +: 8] <= wd[byte_index*8 +: 8];
        end
        for (int p = 0; p < 4; p++) begin
            s1[p] <= sel[p]; s2[p] <= s1[p]; s3[p] <= s2[p];
            expected[p] <= s3[p] < 7 ? m2[s3[p]] : '0;
            delayed[p] <= expected[p];
        end
    end
    initial begin
        we = 0; be = '1; wd = 0; wa = 0;
        for (int b = 0; b < 7; b++) ra[b] = 0;
        for (int p = 0; p < 4; p++) sel[p] = 0;
        // Initialize through the byte-enabled interface, all legal depths.
        for (int a = 0; a < 2*SMALL; a++) begin
            @(negedge clk); wa = AW'(a); wd = {$urandom,$urandom,$urandom,$urandom};
            for (int b = 0; b < 7; b++) we[b] = a < (b >= 5 ? 2*SMALL : SMALL);
        end
        @(negedge clk); we = 0;
        repeat (6) @(posedge clk);
        for (int i = 0; i < 30000; i++) begin
            @(negedge clk);
            for (int b = 0; b < 7; b++) begin
                // Explicit 4K cascade-bank edges as well as randomized traffic.
                ra[b] = AW'(i%4 == 0 ? ((i/4)%4)*4096 : $urandom_range(b>=5 ? 16383 : 8191,0));
                if (b < 5) ra[b] = ra[b] & 14'h1fff;
            end
            for (int p = 0; p < 4; p++) sel[p] = 3'((i + p*3)%8);
            wa = i%7 == 0 ? old_address[i%7] : AW'($urandom_range(8191,0));
            be = i%17 == 0 ? 16'h0 : (i%19 == 0 ? 16'hffff : 16'($urandom));
            wd = {$urandom,$urandom,$urandom,$urandom};
            for (int b = 0; b < 7; b++) we[b] = i%5 != 0 && wa < (b>=5 ? 16384 : 8192);
            @(posedge clk); #1;
            for (int p = 0; p < 4; p++) begin
                if (baseline[p] !== expected[p]) $fatal(1,"baseline reference mismatch cycle=%0d port=%0d",i,p);
                if (captured[p] !== delayed[p]) $fatal(1,"capture reference mismatch cycle=%0d port=%0d",i,p);
            end
        end
        $display("PASS: seven memories, 240000 reference comparisons, masked writes/collisions/cascade boundaries");
        $finish;
    end
endmodule
