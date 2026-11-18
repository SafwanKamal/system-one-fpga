from pathlib import Path

src = Path("rtl/v2/gate/bridge/gate_bridge_core.sv").read_text(encoding="utf-8")
s = src


def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)


rep("module gate_bridge_core #(", "module gate_bridge_core_v3 #(")
rep("// Two-port store-and-forward Ethernet bridge with the agent gate in the path.",
    "// Two-port store-and-forward Ethernet bridge with the v3 agent gate (acceptance tracking) in the path.\n"
    "// Generated from gate_bridge_core.sv by scripts/v2/gate/make_bridge_v3.py; differences: gate_core_v3, and\n"
    "// refused requests are not dropped but mutated (illegal function code, same length) and the PLC's reply is\n"
    "// restored; mutated frames get a corrected TCP checksum from the gate and a freshly computed Ethernet FCS here.")

# ---- gate instance
old = s[s.index("    logic        g_dvalid, g_fwd;"):s.index("    // ------------------------------------------------ per-direction engines")]
new = '''    logic        g_dvalid, g_fwd;
    logic [4:0]  g_rule;
    logic [2:0]  g_class;
    logic [15:0] g_txid;
    logic [7:0]  g_fc;
    logic [1:0]  g_patch;
    logic [7:0]  g_pfc, g_pcode;
    logic [15:0] g_pcsum;
    logic [10:0] g_off_fc, g_off_code, g_off_csum;
    logic signed [15:0] g_lvl;
    logic        g_lvl_ok;
    logic [15:0] g_v0 [4];
    logic [15:0] g_v1m [4];
    logic [3:0]  g_unc, g_wild, g_npend, g_nreads, g_ndenied;
    logic [2:0]  g_nstarts;
    logic [31:0] g_slast;
    gate_core_v3 u_gate (
        .clk(clk), .rst(rst), .s_valid(g_valid), .s_data(g_data), .s_last(g_last), .s_dir(g_dir),
        .s_fcs_ok(g_fcs), .t_ms(t_ms), .d_valid(g_dvalid), .d_forward(g_fwd), .d_rule(g_rule),
        .d_class(g_class), .d_txid(g_txid), .d_fc(g_fc),
        .d_patch(g_patch), .d_pfc(g_pfc), .d_pcode(g_pcode), .d_pcsum(g_pcsum),
        .d_off_fc(g_off_fc), .d_off_code(g_off_code), .d_off_csum(g_off_csum),
        .st_lvl10(g_lvl), .st_lvl_ok(g_lvl_ok), .st_v0(g_v0), .st_v1m(g_v1m), .st_unc(g_unc), .st_wild(g_wild),
        .st_npend(g_npend), .st_nreads(g_nreads), .st_nstarts(g_nstarts), .st_start_last(g_slast),
        .st_ndenied(g_ndenied));

'''
s = s.replace(old, new, 1)

# ---- per-direction patch state
rep("    logic        dec_seen [2], dec_fwd [2];\n",
    "    logic        dec_seen [2], dec_fwd [2];\n"
    "    logic [1:0]  dec_pk [2];\n"
    "    logic [7:0]  dec_pfc [2], dec_pcode [2];\n"
    "    logic [15:0] dec_pcsum [2];\n"
    "    logic [10:0] dec_off_fc [2], dec_off_code [2], dec_off_csum [2];\n"
    "    logic [1:0]  tx_pk [2];\n"
    "    logic [7:0]  tx_pfc [2], tx_pcode [2];\n"
    "    logic [15:0] tx_pcsum [2];\n"
    "    logic [10:0] tx_off_fc [2], tx_off_code [2], tx_off_csum [2];\n"
    "    logic [31:0] c_mut, c_rst;\n")

# ---- decision capture
rep("                if (g_dvalid && owner == d[0]) begin dec_seen[d] <= 1'b1; dec_fwd[d] <= g_fwd; end\n",
    "                if (g_dvalid && owner == d[0]) begin\n"
    "                    dec_seen[d] <= 1'b1; dec_fwd[d] <= g_fwd; dec_pk[d] <= g_patch;\n"
    "                    dec_pfc[d] <= g_pfc; dec_pcode[d] <= g_pcode; dec_pcsum[d] <= g_pcsum;\n"
    "                    dec_off_fc[d] <= g_off_fc; dec_off_code[d] <= g_off_code; dec_off_csum[d] <= g_off_csum;\n"
    "                end\n")

