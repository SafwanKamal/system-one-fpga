`timescale 1ns/1ps
module split_product_pipeline_tb;
    logic clk=0;
    always #5 clk=~clk;
    logic signed [20:0] a32[0:3];
    logic signed [31:0] b32[0:3];
    logic signed [53:0] p32[0:3];
    logic signed [17:0] a30[0:3];
    logic signed [29:0] b30[0:3];
    logic signed [47:0] p30[0:3];
    longint signed expected32[0:2][0:3],expected30[0:2][0:3];
    split_product_pipeline #(.LANES(4)) gamma_dut(clk,a32,b32,p32);
    split_product_pipeline #(.LANES(4),.A_WIDTH(18),.B_WIDTH(30),.OUT_WIDTH(48)) scale_dut(clk,a30,b30,p30);
    initial begin
        for(int n=0;n<1027;n++) begin
            @(negedge clk);
            for(int c=0;c<4;c++) begin
                a32[c]=21'($random); b32[c]=32'($random);
                a30[c]=18'($random); b30[c]=30'($random);
                if(n<8) begin
                    a32[c]=(c%2==0)?21'h100000:21'h0fffff;
                    a30[c]=(c%2==0)?18'h20000:18'h1ffff;
                    case(n)
                        0: begin b32[c]=32'h80000000;b30[c]=30'h20000000;end
                        1: begin b32[c]=32'h7fffffff;b30[c]=30'h1fffffff;end
                        2: begin b32[c]=-1;b30[c]=-1;end
                        3: begin b32[c]=65535;b30[c]=65535;end
                        4: begin b32[c]=-65536;b30[c]=-65536;end
                        5: begin b32[c]=-65535;b30[c]=-65535;end
                        6: begin b32[c]=65536;b30[c]=268435456;end
                        7: begin b32[c]=0;b30[c]=0;end
                    endcase
                end
                expected32[n%3][c]=64'($signed(a32[c]))*64'($signed(b32[c]));
                expected30[n%3][c]=64'($signed(a30[c]))*64'($signed(b30[c]));
            end
            @(posedge clk); #1;
            if(n>=2) for(int c=0;c<4;c++) begin
                if(64'($signed(p32[c]))!=expected32[(n-2)%3][c])
                    $fatal(1,"gamma product mismatch cycle=%0d lane=%0d",n,c);
                if(64'($signed(p30[c]))!=expected30[(n-2)%3][c])
                    $fatal(1,"scale product mismatch cycle=%0d lane=%0d",n,c);
            end
        end
        $display("PASS: 1025 checked cycles, four lanes, both widths, signed extrema and random products; three-clock latency");
        $finish;
    end
endmodule
