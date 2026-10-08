// Behavioural stand-in for the MIG native user interface, for simulating the v2
// memory port and everything above it without the Xilinx DDR2 PHY.
//
// What it reproduces, because the adapter has to cope with it:
//   * app_rdy and app_wdf_rdy drop at random (refresh, bank conflicts, full queues)
//   * read data comes back READ_LATENCY clocks after the command, in order, and
//     cannot be stalled (there is no ready on the read data path)
//   * one command = one 128-bit beat; app_addr counts 16-bit words, 8 per beat
// Storage is an associative array, so a 128 MiB address space costs nothing until
// it is touched. `corrupt` flips bit 0 of one stored beat, to check that a test
// actually detects errors.
module mig_native_model #(
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer DATA_WIDTH = 128,
    parameter integer READ_LATENCY = 22,
    parameter integer BUSY_PERCENT = 20,
    // optional: memory contents at start, one 128-bit word per line from byte 0
    // (e.g. a DDR image, as written by scripts/v2/system_vectors.py)
    parameter string PRELOAD = ""
) (
    input logic clk,
    input logic reset,

    input logic [ADDRESS_WIDTH-1:0] app_addr,
    input logic [2:0] app_cmd,
    input logic app_en,
    input logic [DATA_WIDTH-1:0] app_wdf_data,
    input logic app_wdf_end,
    input logic [DATA_WIDTH/8-1:0] app_wdf_mask,
    input logic app_wdf_wren,
    output logic [DATA_WIDTH-1:0] app_rd_data,
    output logic app_rd_data_end,
    output logic app_rd_data_valid,
    output logic app_rdy,
    output logic app_wdf_rdy,

    input logic corrupt,
    input logic [ADDRESS_WIDTH-1:0] corrupt_word_address
);

    logic [DATA_WIDTH-1:0] memory [logic [ADDRESS_WIDTH-1:0]];
    logic [DATA_WIDTH-1:0] pipe_data [0:READ_LATENCY-1];
    logic pipe_valid [0:READ_LATENCY-1];

    initial begin
        if (PRELOAD != "") begin
            int fd, r, n;
            logic [DATA_WIDTH-1:0] word;
            fd = $fopen(PRELOAD, "r");
            if (fd == 0) $fatal(1, "mig_native_model: cannot open %s", PRELOAD);
            n = 0;
            while (!$feof(fd)) begin
                r = $fscanf(fd, "%h\n", word);
                if (r != 1) break;
                memory[ADDRESS_WIDTH'(n * (DATA_WIDTH / 16))] = word;   // app_addr counts 16-bit words
                n++;
            end
            $fclose(fd);
            $display("mig_native_model: %0d words preloaded from %s", n, PRELOAD);
        end
    end

    always_ff @(posedge clk) begin
        if (reset) begin
            app_rdy <= 1'b0;
            app_wdf_rdy <= 1'b0;
            for (int i = 0; i < READ_LATENCY; i++) begin
                pipe_valid[i] <= 1'b0;
            end
        end else begin
            app_rdy <= ($urandom_range(99) >= BUSY_PERCENT);
            app_wdf_rdy <= ($urandom_range(99) >= BUSY_PERCENT);

            for (int i = READ_LATENCY - 1; i > 0; i--) begin
                pipe_valid[i] <= pipe_valid[i-1];
                pipe_data[i] <= pipe_data[i-1];
            end
            pipe_valid[0] <= 1'b0;

            if (app_en && app_rdy) begin
                if (app_addr[2:0] != 3'b000) begin
                    $error("app_addr %h is not aligned to a beat", app_addr);
                end
                if (app_cmd == 3'b000) begin
                    if (!(app_wdf_wren && app_wdf_rdy && app_wdf_end)) begin
                        $error("write command without its data beat in the same cycle");
                    end
                    memory[app_addr] = app_wdf_data;     // blocking: associative arrays cannot take <=
                end else if (app_cmd == 3'b001) begin
                    pipe_valid[0] <= 1'b1;
                    pipe_data[0] <= memory.exists(app_addr) ? memory[app_addr] : '0;
                end
            end else if (app_wdf_wren && !app_en) begin
                $error("write data without a command (this adapter never does that)");
            end

            if (corrupt && memory.exists(corrupt_word_address)) begin
                memory[corrupt_word_address] = memory[corrupt_word_address] ^ 1;
            end
        end
    end

    assign app_rd_data_valid = pipe_valid[READ_LATENCY-1];
    assign app_rd_data = pipe_data[READ_LATENCY-1];
    assign app_rd_data_end = app_rd_data_valid;

endmodule
