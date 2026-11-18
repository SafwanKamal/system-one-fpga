`timescale 1ns/1ps
// Exercise byte enables, split-bank boundaries, read-first collisions and the
// extra UltraRAM output stage against an independent word-level memory model.
module activation_memory_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    for (genvar g = 0; g < 2; g++) begin : gen_depth
        localparam int DEPTH = g == 0 ? 6144 : 12288;
        localparam int AW = $clog2(DEPTH);
        logic [AW-1:0] ra, wa;
        logic we;
        logic [15:0] be;
        logic [127:0] wd, baseline, pipelined;
        logic [127:0] reference [0:DEPTH-1];
        logic [127:0] expected, previous;
        bit valid_previous = 0;
        bit finished = 0;
        activation_buffer #(.DEPTH(DEPTH)) normal_inst
            (.clk(clk), .read_address(ra), .read_data(baseline),
             .write_enable(we), .write_address(wa), .write_data(wd), .write_byte_enable(be));
        activation_buffer #(.DEPTH(DEPTH), .PIPELINED_URAM(1)) uram_inst
            (.clk(clk), .read_address(ra), .read_data(pipelined),
             .write_enable(we), .write_address(wa), .write_data(wd), .write_byte_enable(be));
        initial begin
            we = 1; be = '1; ra = 0; wa = 0; wd = 0;
            // Initialize every word through the actual byte-write interface.
            for (int a = 0; a < DEPTH; a++) begin
                @(negedge clk); wa = AW'(a); wd = 0;
                @(posedge clk); reference[a] = 0;
            end
            for (int i = 0; i < 30000; i++) begin
                @(negedge clk);
                ra = AW'($urandom_range(DEPTH-1, 0));
                wa = i % 7 == 0 ? ra : AW'($urandom_range(DEPTH-1, 0));
                we = i % 5 != 0;
                be = 16'($urandom);
                wd = {$urandom, $urandom, $urandom, $urandom};
                expected = reference[ra];
                @(posedge clk);
                if (we) for (int b = 0; b < 16; b++)
                    if (be[b]) reference[wa][8*b +: 8] = wd[8*b +: 8];
                #1;
                if (baseline !== expected) $fatal(1, "default depth %0d iteration %0d", DEPTH, i);
                if (valid_previous && pipelined !== previous)
                    $fatal(1, "UltraRAM depth %0d iteration %0d", DEPTH, i);
                previous = expected;
                valid_previous = 1;
            end
            @(negedge clk); we = 0;
            @(posedge clk); #1;
            if (pipelined !== previous) $fatal(1, "UltraRAM final read");
            finished = 1;
        end
    end
    initial begin
        wait (gen_depth[0].finished && gen_depth[1].finished);
        $display("PASS: activation memories, two depths, 60000 masked-write/read checks");
        $finish;
    end
endmodule
