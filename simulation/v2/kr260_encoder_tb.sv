// The KR260 PL block (rtl/v2/platform/kr260/kr260_encoder.sv) as the ARM would use
// it: the image already in the PS DDR (AXI4 slave model, preloaded, random stalls),
// the token ids written next to it, a run started through the AXI4-Lite registers,
// DONE polled, X compared word for word with ImageMachine. Vectors:
// scripts/v2/kr260_vectors.py. `make kr260`.
`timescale 1ns / 1ps

module kr260_encoder_tb;

    localparam string DIR = "vectors/kr260";
    localparam integer AW = 40;

    logic clk = 1'b0;
    logic reset_n = 1'b0;
    always #5 clk = ~clk;                       // pl_clk0 at 100 MHz in this testbench

    logic [7:0] awaddr, araddr;
    logic awvalid, awready, wvalid, wready, bvalid, bready, arvalid, arready, rvalid, rready;
    logic [31:0] wdata, rdata;
    logic [1:0] bresp, rresp;

    logic [AW-1:0] m_araddr, m_awaddr;
    logic [7:0] m_arlen, m_awlen;
    logic [2:0] m_arsize, m_awsize;
    logic [1:0] m_arburst, m_awburst, m_rresp, m_bresp;
    logic m_arvalid, m_arready, m_rlast, m_rvalid, m_rready, m_awvalid, m_awready;
    logic m_wlast, m_wvalid, m_wready, m_bvalid, m_bready;
    logic [127:0] m_rdata, m_wdata;
    logic [15:0] m_wstrb;
    logic irq, memory_error;

    kr260_encoder #(.TILE_OUT(32), .ADDRESS_WIDTH(AW)) dut (
        .clk(clk), .reset_n(reset_n),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(4'hF), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(rready),
        .m_axi_araddr(m_araddr), .m_axi_arlen(m_arlen), .m_axi_arsize(m_arsize),
        .m_axi_arburst(m_arburst), .m_axi_arvalid(m_arvalid), .m_axi_arready(m_arready),
        .m_axi_rdata(m_rdata), .m_axi_rresp(m_rresp), .m_axi_rlast(m_rlast),
        .m_axi_rvalid(m_rvalid), .m_axi_rready(m_rready),
        .m_axi_awaddr(m_awaddr), .m_axi_awlen(m_awlen), .m_axi_awsize(m_awsize),
        .m_axi_awburst(m_awburst), .m_axi_awvalid(m_awvalid), .m_axi_awready(m_awready),
        .m_axi_wdata(m_wdata), .m_axi_wstrb(m_wstrb), .m_axi_wlast(m_wlast),
        .m_axi_wvalid(m_wvalid), .m_axi_wready(m_wready),
        .m_axi_bresp(m_bresp), .m_axi_bvalid(m_bvalid), .m_axi_bready(m_bready),
        .irq(irq), .memory_error(memory_error)
    );

    longint image_base;
    initial begin
        int fd, r, n;
        fd = $fopen({DIR, "/cases.txt"}, "r");
        if (fd == 0) $fatal(1, "no vectors: run scripts/v2/kr260_vectors.py");
        r = $fscanf(fd, "%d %d", n, image_base);
        $fclose(fd);
    end

    axi_slave_model #(
        .ADDRESS_WIDTH(AW), .DATA_WIDTH(128), .BUSY_PERCENT(25), .READ_LATENCY(40),
        .PRELOAD({DIR, "/image.hex"}), .PRELOAD_BASE(64'h6000_0000)
    ) model_inst (
        .clk(clk), .reset(!reset_n),
        .araddr(m_araddr), .arlen(m_arlen), .arsize(m_arsize), .arburst(m_arburst),
        .arvalid(m_arvalid), .arready(m_arready), .rdata(m_rdata), .rresp(m_rresp),
        .rlast(m_rlast), .rvalid(m_rvalid), .rready(m_rready),
        .awaddr(m_awaddr), .awlen(m_awlen), .awsize(m_awsize), .awburst(m_awburst),
        .awvalid(m_awvalid), .awready(m_awready), .wdata(m_wdata), .wstrb(m_wstrb),
        .wlast(m_wlast), .wvalid(m_wvalid), .wready(m_wready), .bresp(m_bresp),
        .bvalid(m_bvalid), .bready(m_bready), .corrupt(1'b0), .corrupt_address('0)
    );

    task automatic axil_write(input logic [7:0] a, input logic [31:0] d);
        @(negedge clk);
        awaddr = a; wdata = d; awvalid = 1'b1; wvalid = 1'b1; bready = 1'b1;
        do @(posedge clk); while (!(awready));
        @(negedge clk);
        awvalid = 1'b0; wvalid = 1'b0;
        while (!bvalid) @(negedge clk);
        @(negedge clk);
        bready = 1'b0;
    endtask

    task automatic axil_read(input logic [7:0] a, output logic [31:0] d);
        @(negedge clk);
        araddr = a; arvalid = 1'b1; rready = 1'b1;
        do @(posedge clk); while (!arready);
        @(negedge clk);
        arvalid = 1'b0;
        while (!rvalid) @(negedge clk);
        d = rdata;
        @(negedge clk);
        rready = 1'b0;
    endtask

    initial begin
        int cases, fd, r, n, hidden, errors, total;
        longint program_address, ids_address, result_address;
        logic [127:0] word;
        logic [31:0] value, status, encoder_clocks, request_clocks, stopped;
        string path;
        awvalid = 0; wvalid = 0; bready = 0; arvalid = 0; rready = 0; awaddr = 0; araddr = 0; wdata = 0;
        errors = 0;
        total = 0;
        repeat (10) @(negedge clk);
        reset_n = 1'b1;
        repeat (5) @(negedge clk);

        axil_read(8'h14, value);
        if (value != 32'h5359_5332) $fatal(1, "ID register reads %h", value);
        axil_read(8'h18, value);
        $display("BUILD register %h (TILE_OUT %0d)", value, value[31:24]);

        fd = $fopen({DIR, "/cases.txt"}, "r");
        r = $fscanf(fd, "%d", cases);
        $fclose(fd);
        for (int c = 0; c < cases; c++) begin
            int bad;
            path = $sformatf("%s/case_%0d.txt", DIR, c);
            fd = $fopen(path, "r");
            r = $fscanf(fd, "%d %d %d %d %d", n, hidden, program_address, ids_address, result_address);
            // the ARM writes the ids into its buffer
            for (int w = 0; w < (2 * n + 15) / 16; w++) begin
                r = $fscanf(fd, "%h", word);
                model_inst.memory[AW'(ids_address + 16 * w)] = word;
            end
            axil_write(8'h20, 32'(program_address));
            axil_write(8'h24, {16'(hidden), 16'(n)});
            axil_write(8'h28, 32'(ids_address));
            axil_write(8'h2C, 32'(result_address));
            axil_write(8'h00, 32'd1);
            do begin
                repeat (200) @(negedge clk);
                axil_read(8'h00, value);
            end while (value[1] == 1'b0);
            if (!irq) begin
                $display("case %0d: irq not raised with DONE", c);
                errors++;
            end
            axil_read(8'h04, status);
            axil_read(8'h08, encoder_clocks);
            axil_read(8'h0C, request_clocks);
            axil_read(8'h10, stopped);
            axil_write(8'h00, 32'd2);
            if (irq) begin
                $display("case %0d: irq still high after clearing DONE", c);
                errors++;
            end
            bad = 0;
            for (int w = 0; w < n * hidden / 16; w++) begin
                logic [127:0] got;
                r = $fscanf(fd, "%h", word);
                got = model_inst.memory.exists(AW'(result_address + 16 * w))
                      ? model_inst.memory[AW'(result_address + 16 * w)] : 'x;
                total++;
                if (got !== word) begin
                    if (bad < 3) $display("case %0d: X word %0d got %h expected %h", c, w, got, word);
                    bad++;
                end
            end
            $fclose(fd);
            errors += bad + (status != 0 ? 1 : 0);
            $display("case %0d: %3d tokens, status %0d, stopped at %0d, %0d mismatching words; clocks: encoder %0d, request %0d",
                     c, n, status, stopped, bad, encoder_clocks, request_clocks);
        end
        if (memory_error) begin
            $display("AXI error response seen");
            errors++;
        end
        if (errors == 0) $display("PASS: KR260 block bit-exact, %0d cases, %0d words compared", cases, total);
        else $display("FAIL: %0d errors", errors);
        $finish;
    end

    initial begin
        #20_000_000_000;
        $fatal(1, "timeout");
    end

endmodule
