// Streams Modbus/TCP traffic (replayed go/no-go episodes + edge-case frames) through
// gate_core and checks every per-frame decision against the Python reference model.
module gate_core_tb;
    logic clk = 0;
    always #4 clk = ~clk;   // 125 MHz

    logic        rst = 1;
    logic        s_valid = 0, s_last = 0, s_dir = 0, s_fcs_ok = 0;
    logic [7:0]  s_data = 0;
    logic [31:0] t_ms = 0;
    logic        d_valid, d_forward;
    logic [3:0]  d_rule;
    logic [2:0]  d_class;
    logic [15:0] d_txid;
    logic [7:0]  d_fc;
    logic signed [15:0] st_lvl10;
    logic [15:0] st_act [4];

    gate_core dut (.*);

    int fd, r, count, errors, fwd_count, len, b, gap;
    int unsigned f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class, byte_v;
    byte unsigned frame [2048];
    string path;
    int lat, max_lat;

    initial begin
        if (!$value$plusargs("frames=%s", path)) path = "gate_frames.txt";
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %s", path); $finish; end
        repeat (4) @(posedge clk);
        rst = 0;
        count = 0; errors = 0; fwd_count = 0; max_lat = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h %h %h %h %h", f_dir, f_t, f_fcs, f_len, e_fwd, e_rule, e_class);
            if (r != 7) break;
            for (b = 0; b < f_len; b++) begin
                r = $fscanf(fd, "%h", byte_v);
                frame[b] = byte_v[7:0];
            end
            // stream the frame
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
                if (lat > 100) begin $display("TIMEOUT frame %0d", count); $finish; end
            end
            if (lat > max_lat) max_lat = lat;
            if (d_forward !== e_fwd[0] || d_rule !== e_rule[3:0] || d_class !== e_class[2:0]) begin
                errors++;
                if (errors < 12)
                    $display("MISMATCH frame %0d dir %0d: got fwd=%0d rule=%0d class=%0d exp fwd=%0d rule=%0d class=%0d (lvl10=%0d)",
                             count, f_dir, d_forward, d_rule, d_class, e_fwd, e_rule, e_class, st_lvl10);
            end
            if (d_forward) fwd_count++;
            count++;
            gap = 12;   // inter-frame gap (bytes) as on the wire
            repeat (gap) @(posedge clk);
        end
        $display("gate_core_tb: %0d frames, %0d forwarded, %0d mismatches, decision latency <= %0d cycles after last byte",
                 count, fwd_count, errors, max_lat);
        $finish;
    end
endmodule
