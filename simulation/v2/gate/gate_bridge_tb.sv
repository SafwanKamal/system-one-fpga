// Board-level test of the gate bridge at the RGMII pins.
//  * PHY models drive RGMII DDR into ports A/B (rx clocks 8.000 ns and 7.9992 ns, i.e.
//    -100 ppm, both asynchronous to the 125 MHz core clock) and decode the TX pins.
//  * MDIO PHY models (address 4 on A, 6 on B) answer reads and record the init writes.
//  * Every frame from gate_bridge_frames.txt is sent with a preamble and a correct (or
//    deliberately corrupted) FCS; a forwarded frame must appear on the other port
//    byte-identical including FCS, a dropped frame must not appear at all.
module gate_bridge_tb;
    import gate_eth_pkg::*;

    logic clk125 = 0;
    always #4 clk125 = ~clk125;
    logic rst = 1;

    logic a_rxc = 0, b_rxc = 0;
`ifdef SPEED100
    always #20.0 a_rxc = ~a_rxc;        // 25 MHz
    always #19.998 b_rxc = ~b_rxc;
    localparam logic [15:0] PHYSTS = 16'h6C02;   // 100 Mb/s, full duplex, link
`else
    always #4.0 a_rxc = ~a_rxc;
    always #3.9996 b_rxc = ~b_rxc;
    localparam logic [15:0] PHYSTS = 16'hAC02;   // 1000 Mb/s, full duplex, link
