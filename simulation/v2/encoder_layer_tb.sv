// Bring-up step 4: one encoder layer of the DDR image, bit-exact against
// ImageMachine (scripts/v2/encoder_vectors.py), through the behavioural memory port
// with random stalls.
//
// For every case: load X through the host port, then single-step the layer's
// instructions; after each one read the destination buffer back and compare every
// word. Then load X again and run the whole layer in one go and compare the final X.
// Prints the clock count of every instruction.
`timescale 1ns / 1ps

module encoder_layer_tb;

    localparam integer ADDRESS_WIDTH = 27;
    localparam integer BUFFER_ADDRESS_WIDTH = 14;
    localparam string DIR = "vectors/encoder";

    logic clk = 1'b0;
    logic reset = 1'b1;
    always #5 clk = ~clk;

    logic start;
    logic [ADDRESS_WIDTH-1:0] program_address;
    logic [15:0] first_instruction, instruction_count, hidden;
    logic [7:0] token_count;
    logic busy, done, error, instruction_done;
    logic [15:0] instruction_index;

    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic [ADDRESS_WIDTH-1:0] read_request_address;
    logic [15:0] read_request_beats;
    logic [127:0] read_data;
    longint beats_delivered, requests_accepted;

    logic [2:0] host_buffer;
    logic host_write;
    logic [BUFFER_ADDRESS_WIDTH-1:0] host_address;
    logic [127:0] host_write_data, host_read_data;
    logic [15:0] host_write_enable;

    encoder_layer #(
        .TILE_OUT(12),
        .MAX_TOKENS(128),
        .MAX_HEAD_DIM(64),
        .MAX_HIDDEN(384)
    ) dut (
        .clk(clk),
        .reset(reset),
        .start(start),
        .program_address(program_address),
        .first_instruction(first_instruction),
        .instruction_count(instruction_count),
        .hidden(hidden),
        .token_count(token_count),
        .busy(busy),
        .done(done),
        .error(error),
        .instruction_done(instruction_done),
        .instruction_index(instruction_index),
        .read_request_valid(read_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(read_request_address),
        .read_request_beats(read_request_beats),
        .read_valid(read_valid),
        .read_ready(read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .host_buffer(host_buffer),
        .host_write(host_write),
        .host_address(host_address),
        .host_write_data(host_write_data),
        .host_write_enable(host_write_enable),
        .host_read_data(host_read_data)
    );

    memory_port_model #(
        .WORDS(1 << 21),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .STALL_PERCENT(20),
        .IMAGE({DIR, "/image.hex"})
    ) memory_inst (
        .clk(clk),
        .reset(reset),
        .read_request_valid(read_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(read_request_address),
        .read_request_beats(read_request_beats),
        .read_valid(read_valid),
        .read_ready(read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .beats_delivered(beats_delivered),
        .requests_accepted(requests_accepted)
    );

    // the memory port's read data must be taken when valid and ready
    always @(posedge clk) begin
        if (!reset && read_valid && read_ready === 1'bx) begin
            $fatal(1, "read_ready is X");
        end
    end

    int errors = 0;
    int total_words = 0;
    longint cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    task automatic host_write_word(input logic [2:0] b, input int address, input logic [127:0] data);
        @(negedge clk);
        host_buffer = b;
        host_address = BUFFER_ADDRESS_WIDTH'(address);
        host_write_data = data;
        host_write_enable = 16'hFFFF;
        host_write = 1'b1;
        @(negedge clk);
        host_write = 1'b0;
    endtask

    task automatic host_read_word(input logic [2:0] b, input int address, output logic [127:0] data);
        @(negedge clk);
        host_buffer = b;
        host_address = BUFFER_ADDRESS_WIDTH'(address);
        repeat (encoder_pkg::READ_LATENCY) @(negedge clk);
        data = host_read_data;
    endtask

    task automatic run(input int first, input int count, output longint clocks);
        longint t0;
        @(negedge clk);
        first_instruction = 16'(first);
        instruction_count = 16'(count);
        start = 1'b1;
        t0 = cycle;
        @(negedge clk);
        start = 1'b0;
        while (!done) @(negedge clk);
        clocks = cycle - t0;
        if (error) begin
            $fatal(1, "sequencer error at instruction %0d", instruction_index);
        end
    endtask

    initial begin
        int cases, fd, n, first, count, hid, prog, index, dst, nwords, r;
        logic [127:0] x0 [];
        logic [127:0] word, got;
        longint clocks;
        longint per_op [0:15];
        string path;

        start = 1'b0;
        host_write = 1'b0;
        host_buffer = '0;
        host_address = '0;
        host_write_data = '0;
        host_write_enable = '0;
        first_instruction = '0;
        instruction_count = '0;
        repeat (5) @(negedge clk);
        reset = 1'b0;

        fd = $fopen({DIR, "/cases.txt"}, "r");
        if (fd == 0) $fatal(1, "no vectors: run scripts/v2/encoder_vectors.py");
        r = $fscanf(fd, "%d", cases);
        $fclose(fd);

        for (int c = 0; c < cases; c++) begin
            int case_errors;
            longint layer_clocks;
            case_errors = 0;
            path = $sformatf("%s/case_%0d.txt", DIR, c);
            fd = $fopen(path, "r");
            r = $fscanf(fd, "%d %d %d %d %d", n, first, count, hid, prog);
            token_count = 8'(n);
            hidden = 16'(hid);
            program_address = ADDRESS_WIDTH'(prog);
            x0 = new[n * hid / 16];
            for (int w = 0; w < n * hid / 16; w++) begin
                r = $fscanf(fd, "%h", word);       // not straight into x0[w]: Verilator
                x0[w] = word;                      // drops %h into a dynamic-array element
            end
            for (int w = 0; w < n * hid / 16; w++) begin
                host_write_word(3'd0, w, x0[w]);
            end

            // single-step, compare the destination after every instruction
            for (int k = 0; k < count; k++) begin
                r = $fscanf(fd, "%d %d %d", index, dst, nwords);
                run(index, 1, clocks);
                per_op[k] = clocks;
                for (int w = 0; w < nwords; w++) begin
                    r = $fscanf(fd, "%h", word);
                    host_read_word(3'(dst), w, got);
                    total_words++;
                    if (got !== word) begin
                        if (case_errors < 5) begin
                            $display("case %0d instruction %0d buffer %0d word %0d: got %h expected %h",
                                     c, index, dst, w, got, word);
                        end
                        case_errors++;
                    end
                end
            end
            $fclose(fd);

            // whole layer in one run, compare the final X
            for (int w = 0; w < n * hid / 16; w++) begin
                host_write_word(3'd0, w, x0[w]);
            end
            run(first, count, layer_clocks);
            fd = $fopen(path, "r");
            r = $fscanf(fd, "%d %d %d %d %d", n, first, count, hid, prog);
            for (int w = 0; w < n * hid / 16; w++) r = $fscanf(fd, "%h", word);
            for (int k = 0; k < count; k++) begin
                r = $fscanf(fd, "%d %d %d", index, dst, nwords);
                for (int w = 0; w < nwords; w++) begin
                    r = $fscanf(fd, "%h", word);
                    if (k == count - 1) begin
                        host_read_word(3'(dst), w, got);
                        total_words++;
                        if (got !== word) begin
                            if (case_errors < 5) begin
                                $display("case %0d full run: X word %0d got %h expected %h", c, w, got, word);
                            end
                            case_errors++;
                        end
                    end
                end
            end
            $fclose(fd);

            $write("case %0d: %3d tokens, %0d mismatching words; clocks per instruction", c, n, case_errors);
            for (int k = 0; k < count; k++) $write(" %0d", per_op[k]);
            $display("; whole layer %0d", layer_clocks);
            errors += case_errors;
        end

        $display("memory: %0d requests, %0d beats", requests_accepted, beats_delivered);
        if (errors == 0) begin
            $display("PASS: encoder layer bit-exact, %0d cases, %0d words compared", cases, total_words);
        end else begin
            $display("FAIL: %0d mismatching words of %0d", errors, total_words);
        end
        $finish;
    end

    initial begin
        #2_000_000_000;
        $fatal(1, "timeout");
    end

endmodule
