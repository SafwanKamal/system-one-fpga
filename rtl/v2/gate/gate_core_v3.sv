// Agent command gate v3: frame classifier, checksum verification, Modbus/TCP parser and acceptance-tracking
// decision core.  Bit-exact implementation of src/sysone/v2/agent_gate/frames_v3.py::GateV3Model
// (decision core: gate_v3.py::V3Core), verified frame by frame, including a state signature, by
// simulation/v2/gate/gate_core_v3_tb.sv.
//
// Differences from gate_core.sv (v1): the state is not "what was forwarded" but "what the PLC acknowledged":
//   * a forwarded write waits in an 8-entry pending table until the PLC's echo (commit), an exception
//     (discard), a timeout or a lost connection (the register becomes uncertain: two possible values, a third
//     makes it wild);
//   * FC3/FC4 read-backs resolve uncertainty and refresh the observed level and its timestamp;
//   * a write is refused unless it is safe in every possible actuator state and at both ends of an age-widened
//     level interval (evaluated sequentially through gate_rules), except that writes which can only lower inlet,
//     pump or heater are always allowed;
//   * IPv4 header and TCP checksums are verified (gate_csum);
//   * rule codes are 5 bits (16 checksum_bad, 18 pending_table_full, 19 state_unknown).
//
// Frames are processed one at a time (the next may stream in while a decision is pending only if the
// caller waits for d_valid, as the bridge does); d_valid is raised after all state updates are done.
module gate_core_v3 #(
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
    output logic [4:0]  d_rule,
    output logic [2:0]  d_class,
    output logic [15:0] d_txid,
    output logic [7:0]  d_fc,
    // byte mutation of the frame being decided (0 none, 1 refused request -> illegal function code,
    // 2 PLC's illegal-function reply -> client's exception).  Valid with d_valid.
    output logic [1:0]  d_patch,
    output logic [7:0]  d_pfc,
    output logic [7:0]  d_pcode,
    output logic [15:0] d_pcsum,
    output logic [10:0] d_off_fc,
    output logic [10:0] d_off_code,
    output logic [10:0] d_off_csum,
    // state signature (compared against GateV3Model.signature() by the testbench)
    output logic signed [15:0] st_lvl10,
    output logic        st_lvl_ok,
    output logic [15:0] st_v0 [4],
    output logic [15:0] st_v1m [4],
    output logic [3:0]  st_unc,
    output logic [3:0]  st_wild,
    output logic [3:0]  st_npend,
    output logic [3:0]  st_nreads,
    output logic [2:0]  st_nstarts,
    output logic [31:0] st_start_last,
    output logic [3:0]  st_ndenied
);
    localparam logic [4:0] PASS = 0, UNMAPPED = 3, RANGE = 4, MALFORMED = 13, NON_MODBUS = 14, FCS_BAD = 15,
                           CSUM_BAD = 16, PEND_FULL = 18, STATE_UNK = 19;
    localparam logic [2:0] C_OTHER = 0, C_ARP = 1, C_TCPCTL = 2, C_READ = 3, C_WRITE = 4,
                           C_RESP = 5, C_OTHERFC = 6;
    localparam int PUMP = 1, OUTLET = 2, INLET = 0, HEATER = 3;
    localparam logic [31:0] NO_START = 32'hFFFF_FFFF;
    localparam logic [31:0] T_ACK = 32'd2000;
    localparam logic [31:0] AGE_MAX = 32'd60000;
    localparam logic [31:0] DEN_TTL = 32'd10000;

    // Generated from src/sysone/v2/agent_gate/gate_v3.py::SQRT100 (round(100*sqrt(o/100)), o = 0..100)
    localparam logic [6:0] SQRT100 [101] = '{
        7'd0, 7'd10, 7'd14, 7'd17, 7'd20, 7'd22, 7'd24, 7'd26, 7'd28, 7'd30,
        7'd32, 7'd33, 7'd35, 7'd36, 7'd37, 7'd39, 7'd40, 7'd41, 7'd42, 7'd44,
        7'd45, 7'd46, 7'd47, 7'd48, 7'd49, 7'd50, 7'd51, 7'd52, 7'd53, 7'd54,
        7'd55, 7'd56, 7'd57, 7'd57, 7'd58, 7'd59, 7'd60, 7'd61, 7'd62, 7'd62,
        7'd63, 7'd64, 7'd65, 7'd66, 7'd66, 7'd67, 7'd68, 7'd69, 7'd69, 7'd70,
        7'd71, 7'd71, 7'd72, 7'd73, 7'd73, 7'd74, 7'd75, 7'd75, 7'd76, 7'd77,
        7'd77, 7'd78, 7'd79, 7'd79, 7'd80, 7'd81, 7'd81, 7'd82, 7'd82, 7'd83,
        7'd84, 7'd84, 7'd85, 7'd85, 7'd86, 7'd87, 7'd87, 7'd88, 7'd88, 7'd89,
        7'd89, 7'd90, 7'd91, 7'd91, 7'd92, 7'd92, 7'd93, 7'd93, 7'd94, 7'd94,
        7'd95, 7'd95, 7'd96, 7'd96, 7'd97, 7'd97, 7'd98, 7'd98, 7'd99, 7'd99,
        7'd100
    };

    // ------------------------------------------------------------ capture (as v1)
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

    // ------------------------------------------------------------ checksum unit
    logic c_valid, ip_ok, tcp_ok, csum_ok;
    gate_csum u_csum (.clk(clk), .rst(rst), .s_valid(s_valid), .s_data(s_data), .s_last(s_last),
                      .c_valid(c_valid), .ip_ok(ip_ok), .tcp_ok(tcp_ok));
    always_ff @(posedge clk) if (c_valid) csum_ok <= ip_ok & tcp_ok;

    // ------------------------------------------------------------ state
    // pending-write table
    logic        pv    [8];
    logic [15:0] pconn [8];
    logic [15:0] ptx   [8];
    logic [1:0]  paddr [8];
    logic [2:0]  pn    [8];
    logic [6:0]  pval  [8][4];
    logic [31:0] pt    [8];
    // read-transaction table
    logic        rdv   [8];
    logic [15:0] rdconn[8];
    logic [15:0] rdtx  [8];
    logic        rdfc4 [8];
    logic [15:0] rdst  [8];
    logic [15:0] rdqty [8];
    logic [2:0]  rptr;
    // register knowledge
    logic [15:0] v0 [4];
    logic [15:0] v1 [4];
    logic [3:0]  unc, wild;
    // observed level
    logic signed [15:0] lvl10;
    logic [31:0] lvl_t;
    logic        lvl_ok;
    // pump starts
    logic [31:0] sring [4];
    logic [2:0]  nstarts;
    logic [31:0] slast;
    // refused requests awaiting the PLC's illegal-function reply
    logic        dv    [8];
    logic [15:0] dconn [8];
    logic [15:0] dtx   [8];
    logic [7:0]  dfc   [8];
    logic [31:0] dt    [8];
    logic [2:0]  dptr;
    // connection
    logic [15:0] cur_conn;
    logic        cur_valid;

    assign st_lvl10 = lvl10;
    assign st_lvl_ok = lvl_ok;
    assign st_unc = unc;
    assign st_wild = wild;
    assign st_nstarts = nstarts;
    assign st_start_last = slast;
    for (genvar r = 0; r < 4; r++) begin : g_sig
        assign st_v0[r]  = v0[r];
        assign st_v1m[r] = unc[r] ? v1[r] : 16'd0;
    end
    always_comb begin
        st_npend = 0; st_nreads = 0; st_ndenied = 0;
        for (int k = 0; k < 8; k++) begin
            st_npend  = st_npend  + {3'd0, pv[k]};
            st_nreads = st_nreads + {3'd0, rdv[k]};
            st_ndenied = st_ndenied + {3'd0, dv[k]};
        end
    end

    // ------------------------------------------------------------ frame processing registers
    typedef enum logic [4:0] {IDLE, S_ETH, S_IP, S_TCP0, S_TCP1, S_PAY0, S_PAY1, S_DEC, S_CONN, S_DEC2, S_ROUTE,
                              S_SCAN, S_MU, S_PRE0, S_POSS, S_PRE1, S_LVL1, S_LVL1B, S_LVL1C, S_LVL2, S_ENUM, S_OTH, S_DRAIN,
                              S_FIN, S_FWD, S_RDFWD, S_RESP, S_RCOMMIT, S_RREAD, S_PATCH, S_DONE} st_t;
    st_t st, mu_ret, scan_next;
    typedef enum logic [2:0] {K_NONE, K_READ, K_WRITE, K_OTHER, K_RESP, K_RESTORE} kind_t;
    kind_t kind;

    logic [31:0] ft;
    logic [15:0] l3, et, toff, poff, total, sport, dport, ff;
    logic [7:0]  vihl, proto, doffb;
    logic signed [17:0] plen;
    logic [7:0]  pb [21];
    logic        early_done;
    logic        r_fwd;
    logic [4:0]  r_rule;
    logic [2:0]  r_class;
    logic [15:0] mtx;
    logic [7:0]  mfc;

    // write request fields
    logic [15:0] w_addr;
    logic [2:0]  w_n;
    logic        w_over;
    logic [15:0] w_vals [4];
    logic [7:0]  w_fc;
    logic [3:0]  touch;

    // possible-values computation
    logic [15:0] pa0 [4];
    logic [15:0] pa1 [4];
    logic [1:0]  pcnt [4];
    logic [3:0]  pw;
    logic [4:0]  pc;           // flat counter k*4+i

    // loops
    logic [3:0]  sk;
    logic [2:0]  mu_i, mu_n;
    logic [1:0]  mu_a;
    logic [15:0] mu_v [4];
    logic [3:0]  rk;

    // level interval
    logic [31:0] age;
    logic [31:0] x1;
    logic [39:0] x2;
    logic [15:0] mp, agep;
    logic [31:0] mi, m2;
    logic signed [15:0] lo_l, hi_l;
    logic signed [15:0] lvl_c;
    logic [15:0] act_c [4];

    // rule engine interface
    logic        rv;
    logic [7:0]  rfc;
    logic [15:0] raddr;
    logic [2:0]  rn;
    logic        rover;
    logic [15:0] rvals [4];
    logic        ro_valid, ro_allow;
    logic [3:0]  ro_rule;
    logic [31:0] rstarts [4];

    gate_rules rules (
        .clk(clk), .in_valid(rv), .fc(rfc), .addr(raddr), .nvals(rn), .nvals_over(rover),
        .vals(rvals), .lvl10(lvl_c), .act(act_c), .t_ms(ft), .starts(sring),
        .out_valid(ro_valid), .rule_id(ro_rule), .allow(ro_allow));

    logic        ff_v, col_en;
    logic [4:0]  ff_rule;
    logic [5:0]  en;           // enumeration counter {c0,c1,c2,c3,lv}
    logic [1:0]  dr;

    // payload field helpers (valid from S_DEC on)
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
    wire signed [17:0] pdulen   = plen - 18'sd7;

    task automatic finish(input logic fwd, input logic [4:0] rule, input logic [2:0] cls);
        r_fwd <= fwd; r_rule <= rule; r_class <= cls; early_done <= 1'b1;
    endtask

    for (genvar g = 0; g < 21; g++) begin : g_pb
        always_ff @(posedge clk)
            if (st == S_PAY1) pb[g] <= B(poff + g);
    end

    // collect the first non-pass result of the sequential rule evaluation
    always_ff @(posedge clk) begin
        if (rst || st == IDLE) begin
            ff_v <= 1'b0; ff_rule <= 5'd0;
        end else if (col_en && ro_valid && !ro_allow && !ff_v) begin
            ff_v <= 1'b1; ff_rule <= {1'b0, ro_rule};
        end
    end

    // helper values
    logic [4:0]  npend_c;
    logic [15:0] mnv, mxv;
    logic [15:0] reg_val;
    logic [16:0] end_a;
    logic        over100, ex_ok, free_found;
    logic [2:0]  free_k;
    logic [15:0] mxi, mxp, mxo;
    logic signed [31:0] lvl_s, lo_s, hi_s, rise_s, fall_s;
    logic        match;
    logic [1:0]  patch_kind;
    logic [7:0]  patch_fc, patch_code;
    logic [15:0] patch_csum;
    logic [10:0] patch_off_fc, patch_off_code, patch_off_csum;
    logic [2:0]  den_k, den_w;
    logic        den_hit;
    logic [15:0] csum_old, csum_t, nfc16;
    assign d_patch = patch_kind; assign d_pfc = patch_fc; assign d_pcode = patch_code; assign d_pcsum = patch_csum;
    assign d_off_fc = patch_off_fc; assign d_off_code = patch_off_code; assign d_off_csum = patch_off_csum;

    // RFC 1624 eqn. 3: new checksum after the 16-bit word m changes to m2
    function automatic logic [15:0] cupd(input logic [15:0] hc, input logic [15:0] m, input logic [15:0] m2);
        logic [17:0] x;
        x = {2'b00, ~hc} + {2'b00, ~m} + {2'b00, m2};
        x = {2'b00, x[15:0]} + {16'd0, x[17:16]};
        x = {2'b00, x[15:0]} + {16'd0, x[17:16]};
        return ~x[15:0];
    endfunction
    logic [1:0]  rr;
    logic [1:0]  pidx;
    logic        rd_ok;
    logic [17:0] q2;

    always_ff @(posedge clk) begin
        d_valid <= 1'b0;
        rv <= 1'b0;
        if (rst) begin
            st <= IDLE;
            for (int k = 0; k < 8; k++) begin pv[k] <= 1'b0; rdv[k] <= 1'b0; end
            for (int r = 0; r < 4; r++) begin
                v0[r] <= 16'd0; v1[r] <= 16'd0; sring[r] <= NO_START;
            end
            unc <= 4'd0; wild <= 4'd0; lvl10 <= 16'sd0; lvl_t <= 32'd0; lvl_ok <= 1'b0;
            nstarts <= 3'd0; slast <= 32'd0; rptr <= 3'd0; cur_valid <= 1'b0; cur_conn <= 16'd0;
            col_en <= 1'b0;
            for (int k = 0; k < 8; k++) dv[k] <= 1'b0;
            dptr <= 3'd0;
            patch_kind <= 2'd0;
        end else begin
            case (st)
            IDLE: if (start) begin
                ft <= t_ms;
                early_done <= 1'b0; kind <= K_NONE; col_en <= 1'b0;
                r_fwd <= 1'b0; r_rule <= 5'd0; r_class <= C_OTHER;
                st <= S_ETH;
            end
            // ---------------------------------------------------- parse (as v1) + checksum
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
                    else if (!csum_ok)
                        finish(1'b0, CSUM_BAD, C_OTHER);
                end
            end
            // ---------------------------------------------------- direction-level checks
            S_DEC: begin
                mtx <= {pb[0], pb[1]};
                mfc <= p_fc;
                d_txid <= {pb[0], pb[1]};
                d_fc <= p_fc;
                st <= S_DEC2;
                if (!early_done)
                    for (int k = 0; k < 8; k++)
                        if (dv[k] && (ft - dt[k]) > DEN_TTL) dv[k] <= 1'b0;
                if (!early_done) begin
                    if (!fdir) begin
                        if (dport != 16'd502) finish(1'b0, NON_MODBUS, C_OTHER);
                        else if (cur_valid && cur_conn != sport) begin
                            sk <= 4'd0; st <= S_CONN;
                        end else begin
                            cur_conn <= sport; cur_valid <= 1'b1;
                        end
                    end else begin
                        if (sport != 16'd502) finish(1'b0, NON_MODBUS, C_OTHER);
                    end
                end
            end
            // ---------------------------------------------------- connection change: old connection's writes become uncertain
            S_CONN: begin
                if (sk < 4'd8) begin
                    if (dv[sk[2:0]] && dconn[sk[2:0]] == cur_conn) dv[sk[2:0]] <= 1'b0;
                    if (pv[sk[2:0]] && pconn[sk[2:0]] == cur_conn) begin
                        pv[sk[2:0]] <= 1'b0;
                        mu_a <= paddr[sk[2:0]]; mu_n <= pn[sk[2:0]]; mu_i <= 3'd0;
                        for (int i = 0; i < 4; i++) mu_v[i] <= {9'd0, pval[sk[2:0]][i]};
                        mu_ret <= S_CONN;
                        sk <= sk + 4'd1;
                        st <= S_MU;
                    end else sk <= sk + 4'd1;
                end else begin
                    // read-table entries of the old connection are forgotten
                    if (rdv[sk[2:0]] && rdconn[sk[2:0]] == cur_conn) rdv[sk[2:0]] <= 1'b0;
                    if (sk == 4'd15) begin
                        cur_conn <= sport; cur_valid <= 1'b1; st <= S_DEC2;
                    end
                    sk <= sk + 4'd1;
                end
            end
            // ---------------------------------------------------- payload classification (as v1)
            S_DEC2: begin
                st <= S_ROUTE;
                kind <= K_NONE;
                if (!early_done) begin
                    if (!fdir) begin
                        if (plen == 0) finish(1'b1, PASS, C_TCPCTL);
                        else if (plen < 18'sd8 || p_poff_s + p_need > CAP) finish(1'b0, MALFORMED, C_OTHER);
                        else if (p_pid != 0 || p_mlen_s != plen - 18'sd6) finish(1'b0, MALFORMED, C_OTHER);
                        else if (p_fc == 8'd3 || p_fc == 8'd4) begin
                            if (plen != 18'sd12) finish(1'b0, MALFORMED, C_OTHER);
                            else begin kind <= K_READ; r_fwd <= 1'b1; r_rule <= PASS; r_class <= C_READ; end
                        end else if (p_fc == 8'd6) begin
                            if (plen != 18'sd12) finish(1'b0, MALFORMED, C_OTHER);
                            else begin
                                kind <= K_WRITE; w_fc <= p_fc; w_addr <= p_w8; w_n <= 3'd1; w_over <= 1'b0;
                                w_vals[0] <= p_w10; w_vals[1] <= 0; w_vals[2] <= 0; w_vals[3] <= 0;
                            end
                        end else if (p_fc == 8'd16) begin
                            if (plen < 18'sd13 || {9'd0, p_bc} != {p_w10, 1'b0} ||
                                plen != 18'sd13 + $signed({10'd0, p_bc}))
                                finish(1'b0, MALFORMED, C_OTHER);
                            else begin
                                kind <= K_WRITE; w_fc <= p_fc; w_addr <= p_w8;
                                w_over <= (p_w10 > 16'd4);
                                w_n <= (p_w10 > 16'd4) ? 3'd4 : p_w10[2:0];
                                w_vals[0] <= {pb[13], pb[14]}; w_vals[1] <= {pb[15], pb[16]};
                                w_vals[2] <= {pb[17], pb[18]}; w_vals[3] <= {pb[19], pb[20]};
                            end
                        end else begin
                            kind <= K_OTHER; w_fc <= p_fc; w_addr <= 0; w_n <= 3'd0; w_over <= 1'b0;
                            w_vals[0] <= 0; w_vals[1] <= 0; w_vals[2] <= 0; w_vals[3] <= 0;
                        end
                    end else begin
                        r_fwd <= 1'b1; r_rule <= PASS; r_class <= C_RESP;
                        if (plen >= 18'sd8 && p_poff_s + p_need <= CAP && p_pid == 0 && p_mlen_s == plen - 18'sd6)
                            kind <= K_RESP;
                    end
                end
            end
            S_ROUTE: begin
                sk <= 4'd0;
                den_hit = 1'b0; den_k = 3'd0;
                for (int k = 7; k >= 0; k--)
                    if (dv[k] && dconn[k] == dport && dtx[k] == mtx) begin den_hit = 1'b1; den_k = k[2:0]; end
                if (kind == K_RESP && den_hit && mfc == 8'hFF && plen == 18'sd9) begin
                    kind <= K_RESTORE; st <= S_PATCH;
                end else
                case (kind)
                    K_READ:  st <= S_RDFWD;
                    K_WRITE: begin st <= S_SCAN; scan_next <= S_PRE0; end
                    K_OTHER: begin st <= S_SCAN; scan_next <= S_OTH; end
                    K_RESP:  begin st <= S_SCAN; scan_next <= S_RESP; end
                    default: st <= S_PATCH;
                endcase
                if (kind == K_RESP) rk <= 4'd0;
            end
            // ---------------------------------------------------- timeouts: expired pending writes become uncertain
            S_SCAN: begin
                if (sk >= 4'd8) st <= scan_next;
                else if (pv[sk[2:0]] && (ft - pt[sk[2:0]]) > T_ACK) begin
                    pv[sk[2:0]] <= 1'b0;
                    mu_a <= paddr[sk[2:0]]; mu_n <= pn[sk[2:0]]; mu_i <= 3'd0;
                    for (int i = 0; i < 4; i++) mu_v[i] <= {9'd0, pval[sk[2:0]][i]};
                    mu_ret <= S_SCAN;
                    sk <= sk + 4'd1;
                    st <= S_MU;
                end else sk <= sk + 4'd1;
            end
            // ---------------------------------------------------- make a pending write's values possible-but-uncertain
            S_MU: begin
                reg_val = mu_v[mu_i[1:0]];
                begin : mu_body
                    logic [1:0] r;
                    r = mu_a + mu_i[1:0];
                    if (reg_val == v0[r] || (unc[r] && reg_val == v1[r])) begin
                        // already possible
                    end else if (unc[r]) wild[r] <= 1'b1;
                    else begin
                        unc[r] <= 1'b1;
                        v0[r] <= (v0[r] < reg_val) ? v0[r] : reg_val;
                        v1[r] <= (v0[r] < reg_val) ? reg_val : v0[r];
                    end
                end
                if (mu_i + 3'd1 >= mu_n) st <= mu_ret;
                mu_i <= mu_i + 3'd1;
            end
            // ---------------------------------------------------- write decision
            S_PRE0: begin
                end_a = {1'b0, w_addr} + {14'd0, w_n};
                over100 = 1'b0;
                for (int i = 0; i < 4; i++) if (i < w_n && w_vals[i] > 16'd100) over100 = 1'b1;
                col_en <= 1'b0;
                for (int r = 0; r < 4; r++) begin
                    if (unc[r]) begin
                        pa0[r] <= (v0[r] < v1[r]) ? v0[r] : v1[r];
                        pa1[r] <= (v0[r] < v1[r]) ? v1[r] : v0[r];
                        pcnt[r] <= 2'd2;
                    end else begin
                        pa0[r] <= v0[r]; pa1[r] <= v0[r]; pcnt[r] <= 2'd1;
                    end
                    pw[r] <= wild[r];
                end
                pc <= 5'd0;
                for (int r = 0; r < 4; r++) touch[r] <= (r >= w_addr && r < w_addr + w_n);
                if (w_over || w_n == 0 || end_a > 17'd4) begin
                    r_fwd <= 1'b0; r_rule <= UNMAPPED; r_class <= C_WRITE; st <= S_PATCH;
                end else if (over100) begin
                    r_fwd <= 1'b0; r_rule <= RANGE; r_class <= C_WRITE; st <= S_PATCH;
                end else st <= S_POSS;
            end
            S_POSS: begin
                begin : poss_body
                    logic [2:0] k;
                    logic [1:0] i, r;
                    logic [15:0] v;
                    k = pc[4:2]; i = pc[1:0];
                    if (pv[k] && i < pn[k]) begin
                        r = paddr[k] + i;
                        v = {9'd0, pval[k][i]};
                        if (v == pa0[r] || (pcnt[r] == 2'd2 && v == pa1[r])) begin
                            // present
                        end else if (pcnt[r] >= 2'd2) pw[r] <= 1'b1;
                        else begin
                            if (v < pa0[r]) begin pa1[r] <= pa0[r]; pa0[r] <= v; end
                            else pa1[r] <= v;
                            pcnt[r] <= 2'd2;
                        end
                    end
                end
                pc <= pc + 5'd1;
                if (pc == 5'd31) st <= S_PRE1;
            end
            S_PRE1: begin
                ex_ok = !touch[OUTLET];
                for (int i = 0; i < 4; i++) begin
                    if (i < w_n) begin
                        // register index w_addr + i
                        if (w_vals[i] > (pw[w_addr[1:0] + i[1:0]] ? 16'd0 : pa0[w_addr[1:0] + i[1:0]])) ex_ok = 1'b0;
                    end
                end
                npend_c = 0;
                for (int k = 0; k < 8; k++) npend_c = npend_c + {4'd0, pv[k]};
                r_class <= C_WRITE;
                if (ex_ok) begin
                    r_fwd <= 1'b1; r_rule <= PASS; st <= S_FWD;
                end else if (npend_c >= 5'd8) begin
                    r_fwd <= 1'b0; r_rule <= PEND_FULL; st <= S_PATCH;
                end else if (pw != 4'd0) begin
                    r_fwd <= 1'b0; r_rule <= STATE_UNK; st <= S_PATCH;
                end else st <= S_LVL1;
            end
            S_LVL1: begin
                // level interval inputs
                mxi = (pa1[INLET]  > 16'd100) ? 16'd100 : pa1[INLET];
                mxp = (pa1[PUMP]   > 16'd100) ? 16'd100 : pa1[PUMP];
                mxo = (pa1[OUTLET] > 16'd100) ? 16'd100 : pa1[OUTLET];
                age = ft - lvl_t;
                if (age > AGE_MAX) age = AGE_MAX;
                // three registered multiply stages (bit-identical to the single product, for timing)
                mp <= mxp * {9'd0, SQRT100[mxo[6:0]]};
                mi <= mxi * age[15:0];
                agep <= age[15:0];
                if (!lvl_ok) begin lo_l <= 16'sd0; hi_l <= 16'sd1000; st <= S_ENUM; en <= 6'd0; end
                else st <= S_LVL1B;
            end
            S_LVL1B: begin
                x1 <= mi * 16'd315;
                m2 <= mp * agep;
                st <= S_LVL1C;
            end
            S_LVL1C: begin
                x2 <= m2 * 16'd53;
                st <= S_LVL2;
            end
            S_LVL2: begin
                lvl_s = {{16{lvl10[15]}}, lvl10};
                rise_s = (x1 + 32'd1048575) >> 20;
                fall_s = x2 >> 24;
                lo_s = lvl_s - fall_s;
                hi_s = lvl_s + rise_s;
                lo_l <= (lo_s < -32'sd100) ? -16'sd100 : lo_s[15:0];
                hi_l <= (hi_s > 32'sd1100) ? 16'sd1100 : hi_s[15:0];
                st <= S_ENUM; en <= 6'd0;
            end
            // ---------------------------------------------------- evaluate every possible state through gate_rules
            S_ENUM: begin
                col_en <= 1'b1;
                if (en == 6'd32) begin
                    st <= S_DRAIN; dr <= 2'd0;
                end else begin
                    begin : enum_body
                        logic ok0, ok1, ok2, ok3;
                        ok0 = (en[4] == 1'b0) || (pcnt[0] == 2'd2);
                        ok1 = (en[3] == 1'b0) || (pcnt[1] == 2'd2);
                        ok2 = (en[2] == 1'b0) || (pcnt[2] == 2'd2);
                        ok3 = (en[1] == 1'b0) || (pcnt[3] == 2'd2);
                        if (ok0 && ok1 && ok2 && ok3) begin
                            rv <= 1'b1;
                            rfc <= w_fc; raddr <= w_addr; rn <= w_n; rover <= 1'b0;
                            for (int i = 0; i < 4; i++) rvals[i] <= w_vals[i];
                            act_c[0] <= en[4] ? pa1[0] : pa0[0];
                            act_c[1] <= en[3] ? pa1[1] : pa0[1];
                            act_c[2] <= en[2] ? pa1[2] : pa0[2];
                            act_c[3] <= en[1] ? pa1[3] : pa0[3];
                            lvl_c <= en[0] ? hi_l : lo_l;
                        end
                    end
                    en <= en + 6'd1;
                end
            end
            S_OTH: begin
                col_en <= 1'b1;
                rv <= 1'b1; rfc <= w_fc; raddr <= 16'd0; rn <= 3'd0; rover <= 1'b0;
                for (int i = 0; i < 4; i++) begin rvals[i] <= 16'd0; act_c[i] <= 16'd0; end
                lvl_c <= 16'sd0;
                st <= S_DRAIN; dr <= 2'd0;
            end
            S_DRAIN: begin
                dr <= dr + 2'd1;
                if (dr == 2'd2) st <= S_FIN;
            end
            S_FIN: begin
                col_en <= 1'b0;
                r_fwd <= !ff_v; r_rule <= ff_v ? ff_rule : PASS;
                r_class <= (kind == K_WRITE) ? C_WRITE : C_OTHERFC;
                if (kind == K_WRITE && !ff_v) st <= S_FWD; else st <= S_PATCH;
            end
            // ---------------------------------------------------- forwarded write: track it as pending
            S_FWD: begin
                pidx = 2'(PUMP) - w_addr[1:0];
                free_found = 1'b0; free_k = 3'd0;
                for (int k = 7; k >= 0; k--) if (!pv[k]) begin free_found = 1'b1; free_k = k[2:0]; end
                if (free_found) begin
                    pv[free_k] <= 1'b1; pconn[free_k] <= sport; ptx[free_k] <= mtx;
                    paddr[free_k] <= w_addr[1:0]; pn[free_k] <= w_n; pt[free_k] <= ft;
                    for (int i = 0; i < 4; i++) pval[free_k][i] <= w_vals[i][6:0];
                    if (touch[PUMP] && w_vals[pidx] != 0 && pa0[PUMP] == 0) begin
                        sring[0] <= sring[1]; sring[1] <= sring[2]; sring[2] <= sring[3]; sring[3] <= ft;
                        nstarts <= (nstarts == 3'd4) ? 3'd4 : nstarts + 3'd1;
                        slast <= ft;
                    end
                end
                st <= S_PATCH;
            end
            // ---------------------------------------------------- forwarded read: remember it
            S_RDFWD: begin
                rdv[rptr] <= 1'b1; rdconn[rptr] <= sport; rdtx[rptr] <= mtx; rdfc4[rptr] <= (mfc == 8'd4);
                rdst[rptr] <= p_w8; rdqty[rptr] <= p_w10;
                rptr <= rptr + 3'd1;
                st <= S_PATCH;
            end
            // ---------------------------------------------------- PLC response
            S_RESP: begin
                if (rk < 4'd8) begin
                    // pending write with this connection and transaction id?
                    if (pv[rk[2:0]] && pconn[rk[2:0]] == dport && ptx[rk[2:0]] == mtx) begin
                        pv[rk[2:0]] <= 1'b0;
                        mu_a <= paddr[rk[2:0]]; mu_n <= pn[rk[2:0]]; mu_i <= 3'd0;
                        for (int i = 0; i < 4; i++) mu_v[i] <= {9'd0, pval[rk[2:0]][i]};
                        mu_ret <= S_PATCH;
                        if (mfc[7]) st <= S_PATCH;                          // exception: not applied
                        else if (mfc == 8'd6 && pdulen == 18'sd5 && p_w8 == {14'd0, paddr[rk[2:0]]} &&
                                 pn[rk[2:0]] == 3'd1 && p_w10 == {9'd0, pval[rk[2:0]][0]})
                            st <= S_RCOMMIT;                               // echo of the write
                        else if (mfc == 8'd16 && pdulen == 18'sd5 && p_w8 == {14'd0, paddr[rk[2:0]]} &&
                                 p_w10 == {13'd0, pn[rk[2:0]]})
                            st <= S_RCOMMIT;
                        else st <= S_MU;                                   // unexpected reply: uncertain
                    end else rk <= rk + 4'd1;
                end else begin
                    // read transaction with this connection and transaction id?
                    if (rdv[rk[2:0]] && rdconn[rk[2:0]] == dport && rdtx[rk[2:0]] == mtx &&
                        (mfc == 8'd3 || mfc == 8'd4)) begin
                        rdv[rk[2:0]] <= 1'b0;
                        q2 = {rdqty[rk[2:0]], 1'b0};
                        rd_ok = (rdfc4[rk[2:0]] == (mfc == 8'd4)) && pdulen >= 18'sd2 &&
                                rdqty[rk[2:0]][15:7] == 9'd0 && pb[8] == q2[7:0] &&
                                pdulen == $signed(q2 + 18'd2);
                        if (rd_ok) begin
                            if (mfc == 8'd4 && rdst[rk[2:0]] == 16'd0 && rdqty[rk[2:0]] >= 16'd1) begin
                                lvl10 <= $signed({pb[9], pb[10]}); lvl_t <= ft; lvl_ok <= 1'b1;
                            end
                            if (mfc == 8'd3) begin
                                for (int i = 0; i < 4; i++) begin
                                    if ({1'b0, rdst[rk[2:0]]} + i < 17'd4 && i < rdqty[rk[2:0]]) begin
                                        v0[rdst[rk[2:0]][1:0] + i[1:0]] <= {pb[9 + 2 * i], pb[10 + 2 * i]};
                                        unc[rdst[rk[2:0]][1:0] + i[1:0]] <= 1'b0;
                                        wild[rdst[rk[2:0]][1:0] + i[1:0]] <= 1'b0;
                                    end
                                end
                            end
                        end
                        st <= S_PATCH;
                    end else if (rk == 4'd15) st <= S_PATCH;
                    else rk <= rk + 4'd1;
                end
            end
            S_RCOMMIT: begin
                begin : rc_body
                    logic [1:0] r;
                    r = mu_a + mu_i[1:0];
                    v0[r] <= mu_v[mu_i[1:0]]; unc[r] <= 1'b0; wild[r] <= 1'b0;
                end
                mu_i <= mu_i + 3'd1;
                if (mu_i + 3'd1 >= mu_n) st <= S_PATCH;
            end
            S_PATCH: begin
                patch_kind <= 2'd0; patch_fc <= 8'd0; patch_code <= 8'd0; patch_csum <= 16'd0;
                patch_off_fc <= 11'd0; patch_off_code <= 11'd0; patch_off_csum <= 11'd0;
                csum_old = {B(toff + 16'd16), B(toff + 16'd17)};
                if ((kind == K_WRITE || kind == K_OTHER) && !r_fwd) begin
                    // refused request: same length, illegal function code, PLC answers with an exception
                    patch_kind <= 2'd1; patch_fc <= 8'h7F;
                    patch_csum <= cupd(csum_old, {pb[6], pb[7]}, {pb[6], 8'h7F});
                    patch_off_fc <= poff[10:0] + 11'd7; patch_off_csum <= toff[10:0] + 11'd16;
                    den_hit = 1'b0; den_w = dptr;
                    for (int k = 7; k >= 0; k--)
                        if (dv[k] && dconn[k] == sport && dtx[k] == mtx) begin den_hit = 1'b1; den_w = k[2:0]; end
                    dv[den_w] <= 1'b1; dconn[den_w] <= sport; dtx[den_w] <= mtx; dfc[den_w] <= mfc; dt[den_w] <= ft;
                    if (!den_hit) dptr <= dptr + 3'd1;
                end else if (kind == K_RESTORE) begin
                    nfc16 = {pb[6], dfc[den_k] | 8'h80};
                    csum_t = cupd(csum_old, {pb[6], pb[7]}, nfc16);
                    patch_kind <= 2'd2; patch_fc <= dfc[den_k] | 8'h80; patch_code <= 8'h03;
                    patch_csum <= cupd(csum_t, {pb[8], 8'h00}, 16'h0300);
                    patch_off_fc <= poff[10:0] + 11'd7; patch_off_code <= poff[10:0] + 11'd8;
                    patch_off_csum <= toff[10:0] + 11'd16;
                    dv[den_k] <= 1'b0;
                end
                st <= S_DONE;
            end
            S_DONE: begin
                d_valid <= 1'b1; d_forward <= r_fwd; d_rule <= r_rule; d_class <= r_class;
                st <= IDLE;
            end
            default: st <= IDLE;
            endcase
        end
    end
endmodule