# ---- E_DECIDE: transmit when forwarded or mutated
old = s[s.index("                E_DECIDE: if (dec_seen[d] || (g_dvalid && owner == d[0])) begin"):s.index("                E_TX: if (!tx_busy[d] && !tx_go[d]) es[d] <= E_IDLE;")]
new = '''                E_DECIDE: if (dec_seen[d] || (g_dvalid && owner == d[0])) begin
                    if ((dec_seen[d] ? dec_fwd[d] : g_fwd) || (dec_seen[d] ? dec_pk[d] : g_patch) == 2'd1) begin
                        tx_go[d] <= 1'b1; tx_len[d] <= blen[d];
                        if (dec_seen[d] ? dec_fwd[d] : g_fwd) c_fwd[d] <= c_fwd[d] + 1;
                        tx_pk[d]       <= dec_seen[d] ? dec_pk[d]       : g_patch;
                        tx_pfc[d]      <= dec_seen[d] ? dec_pfc[d]      : g_pfc;
                        tx_pcode[d]    <= dec_seen[d] ? dec_pcode[d]    : g_pcode;
                        tx_pcsum[d]    <= dec_seen[d] ? dec_pcsum[d]    : g_pcsum;
                        tx_off_fc[d]   <= dec_seen[d] ? dec_off_fc[d]   : g_off_fc;
                        tx_off_code[d] <= dec_seen[d] ? dec_off_code[d] : g_off_code;
                        tx_off_csum[d] <= dec_seen[d] ? dec_off_csum[d] : g_off_csum;
                        es[d] <= E_TX;
                    end else begin
                        c_drop[d] <= c_drop[d] + 1;
                        es[d] <= E_IDLE;
                    end
                end
'''
s = s.replace(old, new, 1)

# ---- statistics: 24 rule counters, mutation counters
old = s[s.index("    // decision statistics"):s.index("    // ------------------------------------------------ transmit")]
new = '''    // decision statistics
    for (genvar r = 0; r < 16; r++) begin : g_rule_cnt
        always_ff @(posedge clk)
            if (rst) c_rule[r] <= 0;
            else if (g_dvalid && g_rule == r) c_rule[r] <= c_rule[r] + 1;
    end
    logic [31:0] c_rule2 [8];
    for (genvar r = 0; r < 8; r++) begin : g_rule_cnt2
        always_ff @(posedge clk)
            if (rst) c_rule2[r] <= 0;
            else if (g_dvalid && g_rule == 5'(16 + r)) c_rule2[r] <= c_rule2[r] + 1;
    end
    always_ff @(posedge clk) begin
        if (rst) begin
            last_dec <= 0; last_txid <= 0; c_mut <= 0; c_rst <= 0;
        end else if (g_dvalid) begin
            last_dec <= {16'd0, g_fc, g_fwd, owner, g_class, g_rule[2:0]} | {11'd0, g_rule, 16'd0};
            last_txid <= {16'd0, g_txid};
            if (g_patch == 2'd1) c_mut <= c_mut + 1;
            if (g_patch == 2'd2) c_rst <= c_rst + 1;
        end
    end

'''
s = s.replace(old, new, 1)

