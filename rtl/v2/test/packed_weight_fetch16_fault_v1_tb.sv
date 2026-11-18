`timescale 1ns/1ps
module packed_weight_fetch16_fault_v1_tb;
    parameter integer BITS=7;
    parameter integer WITH_DOT=0;
    logic clk=0,reset=1,row_valid=0,row_ready,out_valid,out_ready=0,fault;
    logic [39:0] row_address=0,read_request_address;
    logic [127:0] signed_bytes,read_data=0;
    logic read_request_valid,read_request_ready=0,read_valid=0,read_ready,read_last=0,response_error=0;
    logic [15:0] read_request_beats;
    logic [127:0] activations=0;
    logic signed [19:0] out_sum;
    integer checks=0;
    if(WITH_DOT==0) begin: plain
        packed_weight_fetch16_v1 #(.BITS(BITS)) dut(.*);
    end else begin: dot
        packed_weight_fetch_dot16_v1 #(.BITS(BITS)) dut(.*);
    end
    always #5 clk=~clk;
    task restart;
        begin
            reset=1; row_valid=0;read_request_ready=0;read_valid=0;response_error=0;
            @(negedge clk);
            if(row_ready || out_valid || read_ready || read_request_valid || fault) $fatal(1,"reset state");
            reset=0;
        end
    endtask
    task issue(input logic [39:0] address);
        begin
            row_address=address;row_valid=1;
            @(negedge clk);row_valid=0;
            repeat(3) begin
                if(!read_request_valid || read_request_address!=={address[39:4],4'b0})
                    $fatal(1,"descriptor not held");
                @(negedge clk);
            end
            read_request_ready=1;@(negedge clk);read_request_ready=0;
        end
    endtask
    task expect_fault;
        begin
            repeat(3) begin
                @(negedge clk);
                if(!fault || row_ready || out_valid || read_ready || read_request_valid)
                    $fatal(1,"fault did not quarantine");
            end
            checks=checks+1;
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);restart();
        // Early last on a two-beat row.
        issue(40'h123f);read_valid=1;read_last=1;
        @(negedge clk);read_valid=0;expect_fault();restart();
        // Missing last on the sole beat.
        issue(40'h1200);read_valid=1;read_last=0;
        @(negedge clk);read_valid=0;expect_fault();restart();
        // Missing last on the second beat.
        issue(40'h123f);read_valid=1;read_last=0;
        @(negedge clk);@(negedge clk);read_valid=0;expect_fault();restart();
        // Last byte would overflow the physical address representation.
        row_address=40'hffffffffff;row_valid=1;
        @(negedge clk);row_valid=0;expect_fault();restart();
        // Shared memory error while waiting for data.
        issue(40'h1200);response_error=1;
        #1;if(out_valid || read_ready) $fatal(1,"error gating");
        @(negedge clk);response_error=0;expect_fault();restart();
        // Reset every transaction phase. Domain reset cancels pending reads.
        row_address=40'h123f;row_valid=1;@(negedge clk);restart();checks=checks+1;
        issue(40'h123f);restart();checks=checks+1;
        issue(40'h123f);read_valid=1;read_last=0;@(negedge clk);restart();checks=checks+1;
        issue(40'h1200);read_valid=1;read_last=1;@(negedge clk);restart();checks=checks+1;
        issue(40'h1200);read_valid=1;read_last=1;@(negedge clk);read_valid=0;
        repeat(8) @(negedge clk);
        if(!out_valid) $fatal(1,"missing held result");
        response_error=1;#1;if(out_valid) $fatal(1,"published after error");
        @(negedge clk);response_error=0;expect_fault();restart();
        issue(40'h1200);read_valid=1;read_last=1;@(negedge clk);read_valid=0;
        repeat(8) @(negedge clk);if(!out_valid) $fatal(1,"reset result setup");
        restart();checks=checks+1;
        // Recovery after reset: valid zero row must be delivered exactly once.
        issue(40'h1200);read_valid=1;read_last=1;@(negedge clk);read_valid=0;
        repeat(8) @(negedge clk);
        if(!out_valid || (WITH_DOT==0 && signed_bytes!==0) || (WITH_DOT!=0 && out_sum!==0)) $fatal(1,"recovery");
        out_ready=1;@(negedge clk);@(negedge clk);
        if(out_valid || fault || !row_ready) $fatal(1,"recovery duplicate");checks=checks+1;
        $display("PASS bits=%0d dot=%0d fault_reset_checks=%0d",BITS,WITH_DOT,checks);$finish;
    end
    initial begin #100000;$fatal(1,"timeout");end
endmodule
