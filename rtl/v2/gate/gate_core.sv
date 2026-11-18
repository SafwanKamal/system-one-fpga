// Agent command gate: frame classifier, Modbus/TCP parser, plant-state tracker and
// rule engine.  Bit-exact implementation of src/sysone/v2/agent_gate/frames.py::GateModel.
//
// Input: one Ethernet frame at a time (no preamble/SFD/FCS), byte per cycle, with the
// direction (0 = agent-side port A, 1 = plant-side port B) and the MAC's FCS verdict on
// the last byte.  The first CAP bytes are captured; the decision is produced 11 cycles
// after the last byte while the next frame may already be arriving (frames are >= 60 B).
//
// Output: one decision per frame (forward/drop, rule code, frame class).  The state
// (observed level, forwarded actuator values, pump-start times, read-transaction table)
// changes only through forwarded writes and matching FC4 responses.
module gate_core #(
    parameter int CAP = 128
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        s_valid,
    input  logic [7:0]  s_data,
    input  logic        s_last,
    input  logic        s_dir,
    input  logic        s_fcs_ok,
    input  logic [31:0] t_ms,
    output logic        d_valid,
    output logic        d_forward,
    output logic [3:0]  d_rule,
    output logic [2:0]  d_class,
    output logic [15:0] d_txid,
    output logic [7:0]  d_fc,
    output logic signed [15:0] st_lvl10,
    output logic [15:0] st_act [4]
);
    localparam logic [3:0] PASS = 0, UNMAPPED = 3, MALFORMED = 13, NON_MODBUS = 14, FCS_BAD = 15;
    localparam logic [2:0] C_OTHER = 0, C_ARP = 1, C_TCPCTL = 2, C_READ = 3, C_WRITE = 4,
                           C_RESP = 5, C_OTHERFC = 6;
    localparam int PUMP = 1;

    // ------------------------------------------------------------ capture
    logic [7:0]  cap   [CAP];
    logic [7:0]  snap  [CAP];
    logic [15:0] pos;
    logic [15:0] flen;
    logic        fdir, ffcs, start;

    always_ff @(posedge clk) begin
        start <= 1'b0;
        if (rst) begin
            pos <= 0;
        end else if (s_valid) begin
            if (pos < CAP) cap[pos[6:0]] <= s_data;
            if (s_last) begin
                flen  <= pos + 16'd1;
                fdir  <= s_dir;
                ffcs  <= s_fcs_ok;
                start <= 1'b1;
                pos   <= 0;
            end else begin
                pos <= pos + 16'd1;
            end
        end
    end

    for (genvar g = 0; g < CAP; g++) begin : g_snap
        always_ff @(posedge clk)
            if (!rst && s_valid && s_last) snap[g] <= (pos == g) ? s_data : cap[g];
    end

    function automatic logic [7:0] B(input logic [15:0] i);
        return (i < CAP) ? snap[i[6:0]] : 8'h00;
    endfunction
    function automatic logic [15:0] W(input logic [15:0] i);
        return {B(i), B(i + 16'd1)};
    endfunction

    // ------------------------------------------------------------ state
    logic signed [15:0] lvl10;
    logic [15:0] act [4];
    logic [31:0] starts [4];
    logic        tv [4];
    logic [15:0] ttx [4];
    logic [7:0]  tfc [4];
    logic [15:0] tst [4];
    logic [15:0] tqty [4];
    logic [1:0]  tptr;
    assign st_lvl10 = lvl10;
    assign st_act = act;

    // ------------------------------------------------------------ decision pipeline
    typedef enum logic [3:0] {IDLE, S_ETH, S_IP, S_TCP0, S_TCP1, S_PAY0, S_PAY1, S_DEC,
                              S_RWAIT, S_RES, S_COMMIT} st_t;
    st_t st;
    logic [31:0] ft;
    logic [15:0] l3, et, toff, poff, total, sport, dport, ff;
    logic [7:0]  vihl, proto, doffb;
    logic signed [17:0] plen;
    logic [7:0]  pb [21];
    logic        early_done;
    logic        r_fwd;
    logic [3:0]  r_rule;
    logic [2:0]  r_class;
    logic        is_write, is_read, upd_lvl;
    logic [15:0] mtx;
    logic [7:0]  mfc;
    // rule engine interface
    logic        rv;
    logic [7:0]  rfc;
    logic [15:0] raddr;
    logic [2:0]  rn;
    logic        rover;
    logic [15:0] rvals [4];
    logic        ro_valid, ro_allow;
    logic [3:0]  ro_rule;

    gate_rules rules (
        .clk(clk), .in_valid(rv), .fc(rfc), .addr(raddr), .nvals(rn), .nvals_over(rover),
        .vals(rvals), .lvl10(lvl10), .act(act), .t_ms(ft), .starts(starts),
        .out_valid(ro_valid), .rule_id(ro_rule), .allow(ro_allow));

    // payload field helpers (valid in S_DEC .. S_COMMIT)
    wire [15:0] p_pid  = {pb[2], pb[3]};
    wire [15:0] p_mlen = {pb[4], pb[5]};
    wire [7:0]  p_fc   = pb[7];
    wire [15:0] p_w8   = {pb[8], pb[9]};
    wire [15:0] p_w10  = {pb[10], pb[11]};
    wire [7:0]  p_bc   = pb[12];
    wire signed [17:0] p_mlen_s = $signed({2'b00, p_mlen});
    wire signed [17:0] p_poff_s = $signed({2'b00, poff});
    wire signed [17:0] p_flen_s = $signed({2'b00, flen});
    wire signed [17:0] p_need   = (plen < 18'sd21) ? plen : 18'sd21;

    task automatic finish(input logic fwd, input logic [3:0] rule, input logic [2:0] cls);
        r_fwd <= fwd; r_rule <= rule; r_class <= cls; early_done <= 1'b1;
    endtask

    for (genvar g = 0; g < 21; g++) begin : g_pb
        always_ff @(posedge clk)
            if (st == S_PAY1) pb[g] <= B(poff + g);
    end

    logic [15:0] nact [4];

    always_ff @(posedge clk) begin
        d_valid <= 1'b0;
        rv <= 1'b0;
        if (rst) begin
            st <= IDLE;
            lvl10 <= 16'sd500;
            act[0] <= 0; act[1] <= 0; act[2] <= 0; act[3] <= 0;
            starts[0] <= 32'hFFFF_FFFF; starts[1] <= 32'hFFFF_FFFF;
            starts[2] <= 32'hFFFF_FFFF; starts[3] <= 32'hFFFF_FFFF;
            tv[0] <= 1'b0; tv[1] <= 1'b0; tv[2] <= 1'b0; tv[3] <= 1'b0;
            tptr <= 0;
        end else begin
            case (st)
            IDLE: if (start) begin
                ft <= t_ms;
                early_done <= 1'b0; is_write <= 1'b0; is_read <= 1'b0; upd_lvl <= 1'b0;
                rover <= 1'b0; rn <= 0;
                st <= S_ETH;
            end
            S_ETH: begin
                st <= S_IP;
                if (!ffcs) finish(1'b0, FCS_BAD, C_OTHER);
                else if (flen < 14) finish(1'b0, NON_MODBUS, C_OTHER);
                else if (W(12) == 16'h8100) begin
                    if (flen < 18) finish(1'b0, NON_MODBUS, C_OTHER);
                    l3 <= 16'd18; et <= W(16);
                end else begin
                    l3 <= 16'd14; et <= W(12);
                end
            end
            S_IP: begin
                st <= S_TCP0;
                vihl  <= B(l3);
                total <= W(l3 + 16'd2);
                ff    <= W(l3 + 16'd6);
                proto <= B(l3 + 16'd9);
                if (!early_done) begin
                    if (et == 16'h0806) finish(1'b1, PASS, C_ARP);
                    else if (et != 16'h0800 || flen < l3 + 16'd20) finish(1'b0, NON_MODBUS, C_OTHER);
                end
            end
            S_TCP0: begin
                st <= S_TCP1;
                toff <= l3 + {10'd0, vihl[3:0], 2'b00};
                if (!early_done) begin
                    if (vihl[7:4] != 4'd4 || vihl[3:0] < 4'd5) finish(1'b0, MALFORMED, C_OTHER);
                    else if (ff[13:0] != 0) finish(1'b0, MALFORMED, C_OTHER);
                    else if (proto != 8'd6) finish(1'b0, NON_MODBUS, C_OTHER);
                end
            end
            S_TCP1: begin
                st <= S_PAY0;
                sport <= W(toff);
                dport <= W(toff + 16'd2);
                doffb <= B(toff + 16'd12);
                if (!early_done && flen < toff + 16'd20) finish(1'b0, MALFORMED, C_OTHER);
            end
            S_PAY0: begin
                st <= S_PAY1;
                poff <= toff + {10'd0, doffb[7:4], 2'b00};
                plen <= $signed({2'b00, total}) - $signed({12'd0, vihl[3:0], 2'b00})
                        - $signed({12'd0, doffb[7:4], 2'b00});
            end
            S_PAY1: begin
                st <= S_DEC;
                if (!early_done) begin
                    if (doffb[7:4] < 4'd5 || plen < 0 || p_flen_s < p_poff_s + plen)
                        finish(1'b0, MALFORMED, C_OTHER);
                end
            end
            S_DEC: begin
                st <= S_RWAIT;
                mtx <= {pb[0], pb[1]};
                mfc <= p_fc;
                d_txid <= {pb[0], pb[1]};
                d_fc <= p_fc;
                if (!early_done) begin
                    if (!fdir) begin
                        if (dport != 16'd502) finish(1'b0, NON_MODBUS, C_OTHER);
                        else if (plen == 0) finish(1'b1, PASS, C_TCPCTL);
                        else if (plen < 18'sd8 || p_poff_s + p_need > CAP)
                            finish(1'b0, MALFORMED, C_OTHER);
                        else if (p_pid != 0 || p_mlen_s != plen - 18'sd6)
                            finish(1'b0, MALFORMED, C_OTHER);
                        else if (p_fc == 8'd3 || p_fc == 8'd4) begin
                            if (plen != 18'sd12) finish(1'b0, MALFORMED, C_OTHER);
                            else begin
                                is_read <= 1'b1;
                                finish(1'b1, PASS, C_READ);
                            end
                        end else if (p_fc == 8'd6) begin
                            if (plen != 18'sd12) finish(1'b0, MALFORMED, C_OTHER);
                            else begin
                                rv <= 1'b1; rfc <= p_fc; raddr <= p_w8; rn <= 3'd1; rover <= 1'b0;
                                rvals[0] <= p_w10; rvals[1] <= 0; rvals[2] <= 0; rvals[3] <= 0;
                                is_write <= 1'b1;
                            end
                        end else if (p_fc == 8'd16) begin
                            if (plen < 18'sd13 || {9'd0, p_bc} != {p_w10, 1'b0} ||
                                plen != 18'sd13 + $signed({10'd0, p_bc}))
                                finish(1'b0, MALFORMED, C_OTHER);
                            else begin
                                rv <= 1'b1; rfc <= p_fc; raddr <= p_w8;
                                rover <= (p_w10 > 16'd4);
                                rn <= (p_w10 > 16'd4) ? 3'd4 : p_w10[2:0];
                                rvals[0] <= {pb[13], pb[14]}; rvals[1] <= {pb[15], pb[16]};
                                rvals[2] <= {pb[17], pb[18]}; rvals[3] <= {pb[19], pb[20]};
                                is_write <= 1'b1;
                            end
                        end else begin
                            rv <= 1'b1; rfc <= p_fc; raddr <= 0; rn <= 0; rover <= 1'b0;
                            rvals[0] <= 0; rvals[1] <= 0; rvals[2] <= 0; rvals[3] <= 0;
                        end
                    end else begin
                        if (sport != 16'd502) finish(1'b0, NON_MODBUS, C_OTHER);
                        else begin
                            finish(1'b1, PASS, C_RESP);
                            if (plen >= 18'sd11 && p_poff_s + 18'sd11 <= CAP && p_fc == 8'd4 &&
                                p_pid == 0 && p_mlen_s == plen - 18'sd6 && pb[8] >= 8'd2)
                                upd_lvl <= 1'b1;
                        end
                    end
                end
            end
            S_RWAIT: st <= S_RES;   // gate_rules samples rv here; result registered next edge
            S_RES: begin
                st <= S_COMMIT;
                if (!early_done) begin
                    if (rover && is_write) begin
                        r_fwd <= 1'b0; r_rule <= UNMAPPED; r_class <= C_WRITE;
                    end else begin
                        r_fwd <= ro_allow; r_rule <= ro_rule;
                        r_class <= is_write ? C_WRITE : C_OTHERFC;
                    end
                end
            end
            S_COMMIT: begin
                st <= IDLE;
                d_valid <= 1'b1; d_forward <= r_fwd; d_rule <= r_rule; d_class <= r_class;
                if (is_read) begin
                    tv[tptr] <= 1'b1; ttx[tptr] <= mtx; tfc[tptr] <= mfc;
                    tst[tptr] <= p_w8; tqty[tptr] <= p_w10;
                    tptr <= tptr + 2'd1;
                end
                if (upd_lvl) begin
                    if (tv[0] && ttx[0] == mtx && tfc[0] == 8'd4) begin
                        tv[0] <= 1'b0; if (tst[0] == 0 && tqty[0] >= 1) lvl10 <= $signed({pb[9], pb[10]});
                    end else if (tv[1] && ttx[1] == mtx && tfc[1] == 8'd4) begin
                        tv[1] <= 1'b0; if (tst[1] == 0 && tqty[1] >= 1) lvl10 <= $signed({pb[9], pb[10]});
                    end else if (tv[2] && ttx[2] == mtx && tfc[2] == 8'd4) begin
                        tv[2] <= 1'b0; if (tst[2] == 0 && tqty[2] >= 1) lvl10 <= $signed({pb[9], pb[10]});
                    end else if (tv[3] && ttx[3] == mtx && tfc[3] == 8'd4) begin
                        tv[3] <= 1'b0; if (tst[3] == 0 && tqty[3] >= 1) lvl10 <= $signed({pb[9], pb[10]});
                    end
                end
                if (is_write && r_fwd) begin
                    for (int k = 0; k < 4; k++) nact[k] = act[k];
                    for (int i = 0; i < 4; i++)
                        if (i < rn) nact[raddr[1:0] + i[1:0]] = rvals[i];
                    act[0] <= nact[0]; act[1] <= nact[1]; act[2] <= nact[2]; act[3] <= nact[3];
                    if (act[PUMP] == 0 && nact[PUMP] > 0) begin
                        // keep the last 4 start times (oldest dropped); empties first
                        starts[0] <= starts[1]; starts[1] <= starts[2]; starts[2] <= starts[3];
                        starts[3] <= ft;
                    end
                end
            end
            default: st <= IDLE;
            endcase
        end
    end
endmodule
