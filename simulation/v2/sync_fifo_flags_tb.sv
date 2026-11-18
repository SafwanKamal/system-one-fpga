`timescale 1ns/1ps
module sync_fifo_flags_tb;
    logic clk=0;
    always #5 clk=~clk;
    for(genvar g=0;g<3;g++) begin: gen_profile
        localparam int DEPTH = g==0 ? 4 : g==1 ? 8 : 64;
        localparam int WIDTH = g==0 ? 16 : 128;
        logic reset=1,we=0,re=0;
        logic [WIDTH-1:0] wd=0,a,b;
        logic fa,fb,ea,eb;
        logic [$clog2(DEPTH):0] ca,cb;
        bit finished=0;
        int checks=0;
        sync_fifo #(.DEPTH(DEPTH),.WIDTH(WIDTH)) baseline(.clk,.reset,
            .write_enable(we),.write_data(wd),.full(fa),.read_enable(re),.read_data(a),.empty(ea),.count(ca));
        sync_fifo_registered_flags #(.DEPTH(DEPTH),.WIDTH(WIDTH)) candidate(.clk,.reset,
            .write_enable(we),.write_data(wd),.full(fb),.read_enable(re),.read_data(b),.empty(eb),.count(cb));
        task automatic check();
            if(fa!==fb || ea!==eb || ca!==cb || (!ea && a!==b))
                $fatal(1,"FIFO mismatch depth=%0d check=%0d flags=%b%b/%b%b count=%0d/%0d",DEPTH,checks,fa,ea,fb,eb,ca,cb);
            checks++;
        endtask
        initial begin
            repeat(3)@(negedge clk);reset=0;
            for(int i=0;i<50000;i++) begin
                @(negedge clk);
                // Directed fill/drain segments hit full/empty boundaries;
                // random phases cover simultaneous operations and pointer wrap.
                case(i%256)
                    0: begin we=1;re=0;end
                    80: begin we=1;re=1;end
                    90: begin we=0;re=1;end
                    default: if(i%256>=180) begin we=1'($urandom);re=1'($urandom);end
                endcase
                wd=WIDTH'({$urandom,$urandom,$urandom,$urandom});
                check();@(posedge clk);#1;check();
                if(i%997==0)begin
                    @(negedge clk);#2;reset=1;#1;
                    check();if(!eb || fb || cb!=0)$fatal(1,"Async reset flag mismatch");
                    @(negedge clk);reset=0;
                end
            end
            finished=1;
        end
    end
    initial begin
        wait(gen_profile[0].finished && gen_profile[1].finished && gen_profile[2].finished);
        $display("PASS: registered FIFO flags depth4/8/64, 300153 comparisons, full/empty/simultaneous/wrap/asynchronous reset");
        $finish;
    end
endmodule
