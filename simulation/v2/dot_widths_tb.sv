module dot_widths_tb;
    logic clk=0;
    always #5 clk=~clk;
    logic signed [16:0] product [0:1][0:15];
    integer expected [0:1][0:3];
    integer cycle;
    for(genvar w=1;w<=32;w++) begin : gen_width
        wire signed [w-1:0] result [0:1];
        dot16_pipeline #(.LANES(2),.WIDTH(w)) dut(.clk(clk),.product(product),.sum(result));
        always @(negedge clk)
            if(cycle>=4)
                for(int c=0;c<2;c++)
                    if(result[c]!==w'(expected[c][3]))
                        $fatal(1,"Dot mismatch width=%0d cycle=%0d lane=%0d",w,cycle,c);
    end
    initial begin
        cycle=0;
        for(int c=0;c<2;c++) for(int p=0;p<4;p++) expected[c][p]=0;
        repeat(4096) begin
            @(negedge clk); #1;
            for(int c=0;c<2;c++) for(int r=0;r<16;r++)
                product[c][r]=cycle<16 ? (c==0 ? 17'sd65535 : -17'sd65536) :
                              cycle<32 ? (r%2 ? -17'sd65536 : 17'sd65535) : 17'($urandom);
            @(posedge clk); #1;
            for(int c=0;c<2;c++) begin
                for(int p=3;p>0;p--) expected[c][p]=expected[c][p-1];
                expected[c][0]=0;
                for(int r=0;r<16;r++) expected[c][0]+=int'(product[c][r]);
            end
            cycle++;
        end
        @(negedge clk); #2;
        $display("PASS: dot widths 1..32, 4096 consecutive cycles, signed extrema and random full-17-bit inputs, four-cycle latency");
        $finish;
    end
endmodule
