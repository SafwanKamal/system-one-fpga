// ddr_selftest + axi_memory_port (KR260 / AXI platforms) against an AXI4 slave model.
// Requests of 300 beats exercise the splitting into <=256-beat bursts that do not
// cross 4 KiB.
//
// Run 1: clean memory, must pass with zero errors.
// Run 2: one stored beat is corrupted between the write and read phases; the test
//        must report exactly one error.
// Also checks read_last framing on the memory port: exactly one read_last per
// REQUEST_BEATS beats.
module axi_selftest_tb;

    localparam integer ADDRESS_WIDTH = 40;
    localparam integer DATA_WIDTH = 128;
    localparam integer BEATS_WIDTH = 16;
    localparam longint REGION_BYTES = 64'd240000;      // 50 requests of 300 beats
    localparam integer REQUEST_BEATS = 300;

    logic clk = 1'b0;
    logic reset = 1'b1;
    always #5 clk = ~clk;

    logic start;
    logic [31:0] seed;
    logic corrupt;

    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic write_request_valid, write_request_ready, write_valid, write_ready;
    logic [ADDRESS_WIDTH-1:0] read_request_address, write_request_address;
    logic [BEATS_WIDTH-1:0] read_request_beats, write_request_beats;
    logic [DATA_WIDTH-1:0] read_data, write_data;

    logic [ADDRESS_WIDTH-1:0] araddr, awaddr;
    logic [7:0] arlen, awlen;
    logic [2:0] arsize, awsize;
    logic [1:0] arburst, awburst, rresp, bresp;
    logic arvalid, arready, rlast, rvalid, rready, awvalid, awready, wlast, wvalid, wready;
    logic bvalid, bready, response_error;
    logic [DATA_WIDTH-1:0] rdata, wdata;
    logic [DATA_WIDTH/8-1:0] wstrb;

    logic busy, write_done, done, passed;
    logic [31:0] error_count;
    logic [39:0] write_cycles, read_cycles;

    axi_slave_model #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH)
    ) model_inst (
        .clk(clk), .reset(reset),
        .araddr(araddr), .arlen(arlen), .arsize(arsize), .arburst(arburst), .arvalid(arvalid),
        .arready(arready), .rdata(rdata), .rresp(rresp), .rlast(rlast), .rvalid(rvalid),
        .rready(rready),
        .awaddr(awaddr), .awlen(awlen), .awsize(awsize), .awburst(awburst), .awvalid(awvalid),
        .awready(awready), .wdata(wdata), .wstrb(wstrb), .wlast(wlast), .wvalid(wvalid),
        .wready(wready), .bresp(bresp), .bvalid(bvalid), .bready(bready),
        .corrupt(corrupt), .corrupt_address(40'h0000_0D50)
    );

    axi_memory_port #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH)
    ) DUT_port (
        .clk(clk), .reset(reset),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .m_axi_araddr(araddr), .m_axi_arlen(arlen), .m_axi_arsize(arsize), .m_axi_arburst(arburst),
        .m_axi_arvalid(arvalid), .m_axi_arready(arready), .m_axi_rdata(rdata), .m_axi_rresp(rresp),
        .m_axi_rlast(rlast), .m_axi_rvalid(rvalid), .m_axi_rready(rready),
        .m_axi_awaddr(awaddr), .m_axi_awlen(awlen), .m_axi_awsize(awsize), .m_axi_awburst(awburst),
        .m_axi_awvalid(awvalid), .m_axi_awready(awready), .m_axi_wdata(wdata), .m_axi_wstrb(wstrb),
        .m_axi_wlast(wlast), .m_axi_wvalid(wvalid), .m_axi_wready(wready), .m_axi_bresp(bresp),
        .m_axi_bvalid(bvalid), .m_axi_bready(bready), .response_error(response_error)
    );

    ddr_selftest #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH),
        .REGION_BYTES  (REGION_BYTES),
        .REQUEST_BEATS (REQUEST_BEATS)
    ) DUT_test (
        .clk(clk), .reset(reset), .start(start), .seed(seed),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .busy(busy), .write_done(write_done), .done(done), .passed(passed),
        .error_count(error_count), .write_cycles(write_cycles), .read_cycles(read_cycles)
    );

    // read_last framing
    integer beats_seen, lasts_seen;
    always_ff @(posedge clk) begin
        if (reset || start) begin
            beats_seen <= 0;
            lasts_seen <= 0;
        end else if (read_valid && read_ready) begin
            beats_seen <= beats_seen + 1;
            if (read_last) begin
                lasts_seen <= lasts_seen + 1;
                if ((beats_seen + 1) % REQUEST_BEATS != 0) begin
                    $error("read_last after beat %0d, not on a request boundary", beats_seen + 1);
                end
            end
        end
    end

    integer lasts_in_run;

    task automatic run(input logic [31:0] run_seed, input logic inject, output logic ok,
                       output logic [31:0] errors);
        @(negedge clk);
        seed = run_seed;
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;
        wait (write_done);
        @(negedge clk);
        if (inject) begin
            corrupt = 1'b1;
            @(negedge clk);
            corrupt = 1'b0;
        end
        wait (done);
        @(negedge clk);
        ok = passed;
        errors = error_count;
        lasts_in_run = lasts_seen;
        $display("run seed %h: %s, %0d errors, write %0d cycles, read %0d cycles (%.0f%% / %.0f%% of peak), %0d read_last",
                 run_seed, passed ? "PASS" : "FAIL", error_count, write_cycles, read_cycles,
                 100.0 * (REGION_BYTES / 16) / write_cycles, 100.0 * (REGION_BYTES / 16) / read_cycles,
                 lasts_seen);
        start = 1'b1;            // FINISHED -> IDLE
        @(negedge clk);
        start = 1'b0;
    endtask

    logic ok;
    logic [31:0] errors;

    initial begin
        start = 1'b0;
        seed = '0;
        corrupt = 1'b0;
        repeat (5) @(negedge clk);
        reset = 1'b0;
        repeat (5) @(negedge clk);

        run(32'h1234_5678, 1'b0, ok, errors);
        if (!ok || errors != 0 || lasts_in_run != REGION_BYTES / 16 / REQUEST_BEATS) begin
            $fatal(1, "clean run should pass with one read_last per request");
        end
        run(32'h0BAD_F00D, 1'b1, ok, errors);
        if (ok || errors != 1) begin
            $fatal(1, "corrupted run should report exactly one error, got %0d", errors);
        end
        if (response_error) $fatal(1, "AXI error response");
        $display("PASS: ddr_selftest + axi_memory_port against the AXI4 slave model");
        $finish;
    end

    initial begin
        #50_000_000;
        $fatal(1, "timeout");
    end

endmodule
