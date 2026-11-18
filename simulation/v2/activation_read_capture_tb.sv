`timescale 1ns/1ps
module activation_read_capture_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    logic [127:0] data [0:6];
    logic [2:0] select_buffer [0:3];
    logic [127:0] result [0:3];
    logic [127:0] expected [0:3], previous [0:3];
    bit valid_previous = 0;
    activation_read_capture dut (.clk(clk), .physical_data(data),
        .physical_select(select_buffer), .port_data(result));
    initial begin
        for (int i = 0; i < 8192; i++) begin
            @(negedge clk);
            for (int b = 0; b < 7; b++)
                data[b] = {$urandom, $urandom, $urandom, $urandom};
            for (int p = 0; p < 4; p++) begin
                // Cover every selector on every port, collisions, invalid7,
                // and rapid changes with independent randomized RAM outputs.
                select_buffer[p] = 3'((i + p*3) % 8);
                expected[p] = select_buffer[p] < 7 ? data[select_buffer[p]] : '0;
            end
            @(posedge clk); #1;
            for (int p = 0; p < 4; p++) begin
                if (valid_previous && result[p] !== previous[p])
                    $fatal(1, "capture mismatch cycle=%0d port=%0d", i, p);
                previous[p] = expected[p];
            end
            valid_previous = 1;
        end
        @(posedge clk); #1;
        for (int p = 0; p < 4; p++)
            if (result[p] !== previous[p]) $fatal(1, "final capture port=%0d", p);
        $display("PASS: activation read capture 32768 port comparisons");
        $finish;
    end
endmodule
