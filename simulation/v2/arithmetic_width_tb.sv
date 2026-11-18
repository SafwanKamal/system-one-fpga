// Compare the full residual engine against the frozen pre-narrowing RTL.
module arithmetic_width_tb;
    logic clk=0, reset=1, start=0;
    always #5 clk=~clk;
    logic [16:0] multiplier;
    logic [5:0] shift;
    logic [127:0] a_data, x_data;
    logic [15:0] test_width;
    logic [7:0] test_tokens;
    wire [13:0] new_a, old_a, new_x, old_x;
    wire [127:0] new_data, old_data;
    wire new_write, old_write, new_busy, old_busy, new_done, old_done;
    wire [13:0] new_address, old_address;
    add_skip_engine #(.READ_LATENCY(4)) updated(
        .clk(clk),.reset(reset),.start(start),.busy(new_busy),.done(new_done),
        .multiplier(multiplier),.shift(shift),.width(test_width),.token_count(test_tokens),
        .a_data(a_data),.x_data(x_data),.a_address(new_a),.x_address(new_x),
        .destination_write(new_write),.destination_address(new_address),
        .destination_data(new_data),.destination_enable());
    add_skip_legacy #(.READ_LATENCY(4)) baseline(
        .clk(clk),.reset(reset),.start(start),.busy(old_busy),.done(old_done),
        .multiplier(multiplier),.shift(shift),.width(test_width),.token_count(test_tokens),
        .a_data(a_data),.x_data(x_data),.a_address(old_a),.x_address(old_x),
        .destination_write(old_write),.destination_address(old_address),
        .destination_data(old_data),.destination_enable());
    integer writes=0, expected_writes=0;
    initial begin
        multiplier=0; shift=0; a_data=0; x_data=0; test_width=1024; test_tokens=128;
        repeat(3) @(negedge clk);
        reset=0;
        // Cancel an active instruction, then reuse both engines immediately.
        start=1; @(negedge clk); start=0;
        repeat(12) @(negedge clk);
        reset=1; @(negedge clk);
        if(new_write || old_write || new_busy || old_busy) $fatal(1,"Reset did not cancel residual pipeline");
        reset=0;
        // Include all shift values, multiplier endpoints and randomized payloads.
        for(int run=0;run<128;run++) begin
            case(run%8)
                0:test_width=16; 1:test_width=48; 2:test_width=80; 3:test_width=256;
                4:test_width=512; 5:test_width=768; 6:test_width=1008; 7:test_width=1024;
            endcase
            test_tokens=run%8==7 ? 8'd128 : run%3==0 ? 8'd1 : run%3==1 ? 8'd3 : 8'd7;
            expected_writes+=int'(test_width>>3)*int'(test_tokens);
            shift=6'(run);
            multiplier=run<64 ? 17'h1ffff : 17'($urandom);
            start=1;
            @(negedge clk); start=0;
            for(int cycle=0;cycle<int'(test_width>>3)*int'(test_tokens)+30;cycle++) begin
                if(updated.issue && (new_a!==old_a || new_x!==old_x))
                    $fatal(1,"Residual read-address mismatch run=%0d cycle=%0d",run,cycle);
                for(int e=0;e<8;e++) begin
                    case(cycle%8)
                        0: a_data[16*e+:16]=16'h8000;
                        1: a_data[16*e+:16]=16'h7fff;
                        2: a_data[16*e+:16]=16'h8001;
                        3: a_data[16*e+:16]=0;
                        default: a_data[16*e+:16]=16'($urandom);
                    endcase
                end
                for(int e=0;e<16;e++)
                    x_data[8*e+:8]=cycle%4==0 ? 8'h80 : cycle%4==1 ? 8'h7f : 8'($urandom);
                @(posedge clk); #1;
                if(new_write!==old_write || new_busy!==old_busy || new_done!==old_done)
                    $fatal(1,"Residual control mismatch run=%0d cycle=%0d",run,cycle);
                if(new_write) begin
                    writes++;
                    if(new_data!==old_data || new_address!==old_address)
                        $fatal(1,"Residual arithmetic/tag mismatch run=%0d cycle=%0d",run,cycle);
                end
                @(negedge clk);
            end
        end
        if(writes!=expected_writes) $fatal(1,"Residual coverage incomplete: %0d",writes);
        $display("PASS: residual cursor frozen equivalence %0d writes, widths 16..1024, non-power-of-two rows, 128-token boundary, reset/restart, all shifts",writes);
        $finish;
    end
endmodule