# ---- transmit with patch and FCS regeneration
old = s[s.index("    // ------------------------------------------------ transmit"):s.index("    assign txd_b = txd[0]; assign tx_en_b = txen[0];")]
new = '''    // ------------------------------------------------ transmit (direction 0 -> port B, 1 -> port A)
    // A frame with a patch descriptor has up to three fields rewritten while it is streamed out and its
    // Ethernet FCS regenerated (CRC-32 over the rewritten bytes replaces the 4 stored FCS bytes).
    logic [7:0]  txd [2];
    logic        txen [2];
    for (genvar d = 0; d < 2; d++) begin : g_tx
        import gate_eth_pkg::*;
        typedef enum logic [1:0] {T_IDLE, T_PRE, T_DATA, T_IFG} tst_t;
        tst_t ts;
        logic [10:0] ti;
        logic [3:0]  pc;
        logic [7:0]  rdb, ob;
        logic [31:0] crc;
        wire         ce = (d == 0) ? tx_ce_b : tx_ce_a;   // direction 0 transmits on port B
        wire  [10:0] fcs0 = tx_len[d] - 11'd4;
        wire  [31:0] crc_fin = ~crc;
        always_comb begin
            ob = rdb;
            if (tx_pk[d] != 2'd0) begin
                if (ti == tx_off_fc[d]) ob = tx_pfc[d];
                if (tx_pk[d] == 2'd2 && ti == tx_off_code[d]) ob = tx_pcode[d];
                if (ti == tx_off_csum[d]) ob = tx_pcsum[d][15:8];
                if (ti == tx_off_csum[d] + 11'd1) ob = tx_pcsum[d][7:0];
                if (ti >= fcs0) ob = crc_fin[8 * (ti - fcs0) +: 8];
            end
        end
        always_ff @(posedge clk) begin
            rdb <= (d == 0) ? buf0[(ts == T_DATA) ? (ce ? ti + 11'd1 : ti) : 11'd0]
                            : buf1[(ts == T_DATA) ? (ce ? ti + 11'd1 : ti) : 11'd0];
            tx_start[d] <= 1'b0;
            if (rst) begin
                ts <= T_IDLE; tx_busy[d] <= 0; txen[d] <= 0; txd[d] <= 0; c_tx[d] <= 0;
            end else begin
                case (ts)
                T_IDLE: begin
                    txen[d] <= 0;
                    if (tx_go[d]) begin ts <= T_PRE; pc <= 0; tx_busy[d] <= 1; end
                end
                T_PRE: if (ce) begin
                    txen[d] <= 1;
                    txd[d] <= (pc == 4'd7) ? 8'hD5 : 8'h55;
                    if (pc == 4'd0) tx_start[d] <= 1'b1;
                    if (pc == 4'd7) begin ts <= T_DATA; ti <= 0; crc <= 32'hFFFF_FFFF; end
                    pc <= pc + 1;
                end
                T_DATA: if (ce) begin
                    txen[d] <= 1;
                    txd[d] <= ob;
                    if (!(tx_pk[d] != 2'd0 && ti >= fcs0)) crc <= crc_byte(crc, ob);
                    if (ti == tx_len[d] - 11'd1) begin ts <= T_IFG; pc <= 0; c_tx[d] <= c_tx[d] + 1; end
                    ti <= ti + 1;
                end
                T_IFG: if (ce) begin
                    txen[d] <= 0;
                    if (pc == 4'd11) begin ts <= T_IDLE; tx_busy[d] <= 0; end
                    pc <= pc + 1;
                end
                endcase
            end
        end
    end
'''
s = s.replace(old, new, 1)

# ---- status words
rep("            8'd21: st_rdata <= {16'(g_lvl), g_act[0]};\n            8'd22: st_rdata <= {g_act[1], g_act[2]};\n            8'd23: st_rdata <= {16'd0, g_act[3]};\n",
    "            8'd21: st_rdata <= {16'(g_lvl), g_v0[0]};\n            8'd22: st_rdata <= {g_v0[1], g_v0[2]};\n            8'd23: st_rdata <= {16'd0, g_v0[3]};\n"
    "            8'd24: st_rdata <= c_rule2[0]; 8'd25: st_rdata <= c_rule2[1];\n"
    "            8'd26: st_rdata <= c_rule2[2]; 8'd27: st_rdata <= c_rule2[3];\n"
    "            8'd28: st_rdata <= c_mut;      8'd29: st_rdata <= c_rst;\n"
    "            8'd30: st_rdata <= {12'd0, g_ndenied, g_nreads, g_npend, g_wild, g_unc, 3'd0, g_lvl_ok};\n"
    "            8'd31: st_rdata <= g_slast;\n")
Path("rtl/v2/gate/bridge/gate_bridge_core_v3.sv").write_text(s, encoding="utf-8")
print("gate_bridge_core_v3.sv written,", s.count("\n"), "lines")
