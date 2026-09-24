`timescale 1ns / 1ps

/*
End-to-end check of sysone_ethernet_core through its RMII pins.

A PHY model sends the request frames from vectors/ethernet_requests.hex (built by
scripts/ethernet_vectors.py with the host's own encoder) into the RMII receive
pins, one frame at a time, the way a host waits for each answer. Every frame
the core transmits is reassembled from the RMII transmit pins and written to
ethernet_responses.hex, and `uv run python ../scripts/ethernet_vectors.py --check`
decodes them with the host's decoder and compares every logit with the golden
model.

This testbench checks the timing side: frames that must be ignored produce no
response, frames that must be answered produce exactly one, and each response
starts with a correct preamble and SFD.
*/
module sysone_ethernet_tb;

    `include "model_parameters.svh"

    parameter string MEMORY_DIRECTORY = "../memory";
    parameter string VECTOR_DIRECTORY = "vectors";

    localparam integer MAXIMUM_REQUEST_WORDS = 1_000_000;
    localparam integer MAXIMUM_FRAMES = 8_000;
    localparam integer RESPONSE_TIMEOUT = 30_000;
    localparam integer SILENCE_CYCLES = 6_000;
    localparam integer GAP_DIBITS = 48;          // 96 bit times

    logic clk;
    logic reset;

    logic [1:0] rmii_rxd;
    logic rmii_crs_dv;
    logic rmii_rx_er;
    logic [1:0] rmii_txd;
    logic rmii_tx_en;

    logic busy_out;
    logic served_toggle_out;
    logic rx_error_out;
    logic dropped_out;
    logic tx_error_out;

    logic [8:0] request_ROM [0:MAXIMUM_REQUEST_WORDS - 1];
    logic [0:0] expect_ROM [0:MAXIMUM_FRAMES - 1];
    logic [31:0] frame_count_ROM [0:0];

    integer frame_number;
    integer response_number;
    integer answered_number;
    integer error_number;
    integer response_file;

    // latency, in 20 ns clocks: last request dibit -> first and last response dibit
    integer cycle_number = 0;
    integer request_end_cycle;
    integer response_start_cycle;
    integer first_latency_sum, first_latency_minimum, first_latency_maximum;
    integer last_latency_sum, last_latency_minimum, last_latency_maximum;
    logic waiting_for_response;


    /*
     * 50 MHz RMII clock:
     * period = 20 ns
     */
    always begin
        #10 clk = ~clk;
    end


    sysone_ethernet_core #(
        .ROW_NUMBER      (MODEL_ROW_NUMBER),
        .DIMENSION       (MODEL_DIMENSION),
        .HIDDEN          (MODEL_HIDDEN),
        .CLASS_NUMBER    (MODEL_CLASS_NUMBER),
        .MAXIMUM_FEATURES(MODEL_MAXIMUM_FEATURES),
        .POOL_GAIN       (MODEL_POOL_GAIN),

        .EMBEDDING_LOW_FILE    ({MEMORY_DIRECTORY, "/embedding_low.mem"}),
        .EMBEDDING_HIGH_FILE   ({MEMORY_DIRECTORY, "/embedding_high.mem"}),
        .RECIPROCAL_FILE       ({MEMORY_DIRECTORY, "/pool_reciprocals.mem"}),
        .HIDDEN_WEIGHT_FILE    ({MEMORY_DIRECTORY, "/dense_hidden_weights.mem"}),
        .HIDDEN_BIAS_FILE      ({MEMORY_DIRECTORY, "/dense_hidden_biases.mem"}),
        .OUTPUT_WEIGHT_FILE    ({MEMORY_DIRECTORY, "/dense_output_weights.mem"}),
        .OUTPUT_BIAS_FILE      ({MEMORY_DIRECTORY, "/dense_output_biases.mem"}),
        .HIDDEN_MULTIPLIER_FILE({MEMORY_DIRECTORY, "/requant_hidden_multipliers.mem"}),
        .HIDDEN_REQUANT_FILE   ({MEMORY_DIRECTORY, "/requant_hidden_biases.mem"}),
        .OUTPUT_MULTIPLIER_FILE({MEMORY_DIRECTORY, "/requant_output_multipliers.mem"}),
        .OUTPUT_REQUANT_FILE   ({MEMORY_DIRECTORY, "/requant_output_biases.mem"})
    ) DUT (
        .clk              (clk),
        .reset            (reset),
        .rmii_rxd         (rmii_rxd),
        .rmii_crs_dv      (rmii_crs_dv),
        .rmii_rx_er       (rmii_rx_er),
        .rmii_txd         (rmii_txd),
        .rmii_tx_en       (rmii_tx_en),
        .busy_out         (busy_out),
        .served_toggle_out(served_toggle_out),
        .rx_error_out     (rx_error_out),
        .dropped_out      (dropped_out),
        .tx_error_out     (tx_error_out)
    );


    /*
     * PHY receive model.
     *
     * The PHY launches on its rising edge, which is the core's falling edge, and
     * the core samples on the next falling edge. Driving just after our rising
     * edge puts every change half a period away from the sampling edge.
     */
    always @(posedge clk) begin
        cycle_number <= cycle_number + 1;
    end


    task automatic send_dibit (
        input logic [1:0] dibit,
        input logic crs_dv
    );
        begin
            @(posedge clk);
            #1;
            rmii_rxd = dibit;
            rmii_crs_dv = crs_dv;
        end
    endtask


    task automatic send_byte (
        input logic [7:0] data,
        input logic toggle      // CRS_DV low on the first dibit of each nibble
    );
        begin
            for (int i = 0; i < 4; i++) begin
                send_dibit(data[2*i +: 2], !(toggle && (i % 2 == 0)));
            end
        end
    endtask


    task automatic send_frame (
        inout integer pointer
    );
        integer start;
        integer length;
        logic toggle;

        begin
            // find the frame's length and whether its tail toggles CRS_DV
            start = pointer;

            while (request_ROM[pointer] < 9'h100) begin
                pointer++;
            end

            length = pointer - start;
            toggle = (request_ROM[pointer] == 9'h101);
            pointer++;

            // carrier, a few dibits of 00 while the PHY locks, preamble and SFD
            send_dibit(2'b00, 1'b1);
            send_dibit(2'b00, 1'b1);

            for (int i = 0; i < 7; i++) begin
                send_byte(8'h55, 1'b0);
            end

            send_byte(8'hD5, 1'b0);

            // the LAN8720A toggles CRS_DV over the last bytes still in its FIFO
            for (int i = 0; i < length; i++) begin
                send_byte(request_ROM[start + i][7:0], toggle && (i >= length - 2));
            end

            request_end_cycle = cycle_number;

            for (int i = 0; i < GAP_DIBITS; i++) begin
                send_dibit(2'b00, 1'b0);
            end
        end
    endtask


    /*
     * RMII transmit monitor.
     *
     * rmii_TX updates on the rising edge, so the pins are sampled on the falling
     * edge. Dibits are assembled least significant first from the start of
     * TX_EN; the first 8 bytes must be the preamble and SFD.
     */
    logic tx_en_previous;
    logic [7:0] tx_shift;
    integer tx_dibit_count;
    integer tx_byte_count;
    logic [7:0] tx_byte;

    always @(negedge clk) begin
        if (reset) begin
            tx_en_previous <= 1'b0;
            tx_dibit_count = 0;
            tx_byte_count = 0;
        end else begin
            if (rmii_tx_en && !tx_en_previous) begin
                response_start_cycle = cycle_number;
            end

            if (rmii_tx_en) begin
                tx_byte = {rmii_txd, tx_shift[7:2]};
                tx_shift = tx_byte;
                tx_dibit_count++;

                if (tx_dibit_count == 4) begin
                    tx_dibit_count = 0;

                    if (tx_byte_count < 7 && tx_byte != 8'h55) begin
                        $error("Response %0d: preamble byte %0d is %02h", response_number, tx_byte_count, tx_byte);
                        error_number++;
                    end else if (tx_byte_count == 7 && tx_byte != 8'hD5) begin
                        $error("Response %0d: SFD is %02h", response_number, tx_byte);
                        error_number++;
                    end else if (tx_byte_count >= 8) begin
                        $fwrite(response_file, "%03h\n", tx_byte);
                    end

                    tx_byte_count++;
                end
            end else if (tx_en_previous) begin
                if (tx_dibit_count != 0) begin
                    $error("Response %0d ended on a partial byte", response_number);
                    error_number++;
                end

                $fwrite(response_file, "%03h\n", 9'h100);
                response_number++;

                if (waiting_for_response) begin
                    first_latency_sum += response_start_cycle - request_end_cycle;
                    last_latency_sum += cycle_number - request_end_cycle;

                    if (response_start_cycle - request_end_cycle < first_latency_minimum)
                        first_latency_minimum = response_start_cycle - request_end_cycle;
                    if (response_start_cycle - request_end_cycle > first_latency_maximum)
                        first_latency_maximum = response_start_cycle - request_end_cycle;
                    if (cycle_number - request_end_cycle < last_latency_minimum)
                        last_latency_minimum = cycle_number - request_end_cycle;
                    if (cycle_number - request_end_cycle > last_latency_maximum)
                        last_latency_maximum = cycle_number - request_end_cycle;
                end
                tx_dibit_count = 0;
                tx_byte_count = 0;
            end

            tx_en_previous <= rmii_tx_en;
        end
    end


    initial begin
        integer pointer;
        integer responses_before;
        integer wait_cycles;

        clk = 1'b0;
        reset = 1'b1;
        rmii_rxd = 2'b00;
        rmii_crs_dv = 1'b0;
        rmii_rx_er = 1'b0;
        tx_shift = '0;

        frame_number = 0;
        response_number = 0;
        answered_number = 0;
        error_number = 0;
        pointer = 0;
        waiting_for_response = 1'b0;
        first_latency_sum = 0;
        first_latency_minimum = 1 << 30;
        first_latency_maximum = 0;
        last_latency_sum = 0;
        last_latency_minimum = 1 << 30;
        last_latency_maximum = 0;

        $readmemh({VECTOR_DIRECTORY, "/ethernet_requests.hex"}, request_ROM);
        $readmemb({VECTOR_DIRECTORY, "/ethernet_expect.hex"}, expect_ROM);
        $readmemh({VECTOR_DIRECTORY, "/ethernet_frame_count.hex"}, frame_count_ROM);

        // An unloaded file reads as zeros, not X, in a two-state simulator
        if (frame_count_ROM[0] == 0 || request_ROM[0] == 0) begin
            $fatal(1, "Vectors not loaded: run `make ethernet-vectors` first");
        end

        response_file = $fopen("ethernet_responses.hex", "w");

        repeat (5) begin
            @(negedge clk);
        end

        reset = 1'b0;

        repeat (5) begin
            @(negedge clk);
        end


        while (frame_number < frame_count_ROM[0]) begin
            responses_before = response_number;
            waiting_for_response = expect_ROM[frame_number];
            send_frame(pointer);

            if (expect_ROM[frame_number]) begin
                wait_cycles = 0;

                while (response_number == responses_before && wait_cycles < RESPONSE_TIMEOUT) begin
                    @(negedge clk);
                    wait_cycles++;
                end

                if (response_number == responses_before) begin
                    $error("Frame %0d: no response after %0d cycles", frame_number, RESPONSE_TIMEOUT);
                    error_number++;
                end

                answered_number++;
            end else begin
                repeat (SILENCE_CYCLES) begin
                    @(negedge clk);
                end

                if (response_number != responses_before) begin
                    $error("Frame %0d should have been ignored but was answered", frame_number);
                    error_number++;
                end
            end

            frame_number++;

            if (frame_number % 500 == 0) begin
                $display("Sent %0d frames, %0d responses", frame_number, response_number);
            end
        end

        $fclose(response_file);

        $display("----------------------------------------------------------");
        $display("frames sent        %0d", frame_number);
        $display("responses          %0d (expected %0d)", response_number, answered_number);
        $display("rx_error_out       %0d (bad frames were sent, so 1 is expected)", rx_error_out);
        $display("dropped_out        %0d", dropped_out);
        $display("tx_error_out       %0d", tx_error_out);
        $display(
            "latency, end of request frame -> first response dibit: min %0.1f  mean %0.1f  max %0.1f us",
            first_latency_minimum * 0.02,
            first_latency_sum * 0.02 / answered_number,
            first_latency_maximum * 0.02
        );
        $display(
            "latency, end of request frame -> last response dibit:  min %0.1f  mean %0.1f  max %0.1f us",
            last_latency_minimum * 0.02,
            last_latency_sum * 0.02 / answered_number,
            last_latency_maximum * 0.02
        );

        if (response_number != answered_number || dropped_out || tx_error_out || !rx_error_out) begin
            error_number++;
        end

        if (error_number != 0) begin
            $fatal(1, "FAIL: %0d errors", error_number);
        end

        $display("PASS: every frame answered or ignored as expected; run --check for the payloads");
        $finish;
    end

endmodule
