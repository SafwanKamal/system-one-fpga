`timescale 1ns / 1ps

/*
v2 memory link through its RMII pins, across two clocks, into a behavioural MIG.

  50 MHz Ethernet clock  : PHY model -> memory_link_core -> PHY transmit monitor
  75 MHz memory clock    : memory_link_core -> mig_memory_port -> mig_native_model
                           (random app_rdy / app_wdf_rdy stalls)

Request frames come from vectors/memory_requests.hex (scripts/v2/memory_link_vectors.py,
built with the host's own encoder), one at a time as a host would send them.
Every transmitted frame is reassembled from the RMII transmit pins and written to
memory_responses.hex; `memory_link_vectors.py --check` then decodes each reply with
the host decoder and compares it with a Python model of the memory.

This testbench checks the timing side: frames that must be ignored get no reply,
the others exactly one, each with a correct preamble and SFD.
*/
module memory_link_tb;

    parameter string VECTOR_DIRECTORY = "vectors";

    localparam integer MAXIMUM_REQUEST_WORDS = 400_000;
    localparam integer MAXIMUM_FRAMES = 1_000;
    localparam integer RESPONSE_TIMEOUT = 60_000;
    localparam integer SILENCE_CYCLES = 3_000;
    localparam integer GAP_DIBITS = 48;

    logic clk = 1'b0;            // Ethernet, 50 MHz
    logic memory_clk = 1'b0;     // memory controller ui_clk, ~75 MHz
    logic reset = 1'b1;

    always #10 clk = ~clk;
    always #6.667 memory_clk = ~memory_clk;

    logic [1:0] rmii_rxd;
    logic rmii_crs_dv;
    logic rmii_rx_er;
    logic [1:0] rmii_txd;
    logic rmii_tx_en;

    logic accepted, rejected, replied, rx_error, dropped, memory_busy, run_active;
    integer rx_error_count = 0, dropped_count = 0, rejected_count = 0;

    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic write_request_valid, write_request_ready, write_valid, write_ready;
    logic [26:0] read_request_address, write_request_address;
    logic [15:0] read_request_beats, write_request_beats;
    logic [127:0] read_data, write_data;

    logic [26:0] app_addr;
    logic [2:0] app_cmd;
    logic app_en, app_wdf_end, app_wdf_wren, app_rd_data_end, app_rd_data_valid;
    logic app_rdy, app_wdf_rdy;
    logic [127:0] app_wdf_data, app_rd_data;
    logic [15:0] app_wdf_mask;

    // memory side reset releases later than the Ethernet side, as calibration does
    logic memory_reset = 1'b1;

    memory_link_core DUT (
        .ethernet_clk(clk), .ethernet_reset(reset),
        .rmii_rxd(rmii_rxd), .rmii_crs_dv(rmii_crs_dv), .rmii_rx_er(rmii_rx_er),
        .rmii_txd(rmii_txd), .rmii_tx_en(rmii_tx_en),
        .accepted_out(accepted), .rejected_out(rejected), .replied_out(replied),
        .rx_error_out(rx_error), .dropped_out(dropped),
        .memory_clk(memory_clk), .memory_reset(memory_reset),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .run_start_out(), .run_descriptor_out(), .run_active_out(run_active),
        .run_done_in(run_active), .run_result_in(128'h80 << 64),
        .memory_busy_out(memory_busy)
    );

    mig_memory_port port_inst (
        .clk(memory_clk), .reset(memory_reset),
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

    mig_native_model model_inst (
        .clk(memory_clk), .reset(memory_reset),
        .app_addr(app_addr), .app_cmd(app_cmd), .app_en(app_en),
        .app_wdf_data(app_wdf_data), .app_wdf_end(app_wdf_end), .app_wdf_mask(app_wdf_mask),
        .app_wdf_wren(app_wdf_wren), .app_rd_data(app_rd_data),
        .app_rd_data_end(app_rd_data_end), .app_rd_data_valid(app_rd_data_valid),
        .app_rdy(app_rdy), .app_wdf_rdy(app_wdf_rdy),
        .corrupt(1'b0), .corrupt_word_address('0)
    );

    always @(posedge clk) begin
        if (rx_error) rx_error_count++;
        if (dropped) dropped_count++;
        if (rejected) rejected_count++;
    end

    logic [8:0] request_ROM [0:MAXIMUM_REQUEST_WORDS - 1];
    logic [0:0] expect_ROM [0:MAXIMUM_FRAMES - 1];
    logic [31:0] frame_count_ROM [0:0];

    integer frame_number = 0;
    integer response_number = 0;
    integer answered_number = 0;
    integer error_number = 0;
    integer response_file;

    // ---- PHY receive model: drive just after our rising edge (see v1 testbench)
    task automatic send_dibit(input logic [1:0] dibit, input logic crs_dv);
        @(posedge clk);
        #1;
        rmii_rxd = dibit;
        rmii_crs_dv = crs_dv;
    endtask

    task automatic send_byte(input logic [7:0] data);
        for (int i = 0; i < 4; i++) begin
            send_dibit(data[2*i +: 2], 1'b1);
        end
    endtask

    task automatic send_frame(inout integer pointer);
        integer start;
        integer length;
        start = pointer;
        while (request_ROM[pointer] < 9'h100) pointer++;
        length = pointer - start;
        pointer++;
        send_dibit(2'b00, 1'b1);
        send_dibit(2'b00, 1'b1);
        for (int i = 0; i < 7; i++) send_byte(8'h55);
        send_byte(8'hD5);
        for (int i = 0; i < length; i++) send_byte(request_ROM[start + i][7:0]);
        for (int i = 0; i < GAP_DIBITS; i++) send_dibit(2'b00, 1'b0);
    endtask

    // ---- PHY transmit monitor
    logic tx_en_previous = 1'b0;
    logic [7:0] tx_shift = '0;
    logic [7:0] tx_byte;
    integer tx_dibit_count = 0;
    integer tx_byte_count = 0;

    always @(negedge clk) begin
        if (!reset) begin
            if (rmii_tx_en) begin
                tx_byte = {rmii_txd, tx_shift[7:2]};
                tx_shift = tx_byte;
                tx_dibit_count++;
                if (tx_dibit_count == 4) begin
                    tx_dibit_count = 0;
                    if (tx_byte_count < 7 && tx_byte != 8'h55) begin
                        $error("reply %0d: preamble byte %0d is %02h", response_number, tx_byte_count, tx_byte);
                        error_number++;
                    end else if (tx_byte_count == 7 && tx_byte != 8'hD5) begin
                        $error("reply %0d: SFD is %02h", response_number, tx_byte);
                        error_number++;
                    end else if (tx_byte_count >= 8) begin
                        $fwrite(response_file, "%03h\n", tx_byte);
                    end
                    tx_byte_count++;
                end
            end else if (tx_en_previous) begin
                if (tx_dibit_count != 0) begin
                    $error("reply %0d ended on a partial byte", response_number);
                    error_number++;
                end
                $fwrite(response_file, "%03h\n", 9'h100);
                response_number++;
                tx_dibit_count = 0;
                tx_byte_count = 0;
            end
            tx_en_previous <= rmii_tx_en;
        end
    end

    initial begin
        integer pointer;
        integer replies_before;
        integer waited;
        rmii_rxd = 2'b00;
        rmii_crs_dv = 1'b0;
        rmii_rx_er = 1'b0;
        pointer = 0;

        $readmemh({VECTOR_DIRECTORY, "/memory_requests.hex"}, request_ROM);
        $readmemb({VECTOR_DIRECTORY, "/memory_expect.hex"}, expect_ROM);
        $readmemh({VECTOR_DIRECTORY, "/memory_frame_count.hex"}, frame_count_ROM);
        if (frame_count_ROM[0] == 0 || request_ROM[0] == 0) begin
            $fatal(1, "Vectors not loaded: run `make memory-vectors` first");
        end
        response_file = $fopen("memory_responses.hex", "w");

        repeat (5) @(negedge clk);
        reset = 1'b0;
        // the first frames arrive while the memory side is still "calibrating"
        fork
            begin
                repeat (3000) @(negedge memory_clk);
                memory_reset = 1'b0;
            end
        join_none

        while (frame_number < frame_count_ROM[0]) begin
            replies_before = response_number;
            send_frame(pointer);
            if (expect_ROM[frame_number]) begin
                waited = 0;
                while (response_number == replies_before && waited < RESPONSE_TIMEOUT) begin
                    @(negedge clk);
                    waited++;
                end
                if (response_number == replies_before) begin
                    $error("frame %0d: no reply after %0d cycles", frame_number, RESPONSE_TIMEOUT);
                    error_number++;
                end
                answered_number++;
            end else begin
                repeat (SILENCE_CYCLES) @(negedge clk);
                if (response_number != replies_before) begin
                    $error("frame %0d should have been ignored but was answered", frame_number);
                    error_number++;
                end
            end
            frame_number++;
        end
        $fclose(response_file);

        $display("frames sent %0d, replies %0d (expected %0d), FCS errors %0d, rejected %0d, dropped %0d",
                 frame_number, response_number, answered_number, rx_error_count, rejected_count,
                 dropped_count);
        if (response_number != answered_number || dropped_count != 0 || rx_error_count == 0
            || rejected_count == 0) begin
            error_number++;
        end
        if (error_number != 0) begin
            $fatal(1, "FAIL: %0d errors", error_number);
        end
        $display("PASS: every frame answered or ignored as expected; run --check for the payloads");
        $finish;
    end

endmodule
