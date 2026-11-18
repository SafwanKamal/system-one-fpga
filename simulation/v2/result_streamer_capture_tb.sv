`timescale 1ns/1ps
module result_streamer_capture_tb;
    logic clk = 0;
    always #5 clk = ~clk;
    for (genvar g = 0; g < 3; g++) begin : gen_latency
        localparam int L = 3 + g;
        logic reset = 1, start = 0, ready = 0, valid;
        logic [14:0] first_address, read_address;
        logic [15:0] words;
        logic [127:0] data, pipeline [0:L-1];
        bit finished = 0;
        function automatic logic [127:0] pattern(input logic [14:0] address);
            return {32'(address) ^ 32'h19283746, 32'(address)*7, 32'(address)*3, 32'(address)};
        endfunction
        always @(posedge clk) begin
            pipeline[0] <= pattern(read_address);
            for (int i=1; i<L; i++) pipeline[i] <= pipeline[i-1];
        end
        result_streamer #(.READ_LATENCY(L)) dut (
            .clk(clk), .reset(reset), .start(start), .first_address(first_address), .words(words),
            .read_address(read_address), .read_data(pipeline[L-1]), .valid(valid), .ready(ready), .data(data)
        );
        initial begin
            int lengths[8] = '{1,2,63,64,65,97,129,1024};
            repeat(5) @(negedge clk);
            reset=0;
            for (int t=0; t<32; t++) begin
                int accepted, cycles;
                logic [127:0] held;
                bit was_held;
                @(negedge clk);
                first_address=15'(t*71); words=16'(lengths[t%8]); start=1; ready=0;
                @(negedge clk); start=0;
                accepted=0; cycles=0; was_held=0;
                while (accepted<words) begin
                    // Force an initial 100-cycle stall, then random backpressure.
                    ready=cycles>100 && $urandom_range(99,0)<35;
                    @(posedge clk);
                    if (was_held && (!valid || data !== held)) $fatal(1,"unstable held output L%0d",L);
                    was_held=valid && !ready;
                    held=data;
                    if (valid && ready) begin
                        if(data !== pattern(first_address+15'(accepted)))
                            $fatal(1,"stream data/order mismatch L%0d case%0d word%0d",L,t,accepted);
                        accepted++;
                    end
                    cycles++;
                    if(cycles>100000) $fatal(1,"stream timeout");
                    @(negedge clk);
                end
                ready=0;
                repeat(5) @(negedge clk);
                if(valid) $fatal(1,"duplicate output after chunk completion");
            end
            finished=1;
        end
    end
    initial begin
        wait(gen_latency[0].finished && gen_latency[1].finished && gen_latency[2].finished);
        $display("PASS: result streamer 96 chunks, latency 3/4/5, prolonged/random backpressure");
        $finish;
    end
endmodule