`endif
    logic [3:0] a_rd = 0, b_rd = 0;
    logic a_rx_ctl = 0, b_rx_ctl = 0;
    logic a_txc, b_txc, a_tx_ctl, b_tx_ctl;
    logic [3:0] a_td, b_td;
    logic a_rst_n, b_rst_n, a_mdc, b_mdc, a_mdio_o, b_mdio_o, a_mdio_t, b_mdio_t;
    logic a_mdio_i, b_mdio_i;
    logic [7:0] st_addr = 0;
    logic [31:0] st_rdata;

    gate_bridge_io #(.MDIO_DIV(2), .MDIO_RESET_CYC(50), .MDIO_SETTLE_CYC(100),
                     .MDIO_POLL_CYC(3000), .MS_DIV(32'h7FFF_FFFF)) dut (
        .clk125(clk125), .rst(rst), .clk_status(32'h3),
        .a_rxc(a_rxc), .a_rd(a_rd), .a_rx_ctl(a_rx_ctl), .a_txc(a_txc), .a_td(a_td), .a_tx_ctl(a_tx_ctl),
        .a_rst_n(a_rst_n), .a_mdc(a_mdc), .a_mdio_o(a_mdio_o), .a_mdio_t(a_mdio_t), .a_mdio_i(a_mdio_i),
        .b_rxc(b_rxc), .b_rd(b_rd), .b_rx_ctl(b_rx_ctl), .b_txc(b_txc), .b_td(b_td), .b_tx_ctl(b_tx_ctl),
        .b_rst_n(b_rst_n), .b_mdc(b_mdc), .b_mdio_o(b_mdio_o), .b_mdio_t(b_mdio_t), .b_mdio_i(b_mdio_i),
        .st_addr(st_addr), .st_rdata(st_rdata));

    // ---------------------------------------------------------------- MDIO PHY models
    logic [15:0] regs_a [32], regs_b [32];
    logic [15:0] ext_a [256], ext_b [256];
    logic drv_a = 0, bit_a = 1, drv_b = 0, bit_b = 1;
    assign a_mdio_i = a_mdio_t ? (drv_a ? bit_a : 1'b1) : a_mdio_o;
    assign b_mdio_i = b_mdio_t ? (drv_b ? bit_b : 1'b1) : b_mdio_o;

    task automatic mdio_model(input bit is_b, input logic [4:0] myaddr);
        int ones; logic [13:0] hdr; int hb; logic [15:0] wd; int k;
        logic [4:0] pa, ra; logic [1:0] op; logic [15:0] rdv;
        forever begin
            // wait for 32 ones then ST=01
            ones = 0;
            while (1) begin
                if (is_b) @(posedge b_mdc); else @(posedge a_mdc);
                if ((is_b ? b_mdio_i : a_mdio_i) == 1'b1) ones++;
                else if (ones >= 32) break;
                else ones = 0;
            end
            // we just saw ST bit0 = 0; read 13 more header bits: ST1, OP(2), PA(5), RA(5)
            for (hb = 0; hb < 13; hb++) begin
                if (is_b) @(posedge b_mdc); else @(posedge a_mdc);
                hdr[12 - hb] = is_b ? b_mdio_i : a_mdio_i;
            end
            op = hdr[11:10]; pa = hdr[9:5]; ra = hdr[4:0];
            if (op == 2'b10) begin  // read
                if (pa == myaddr) begin
                    if (ra == 5'h0E && (is_b ? regs_b[5'h0D] : regs_a[5'h0D]) == 16'h401F)
                        rdv = is_b ? ext_b[(is_b ? regs_b[5'h0E] : regs_a[5'h0E]) & 8'hFF]
                                   : ext_a[regs_a[5'h0E] & 8'hFF];
                    else rdv = is_b ? regs_b[ra] : regs_a[ra];
                    // IEEE 802.3 cl.22: the PHY drives in response to MDC rising edges and the
                    // STA samples on rising edges.  After the rising edge of TA1 drive TA2 = 0,
                    // after the rising edge of TA2 drive D15, and so on.
                    if (is_b) @(posedge b_mdc); else @(posedge a_mdc);     // rising edge of TA1
                    #10;
                    if (is_b) begin drv_b = 1; bit_b = 0; end else begin drv_a = 1; bit_a = 0; end
                    for (k = 15; k >= 0; k--) begin
                        if (is_b) @(posedge b_mdc); else @(posedge a_mdc);
                        #10;
                        if (is_b) bit_b = rdv[k]; else bit_a = rdv[k];
                    end
                    if (is_b) @(posedge b_mdc); else @(posedge a_mdc);
                    #10;
                    if (is_b) drv_b = 0; else drv_a = 0;
                end
            end else begin           // write: TA(2) + data(16)
                for (k = 0; k < 18; k++) begin
                    if (is_b) @(posedge b_mdc); else @(posedge a_mdc);
                    if (k >= 2) wd[17 - k] = is_b ? b_mdio_i : a_mdio_i;
                end
                if (pa == myaddr) begin
                    if (ra == 5'h0E && (is_b ? regs_b[5'h0D] : regs_a[5'h0D]) == 16'h401F) begin
                        if (is_b) ext_b[regs_b[5'h0E] & 8'hFF] = wd; else ext_a[regs_a[5'h0E] & 8'hFF] = wd;
                    end else begin
                        if (is_b) regs_b[ra] = wd; else regs_a[ra] = wd;
                    end
                end
            end
        end
    endtask

    // ---------------------------------------------------------------- RGMII drive
    task automatic send_byte(input bit is_b, input logic [7:0] b, input logic dv);
`ifdef SPEED100
        // one nibble per clock (low nibble first), same value on both edges
        for (int h = 0; h < 2; h++) begin
            if (is_b) begin @(negedge b_rxc); #2; b_rd = h ? b[7:4] : b[3:0]; b_rx_ctl = dv; end
            else      begin @(negedge a_rxc); #2; a_rd = h ? b[7:4] : b[3:0]; a_rx_ctl = dv; end
        end
