// ddr_selftest + mig_memory_port against the behavioural MIG model.
//
// Run 1: clean memory, must pass with zero errors.
// Run 2: one stored beat is corrupted between the write and read phases; the test
//        must report exactly one error.
// Also checks read_last framing on the memory port: exactly one read_last per
// REQUEST_BEATS beats.
module ddr_selftest_tb;

    localparam integer ADDRESS_WIDTH = 27;
    localparam integer DATA_WIDTH = 128;
    localparam integer BEATS_WIDTH = 16;
    localparam longint REGION_BYTES = 64'd262144;      // 256 KiB keeps the run short
    localparam integer REQUEST_BEATS = 64;

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

    logic [ADDRESS_WIDTH-1:0] app_addr;
    logic [2:0] app_cmd;
    logic app_en, app_wdf_end, app_wdf_wren, app_rd_data_end, app_rd_data_valid;
    logic app_rdy, app_wdf_rdy;
    logic [DATA_WIDTH-1:0] app_wdf_data, app_rd_data;
    logic [DATA_WIDTH/8-1:0] app_wdf_mask;

    logic busy, write_done, done, passed;
    logic [31:0] error_count;
    logic [39:0] write_cycles, read_cycles;

    mig_native_model #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH)
    ) model_inst (
        .clk(clk), .reset(reset),
        .app_addr(app_addr), .app_cmd(app_cmd), .app_en(app_en),
        .app_wdf_data(app_wdf_data), .app_wdf_end(app_wdf_end), .app_wdf_mask(app_wdf_mask),
        .app_wdf_wren(app_wdf_wren), .app_rd_data(app_rd_data),
        .app_rd_data_end(app_rd_data_end), .app_rd_data_valid(app_rd_data_valid),
        .app_rdy(app_rdy), .app_wdf_rdy(app_wdf_rdy),
        .corrupt(corrupt), .corrupt_word_address(27'h0000_1A8)
    );

    mig_memory_port #(
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
        .app_addr(app_addr), .app_cmd(app_cmd), .app_en(app_en),
        .app_wdf_data(app_wdf_data), .app_wdf_end(app_wdf_end), .app_wdf_mask(app_wdf_mask),
        .app_wdf_wren(app_wdf_wren), .app_rd_data(app_rd_data),
        .app_rd_data_end(app_rd_data_end), .app_rd_data_valid(app_rd_data_valid),
        .app_rdy(app_rdy), .app_wdf_rdy(app_wdf_rdy)
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
        $display("PASS: ddr_selftest + mig_memory_port against the MIG model");
        $finish;
    end

    initial begin
        #50_000_000;
        $fatal(1, "timeout");
    end

endmodule
