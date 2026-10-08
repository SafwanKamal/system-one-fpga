// Behavioural AXI4 slave memory for simulating axi_memory_port.
//
// Random AR/AW/W ready, random gaps on R, reads served in order after a latency,
// one B response per write burst. Checks the AXI4 rules the master must keep:
// INCR bursts, ARLEN/AWLEN <= 255, full-width size, no burst crossing 4 KiB, WLAST
// on exactly the last beat of each write burst.
module axi_slave_model #(
    parameter integer ADDRESS_WIDTH = 40,
    parameter integer DATA_WIDTH = 128,
    parameter integer BUSY_PERCENT = 25,
    parameter integer READ_LATENCY = 30,
    // optional: memory contents at start, one word per line, word 0 at PRELOAD_BASE
    parameter string PRELOAD = "",
    parameter longint PRELOAD_BASE = 0
) (
    input logic clk,
    input logic reset,

    input logic [ADDRESS_WIDTH-1:0] araddr,
    input logic [7:0] arlen,
    input logic [2:0] arsize,
    input logic [1:0] arburst,
    input logic arvalid,
    output logic arready,
    output logic [DATA_WIDTH-1:0] rdata,
    output logic [1:0] rresp,
    output logic rlast,
    output logic rvalid,
    input logic rready,

    input logic [ADDRESS_WIDTH-1:0] awaddr,
    input logic [7:0] awlen,
    input logic [2:0] awsize,
    input logic [1:0] awburst,
    input logic awvalid,
    output logic awready,
    input logic [DATA_WIDTH-1:0] wdata,
    input logic [DATA_WIDTH/8-1:0] wstrb,
    input logic wlast,
    input logic wvalid,
    output logic wready,
    output logic [1:0] bresp,
    output logic bvalid,
    input logic bready,

    input logic corrupt,
    input logic [ADDRESS_WIDTH-1:0] corrupt_address
);

    localparam integer BEAT_BYTES = DATA_WIDTH / 8;

    logic [DATA_WIDTH-1:0] memory [logic [ADDRESS_WIDTH-1:0]];

    initial begin
        if (PRELOAD != "") begin
            int fd, r, n;
            logic [DATA_WIDTH-1:0] word;
            fd = $fopen(PRELOAD, "r");
            if (fd == 0) $fatal(1, "axi_slave_model: cannot open %s", PRELOAD);
            n = 0;
            while (!$feof(fd)) begin
                r = $fscanf(fd, "%h\n", word);
                if (r != 1) break;
                memory[ADDRESS_WIDTH'(PRELOAD_BASE + longint'(n) * BEAT_BYTES)] = word;
                n++;
            end
            $fclose(fd);
            $display("axi_slave_model: %0d words preloaded from %s", n, PRELOAD);
        end
    end

    // read bursts: address, beats, cycle when data may start
    logic [ADDRESS_WIDTH-1:0] read_queue_address [$];
    int read_queue_beats [$];
    longint read_queue_ready_at [$];
    logic [ADDRESS_WIDTH-1:0] write_queue_address [$];
    int write_queue_beats [$];
    int b_pending;
    longint cycle;

    logic [ADDRESS_WIDTH-1:0] r_address;
    int r_left;
    logic r_active;
    logic [ADDRESS_WIDTH-1:0] w_address;
    int w_left;
    logic w_active;

    function automatic void check_burst(input logic [ADDRESS_WIDTH-1:0] a, input logic [7:0] len,
                                        input logic [2:0] size, input logic [1:0] burst);
        if (burst != 2'b01) $error("burst type %0d, expected INCR", burst);
        if (size != $clog2(BEAT_BYTES)) $error("burst size %0d is not full width", size);
        if (a % BEAT_BYTES != 0) $error("address %h not beat aligned", a);
        if ((a / 4096) != ((a + (len + 1) * BEAT_BYTES - 1) / 4096))
            $error("burst at %h, %0d beats, crosses a 4 KiB boundary", a, len + 1);
    endfunction

    always_ff @(posedge clk) begin
        if (reset) begin
            arready <= 1'b0;
            awready <= 1'b0;
            wready <= 1'b0;
            rvalid <= 1'b0;
            bvalid <= 1'b0;
            r_active <= 1'b0;
            w_active <= 1'b0;
            b_pending <= 0;
            cycle <= 0;
            read_queue_address.delete();
            read_queue_beats.delete();
            read_queue_ready_at.delete();
            write_queue_address.delete();
            write_queue_beats.delete();
        end else begin
            cycle <= cycle + 1;
            arready <= ($urandom_range(99) >= BUSY_PERCENT);
            awready <= ($urandom_range(99) >= BUSY_PERCENT);
            wready <= ($urandom_range(99) >= BUSY_PERCENT);

            if (arvalid && arready) begin
                check_burst(araddr, arlen, arsize, arburst);
                read_queue_address.push_back(araddr);
                read_queue_beats.push_back(arlen + 1);
                read_queue_ready_at.push_back(cycle + READ_LATENCY);
            end
            if (awvalid && awready) begin
                check_burst(awaddr, awlen, awsize, awburst);
                write_queue_address.push_back(awaddr);
                write_queue_beats.push_back(awlen + 1);
            end

            // ---- R channel
            if (rvalid && rready) begin
                if (r_left == 1) begin
                    r_active = 1'b0;
                end else begin
                    r_address = r_address + BEAT_BYTES;
                    r_left = r_left - 1;
                end
            end
            if (!r_active && read_queue_address.size() > 0 && read_queue_ready_at[0] <= cycle) begin
                r_address = read_queue_address.pop_front();
                r_left = read_queue_beats.pop_front();
                void'(read_queue_ready_at.pop_front());
                r_active = 1'b1;
            end
            if (r_active && (!rvalid || rready)) begin
                rvalid <= ($urandom_range(99) >= BUSY_PERCENT);
                rdata <= memory.exists(r_address) ? memory[r_address] : '0;
                rlast <= (r_left == 1);
            end else if (!r_active) begin
                rvalid <= 1'b0;
            end

            // ---- W channel
            if (!w_active && write_queue_address.size() > 0) begin
                w_address = write_queue_address.pop_front();
                w_left = write_queue_beats.pop_front();
                w_active = 1'b1;
            end
            if (wvalid && wready) begin
                if (!w_active) begin
                    $error("W beat before its AW");
                end else begin
                    memory[w_address] = wdata;
                    if (wlast != (w_left == 1)) $error("WLAST wrong with %0d beats left", w_left);
                    if (w_left == 1) begin
                        w_active = 1'b0;
                        b_pending = b_pending + 1;
                    end else begin
                        w_address = w_address + BEAT_BYTES;
                        w_left = w_left - 1;
                    end
                end
            end

            // ---- B channel
            if (bvalid && bready) begin
                bvalid <= 1'b0;
            end else if (!bvalid && b_pending > 0) begin
                bvalid <= 1'b1;
                b_pending = b_pending - 1;
            end

            if (corrupt && memory.exists(corrupt_address)) begin
                memory[corrupt_address] = memory[corrupt_address] ^ 1;
            end
        end
    end

    assign rresp = 2'b00;
    assign bresp = 2'b00;

endmodule
