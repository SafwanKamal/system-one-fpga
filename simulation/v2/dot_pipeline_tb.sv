module dot_pipeline_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    logic signed [16:0] product [0:1][0:15];
    wire signed [23:0] wide [0:1];
    wire signed [18:0] narrow [0:1];
    dot16_pipeline #(.LANES(2), .WIDTH(24)) a(.clk(clk), .product(product), .sum(wide));
    dot16_pipeline #(.LANES(2), .WIDTH(19)) b(.clk(clk), .product(product), .sum(narrow));
    integer expected [0:1][0:3];
    initial begin
        for (int c=0;c<2;c++) for (int p=0;p<4;p++) expected[c][p]=0;
        for (int cycle=0;cycle<512;cycle++) begin
            @(negedge clk);
            for (int c=0;c<2;c++) for (int r=0;r<16;r++) begin
                if (cycle<16) product[c][r]=c==0 ? 17'sd65535 : -17'sd65536;
                else if (cycle<32) product[c][r]=r%2 ? -17'sd65536 : 17'sd65535;
                else product[c][r]=17'($urandom);
            end
            @(posedge clk); #1;
            for (int c=0;c<2;c++) begin
                for (int p=3;p>0;p--) expected[c][p]=expected[c][p-1];
                expected[c][0]=0;
                for (int r=0;r<16;r++) expected[c][0]+=int'(product[c][r]);
                if (cycle>=3 && (wide[c]!==24'(expected[c][3]) || narrow[c]!==19'(expected[c][3])))
                    $fatal(1,"Dot latency/value mismatch cycle=%0d lane=%0d",cycle,c);
            end
        end
        $display("PASS: dot pipeline 512 consecutive cycles, signed extrema, modular widths, four-cycle latency");
        $finish;
    end
endmodule
