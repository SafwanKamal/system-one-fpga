`timescale 1ns/1ps
// Verify both DSP layouts and both latencies over the complete supported domain.
module mac_pipeline_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    logic signed [8:0] a [0:3][0:15];
    logic signed [7:0] b [0:15];
    integer input_a = 0, input_b = 0;
    always_comb begin
        for (int c = 0; c < 4; c++) begin
            for (int r = 0; r < 16; r++) begin
                a[c][r] = 9'(c % 2 == 0 ? input_a : 127 - input_a);
                b[r] = 8'(input_b);
            end
        end
    end
    wire signed [16:0] plain [0:3][0:15], packed_direct [0:3][0:15];
    wire signed [16:0] piped [0:3][0:15], packed_piped [0:3][0:15];
    integer previous [0:3][0:15];
    mac_array #(.LANES(4)) direct_dut (.clk, .a, .b, .product(plain));
    mac_array #(.LANES(4), .PACK(1)) packed_dut (.clk, .a, .b, .product(packed_direct));
    mac_array #(.LANES(4), .INPUT_REGISTERS(1)) pipeline_dut (.clk, .a, .b, .product(piped));
    mac_array #(.LANES(4), .PACK(1), .INPUT_REGISTERS(1)) packed_pipeline_dut
        (.clk, .a, .b, .product(packed_piped));
    initial begin
        for (int av = -128; av <= 255; av++) begin
            for (int bv = -128; bv <= 127; bv++) begin
                @(negedge clk);
                // Include differently signed adjacent lanes in each packed pair.
                input_a = av;
                input_b = bv;
                @(posedge clk); #1;
                for (int c = 0; c < 4; c++) begin
                    for (int r = 0; r < 16; r++) begin
                        if ($signed(plain[c][r]) != $signed(a[c][r]) * $signed(b[r]) ||
                            packed_direct[c][r] !== plain[c][r])
                            $fatal(1, "direct product mismatch a=%0d b=%0d lane=%0d", av, bv, c);
                        if ((av != -128 || bv != -128) &&
                            ($signed(piped[c][r]) != previous[c][r] || packed_piped[c][r] !== piped[c][r]))
                            $fatal(1, "pipeline product/latency mismatch a=%0d b=%0d lane=%0d", av, bv, c);
                        previous[c][r] = $signed(a[c][r]) * $signed(b[r]);
                    end
                end
            end
        end
        $display("PASS: 98,304 operand pairs, mixed adjacent lanes, packed/plain, latencies 1/2");
        $finish;
    end
endmodule
