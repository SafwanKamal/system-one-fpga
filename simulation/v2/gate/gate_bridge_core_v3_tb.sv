// Bridge-core level test of the v3 gate with byte mutation.  Bytes are driven straight into the receive side
// (preamble, frame, FCS) and the transmit side is captured.  For every frame the expected transmitted frame (none,
// the original, a mutated request or a restored reply) comes from the Python model; the FCS of a transmitted frame
// must equal CRC-32 over the expected bytes, which checks the regenerated FCS of every mutated frame.
module gate_bridge_core_v3_tb;
    import gate_eth_pkg::*;

    logic clk = 0;
    always #4 clk = ~clk;
    logic rst = 1;

    logic [7:0] rxd_a = 0, rxd_b = 0;
    logic dv_a = 0, dv_b = 0;
    logic [7:0] txd_a, txd_b;
    logic en_a, en_b;
    logic [7:0] st_addr = 0;
    logic [31:0] st_rdata;
    logic [31:0] st_ext [16];

    gate_bridge_core_v3 #(.MS_DIV(32'h7FFF_FFFF)) dut (
        .clk(clk), .rst(rst),
        .rxc_a(clk), .rrst_a(rst), .rxd_a(rxd_a), .rx_dv_a(dv_a), .rx_er_a(1'b0), .rx_ce_a(1'b1),
        .rxc_b(clk), .rrst_b(rst), .rxd_b(rxd_b), .rx_dv_b(dv_b), .rx_er_b(1'b0), .rx_ce_b(1'b1),
        .txd_a(txd_a), .txd_b(txd_b), .tx_en_a(en_a), .tx_en_b(en_b), .tx_ce_a(1'b1), .tx_ce_b(1'b1),
        .st_addr(st_addr), .st_rdata(st_rdata), .st_ext(st_ext));

    // ---------------------------------------------------------------- transmit capture
    byte unsigned cap_a [2048], cap_b [2048];
    int cap_len_a = 0, cap_len_b = 0;
    logic in_a = 0, in_b = 0, have_a = 0, have_b = 0;
    int n_a, n_b;
    always @(posedge clk) begin
        if (en_a) begin
            if (!in_a) begin if (txd_a == 8'hD5) begin in_a <= 1; n_a = 0; end end
            else begin cap_a[n_a] = txd_a; n_a++; end
        end else if (in_a) begin in_a <= 0; cap_len_a = n_a; have_a <= 1; end
        if (en_b) begin
            if (!in_b) begin if (txd_b == 8'hD5) begin in_b <= 1; n_b = 0; end end
            else begin cap_b[n_b] = txd_b; n_b++; end
        end else if (in_b) begin in_b <= 0; cap_len_b = n_b; have_b <= 1; end
    end

    // ---------------------------------------------------------------- frame drive
    byte unsigned inf [2048], outf [2048];
    task automatic drive(input bit is_b, input logic [7:0] b, input logic dv);
        @(negedge clk);
        if (is_b) begin rxd_b = b; dv_b = dv; end else begin rxd_a = b; dv_a = dv; end
    endtask

    task automatic send_frame(input bit is_b, input int len, input bit good_fcs);
        logic [31:0] c, fcs;
        c = 32'hFFFF_FFFF;
        for (int i = 0; i < len; i++) c = crc_byte(c, inf[i]);
        fcs = ~c;
        if (!good_fcs) fcs = fcs ^ 32'h0000_0100;
        for (int i = 0; i < 7; i++) drive(is_b, 8'h55, 1);
        drive(is_b, 8'hD5, 1);
        for (int i = 0; i < len; i++) drive(is_b, inf[i], 1);
        for (int i = 0; i < 4; i++) drive(is_b, fcs[8 * i +: 8], 1);
        for (int i = 0; i < 12; i++) drive(is_b, 8'h00, 0);
    endtask

    // ---------------------------------------------------------------- run
    int fd, r, count, errors, tx_count, mut_seen, rst_seen, lat, bad_bytes;
    int unsigned f_dir, f_fcs, f_len, f_tx, f_olen, bv;
    string path;
    logic [31:0] fcs_e, crc_e;
    int exp_len, got_len;

    initial begin
        for (int i = 0; i < 16; i++) st_ext[i] = 0;
        if (!$value$plusargs("frames=%s", path)) path = "gate_v3_bridge_rec.txt";
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %s", path); $finish; end
        repeat (6) @(posedge clk);
        rst = 0;
        repeat (4) @(posedge clk);
        count = 0; errors = 0; tx_count = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h %h %h", f_dir, f_fcs, f_len, f_tx, f_olen);
            if (r != 5) break;
            for (int i = 0; i < f_len; i++) begin r = $fscanf(fd, "%h", bv); inf[i] = bv[7:0]; end
            for (int i = 0; i < f_olen; i++) begin r = $fscanf(fd, "%h", bv); outf[i] = bv[7:0]; end
            have_a = 0; have_b = 0;
            send_frame(f_dir[0], f_len, f_fcs[0]);
            lat = 0;
            if (f_tx) begin
                while (!(f_dir[0] ? have_a : have_b) && lat < 20000) begin @(posedge clk); lat++; end
                repeat (20) @(posedge clk);
                if (!(f_dir[0] ? have_a : have_b)) begin
                    errors++;
                    if (errors < 12) $display("MISSING frame %0d dir %0d: expected a transmission", count, f_dir);
                end else begin
                    got_len = f_dir[0] ? cap_len_a : cap_len_b;
                    exp_len = f_olen + 4;
                    crc_e = 32'hFFFF_FFFF;
                    for (int i = 0; i < f_olen; i++) crc_e = crc_byte(crc_e, outf[i]);
                    fcs_e = ~crc_e;
                    bad_bytes = 0;
                    if (got_len != exp_len) bad_bytes = -1;
                    else begin
                        for (int i = 0; i < f_olen; i++)
                            if ((f_dir[0] ? cap_a[i] : cap_b[i]) !== outf[i]) bad_bytes++;
                        for (int i = 0; i < 4; i++)
                            if ((f_dir[0] ? cap_a[f_olen + i] : cap_b[f_olen + i]) !== fcs_e[8 * i +: 8]) bad_bytes++;
                    end
                    if (bad_bytes != 0) begin
                        errors++;
                        if (errors < 12) $display("MISMATCH frame %0d dir %0d: length got %0d exp %0d, %0d byte differences",
                                                  count, f_dir, got_len, exp_len, bad_bytes);
                    end
                    tx_count++;
                end
                if (f_dir[0] ? have_b : have_a) begin
                    errors++;
                    if (errors < 12) $display("WRONG PORT frame %0d dir %0d", count, f_dir);
                end
            end else begin
                repeat (1500) @(posedge clk);
                if (have_a || have_b) begin
                    errors++;
                    if (errors < 12) $display("UNEXPECTED transmission frame %0d dir %0d", count, f_dir);
                end
            end
            count++;
        end
        @(negedge clk); st_addr = 8'd28; repeat (3) @(posedge clk); mut_seen = st_rdata;
        @(negedge clk); st_addr = 8'd29; repeat (3) @(posedge clk); rst_seen = st_rdata;
        $display("gate_bridge_core_v3_tb: %0d frames, %0d transmitted, %0d mismatches; hardware counters: %0d mutated requests, %0d restored replies",
                 count, tx_count, errors, mut_seen, rst_seen);
        $finish;
    end
endmodule