`else
        // low nibble + DV stable around the rising edge, high nibble + (DV^ER) around falling
        if (is_b) begin
            @(negedge b_rxc); #2; b_rd = b[3:0]; b_rx_ctl = dv;
            @(posedge b_rxc); #2; b_rd = b[7:4]; b_rx_ctl = dv;
        end else begin
            @(negedge a_rxc); #2; a_rd = b[3:0]; a_rx_ctl = dv;
            @(posedge a_rxc); #2; a_rd = b[7:4]; a_rx_ctl = dv;
        end
`endif
    endtask

    byte unsigned frame [2048];
    task automatic send_frame(input bit is_b, input int len, input bit good_fcs);
        logic [31:0] c; logic [31:0] fcs;
        c = 32'hFFFF_FFFF;
        for (int i = 0; i < len; i++) c = crc_byte(c, frame[i]);
        fcs = ~c;
        if (!good_fcs) fcs = fcs ^ 32'h0000_0100;
        for (int i = 0; i < 7; i++) send_byte(is_b, 8'h55, 1);
        send_byte(is_b, 8'hD5, 1);
        for (int i = 0; i < len; i++) send_byte(is_b, frame[i], 1);
        for (int i = 0; i < 4; i++) send_byte(is_b, fcs[8*i +: 8], 1);
        for (int i = 0; i < 12; i++) send_byte(is_b, 8'h00, 0);
    endtask

    // ---------------------------------------------------------------- TX capture
    byte unsigned out_a [$], out_b [$];
    int nout_a = 0, nout_b = 0;
    byte unsigned cap_a [2048], cap_b [2048];
    int len_a [$], len_b [$];
    task automatic tx_monitor(input bit is_b);
        logic [3:0] lo; logic en; int n; bit infr;
        infr = 0; n = 0;
        forever begin
`ifdef SPEED100
            // nibble per TXC rising edge; two nibbles per byte
            if (is_b) @(posedge b_txc); else @(posedge a_txc);
            #1; lo = is_b ? b_td : a_td; en = is_b ? b_tx_ctl : a_tx_ctl;
            if (en) begin
                if (is_b) @(posedge b_txc); else @(posedge a_txc);
                #1;
            end
`else
            if (is_b) @(posedge b_txc); else @(posedge a_txc);
            #1; lo = is_b ? b_td : a_td; en = is_b ? b_tx_ctl : a_tx_ctl;
            if (is_b) @(negedge b_txc); else @(negedge a_txc);
            #1;
`endif
            if (en) begin
                if (is_b) cap_b[n] = {b_td, lo}; else cap_a[n] = {a_td, lo};
                n++; infr = 1;
            end else if (infr) begin
                // strip preamble/SFD (8 bytes), store frame incl FCS
                for (int i = 8; i < n; i++) if (is_b) out_b.push_back(cap_b[i]); else out_a.push_back(cap_a[i]);
                if (is_b) len_b.push_back(n - 8); else len_a.push_back(n - 8);
                n = 0; infr = 0;
            end
        end
    endtask

    // ---------------------------------------------------------------- main
    int fd, r, count, errors, nfwd;
    int unsigned f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class, bv;
    string path;
    logic [31:0] c2, fcs2;

    task automatic read_status(input logic [7:0] a, output logic [31:0] v);
        @(negedge clk125); st_addr = a; @(posedge clk125); @(posedge clk125); #1; v = st_rdata;
    endtask

    initial begin
        logic [31:0] v;
        for (int i = 0; i < 32; i++) begin regs_a[i] = 0; regs_b[i] = 0; end
        regs_a[2] = 16'h2000; regs_a[3] = 16'hA231; regs_a[1] = 16'h796D; regs_a[5'h11] = PHYSTS;
        regs_b[2] = 16'h2000; regs_b[3] = 16'hA231; regs_b[1] = 16'h796D; regs_b[5'h11] = PHYSTS;
        for (int i = 0; i < 256; i++) begin ext_a[i] = 0; ext_b[i] = 0; end
        fork
            mdio_model(0, 5'd4);
            mdio_model(1, 5'd6);
            tx_monitor(0);
            tx_monitor(1);
        join_none
        repeat (10) @(posedge clk125);
        rst = 0;
        // wait for MDIO bring-up (scan + config) on both PHYs
        repeat (60000) @(posedge clk125);
        $display("MDIO A: RGMIICTL=%h RGMIIDCTL=%h ANAR=%h CFG1=%h BMCR=%h",
                 ext_a[8'h32], ext_a[8'h86], regs_a[4], regs_a[9], regs_a[0]);
        $display("MDIO B: RGMIICTL=%h RGMIIDCTL=%h ANAR=%h CFG1=%h BMCR=%h",
                 ext_b[8'h32], ext_b[8'h86], regs_b[4], regs_b[9], regs_b[0]);
        read_status(8'd49, v); $display("status A ctrl=%h", v);
        read_status(8'd50, v); $display("status A id=%h", v);
        read_status(8'd51, v); $display("status A bmsr/physts=%h", v);
        read_status(8'd52, v); $display("status A rgmiictl/attempts=%h", v);
        read_status(8'd53, v); $display("status B ctrl=%h", v);

        if (!$value$plusargs("frames=%s", path)) path = "gate_bridge_frames.txt";
        fd = $fopen(path, "r");
        count = 0; errors = 0; nfwd = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h %h %h %h %h", f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class);
            if (r != 7) break;
            for (int b = 0; b < f_len; b++) begin r = $fscanf(fd, "%h", bv); frame[b] = bv[7:0]; end
            send_frame(f_dir[0], f_len, f_fcs[0]);
`ifdef SPEED100
            repeat (4000) @(posedge clk125);  // 100 Mb/s: ~10x longer per frame
`else
            repeat (400) @(posedge clk125);   // > store + decide + transmit for <= 128-byte frames
`endif
            begin
                int got; got = f_dir[0] ? len_a.size() : len_b.size();
                if (e_fwd[0]) begin
                    if (got != 1) begin
                        errors++; if (errors < 10) $display("frame %0d: expected forward, got %0d frames", count, got);
                    end else begin
                        int L; bit ok;
                        L = f_dir[0] ? len_a.pop_front() : len_b.pop_front();
                        c2 = 32'hFFFF_FFFF;
                        for (int i = 0; i < f_len; i++) c2 = crc_byte(c2, frame[i]);
                        fcs2 = ~c2;
                        ok = (L == f_len + 4);
                        for (int i = 0; i < L; i++) begin
                            byte unsigned x; x = f_dir[0] ? out_a.pop_front() : out_b.pop_front();
                            if (i < f_len && x != frame[i]) ok = 0;
                            if (i >= f_len && x != fcs2[8*(i - f_len) +: 8]) ok = 0;
                        end
                        if (!ok) begin errors++; if (errors < 10) $display("frame %0d: forwarded bytes differ (len %0d vs %0d)", count, L, f_len + 4); end
                        nfwd++;
                    end
                end else if (got != 0) begin
                    errors++; if (errors < 10) $display("frame %0d: expected drop (rule %0d), but it was forwarded", count, e_rule);
                    while (len_a.size() > 0) begin int L; L = len_a.pop_front(); repeat (L) void'(out_a.pop_front()); end
                    while (len_b.size() > 0) begin int L; L = len_b.pop_front(); repeat (L) void'(out_b.pop_front()); end
                end
            end
            count++;
        end
        read_status(8'd8, v);  $display("A->B loaded %0d", v);
        read_status(8'd9, v);  $display("A->B forwarded %0d", v);
        read_status(8'd10, v); $display("A->B dropped %0d", v);
        read_status(8'd13, v); $display("B->A forwarded %0d", v);
        read_status(8'd3, v);  $display("rx A bad %0d", v);
        read_status(8'd4, v);  $display("rx A overflow %0d", v);
        read_status(8'd16, v); $display("latency last %0d cycles", v);
        read_status(8'd17, v); $display("latency min %0d cycles", v);
        read_status(8'd18, v); $display("latency max %0d cycles", v);
        $display("gate_bridge_tb: %0d frames, %0d forwarded and byte-identical, %0d errors", count, nfwd, errors);
        $finish;
    end
endmodule
