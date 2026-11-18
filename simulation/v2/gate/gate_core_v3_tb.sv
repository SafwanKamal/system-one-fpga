// Streams Modbus/TCP traffic through gate_core_v3 and checks, for every frame, the decision (forward, rule,
// class), the 17-field state signature and the byte-mutation descriptor against frames_v3.GateV3Model
// (vectors from scripts/v2/gate_v3_vectors.py).
module gate_core_v3_tb;
    logic clk = 0;
    always #4 clk = ~clk;   // 125 MHz

    logic        rst = 1;
    logic        s_valid = 0, s_last = 0, s_dir = 0, s_fcs_ok = 0;
    logic [7:0]  s_data = 0;
    logic [31:0] t_ms = 0;
    logic        d_valid, d_forward;
    logic [4:0]  d_rule;
    logic [2:0]  d_class;
    logic [15:0] d_txid;
    logic [7:0]  d_fc;
    logic [1:0]  d_patch;
    logic [7:0]  d_pfc, d_pcode;
    logic [15:0] d_pcsum;
    logic [10:0] d_off_fc, d_off_code, d_off_csum;
    logic signed [15:0] st_lvl10;
    logic        st_lvl_ok;
    logic [15:0] st_v0 [4];
    logic [15:0] st_v1m [4];
    logic [3:0]  st_unc, st_wild, st_npend, st_nreads, st_ndenied;
    logic [2:0]  st_nstarts;
    logic [31:0] st_start_last;

    gate_core_v3 dut (.*);

    int fd, r, count, errors, sig_errors, patch_errors, fwd_count, b, gap, lat, max_lat;
    int unsigned f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class, byte_v;
    int unsigned sg [17];
    int unsigned pf [7];
    byte unsigned frame [2048];
    string path;
    logic [31:0] got [17];

    initial begin
        if (!$value$plusargs("frames=%s", path)) path = "gate_v3_frames.txt";
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %s", path); $finish; end
        repeat (4) @(posedge clk);
        rst = 0;
        count = 0; errors = 0; sig_errors = 0; patch_errors = 0; fwd_count = 0; max_lat = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h %h %h %h %h", f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class);
            if (r != 7) break;
            for (int i = 0; i < 17; i++) r = $fscanf(fd, "%h", sg[i]);
            for (int i = 0; i < 7; i++) r = $fscanf(fd, "%h", pf[i]);
            for (b = 0; b < f_len; b++) begin
                r = $fscanf(fd, "%h", byte_v);
                frame[b] = byte_v[7:0];
            end
            for (b = 0; b < f_len; b++) begin
                @(negedge clk);
                s_valid = 1; s_data = frame[b]; s_dir = f_dir[0]; t_ms = f_t;
                s_last = (b == f_len - 1); s_fcs_ok = f_fcs[0];
            end
            @(negedge clk);
            s_valid = 0; s_last = 0;
            lat = 0;
            while (!d_valid) begin
                @(posedge clk); #1; lat++;
                if (lat > 1500) begin $display("TIMEOUT frame %0d", count); $finish; end
            end
            if (lat > max_lat) max_lat = lat;
            if (d_forward !== e_fwd[0] || d_rule !== e_rule[4:0] || d_class !== e_class[2:0]) begin
                errors++;
                if (errors < 12)
                    $display("MISMATCH frame %0d dir %0d: got fwd=%0d rule=%0d class=%0d exp fwd=%0d rule=%0d class=%0d",
                             count, f_dir, d_forward, d_rule, d_class, e_fwd, e_rule, e_class);
            end
            got[0] = {16'd0, st_lvl10}; got[1] = {31'd0, st_lvl_ok};
            for (int i = 0; i < 4; i++) begin got[2 + i] = {16'd0, st_v0[i]}; got[6 + i] = {16'd0, st_v1m[i]}; end
            got[10] = {28'd0, st_unc}; got[11] = {28'd0, st_wild}; got[12] = {28'd0, st_npend};
            got[13] = {28'd0, st_nreads}; got[14] = {29'd0, st_nstarts}; got[15] = st_start_last;
            got[16] = {28'd0, st_ndenied};
            for (int i = 0; i < 17; i++) begin
                if (got[i] !== sg[i]) begin
                    sig_errors++;
                    if (sig_errors < 12)
                        $display("SIG MISMATCH frame %0d field %0d: got %0h exp %0h (rule exp %0d)", count, i, got[i], sg[i], e_rule);
                    break;
                end
            end
            // byte-mutation descriptor
            if (d_patch !== pf[0][1:0] ||
                (pf[0] != 0 && (d_pfc !== pf[1][7:0] || d_pcode !== pf[2][7:0] || d_pcsum !== pf[3][15:0] ||
                                d_off_fc !== pf[4][10:0] || d_off_code !== pf[5][10:0] || d_off_csum !== pf[6][10:0]))) begin
                patch_errors++;
                if (patch_errors < 12)
                    $display("PATCH MISMATCH frame %0d: got kind=%0d fc=%0h code=%0h csum=%0h off=%0d/%0d/%0d exp kind=%0d fc=%0h code=%0h csum=%0h off=%0d/%0d/%0d",
                             count, d_patch, d_pfc, d_pcode, d_pcsum, d_off_fc, d_off_code, d_off_csum,
                             pf[0], pf[1], pf[2], pf[3], pf[4], pf[5], pf[6]);
            end
            if (d_forward) fwd_count++;
            count++;
            gap = 12;
            repeat (gap) @(posedge clk);
        end
        $display("gate_core_v3_tb: %0d frames, %0d forwarded, %0d decision mismatches, %0d state mismatches, %0d patch mismatches, latency <= %0d cycles after last byte",
                 count, fwd_count, errors, sig_errors, patch_errors, max_lat);
        $finish;
    end
endmodule
