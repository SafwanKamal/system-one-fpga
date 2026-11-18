// Two-port store-and-forward Ethernet bridge with the v3 agent gate (acceptance tracking) in the path.
// Generated from gate_bridge_core.sv by scripts/v2/gate/make_bridge_v3.py; differences: gate_core_v3, and
// refused requests are not dropped but mutated (illegal function code, same length) and the PLC's reply is
// restored; mutated frames get a corrected TCP checksum from the gate and a freshly computed Ethernet FCS here.
//   port A = agent side (KR260 J10B, pl_gem2), port B = plant side (J10A, pl_gem3)
//   direction 0: A -> gate -> B   (requests, gated)
//   direction 1: B -> gate -> A   (responses, update plant state)
// Frames are received into per-port dual-clock FIFOs, then streamed once into a
// per-direction buffer while the shared gate_core inspects them; forwarded frames are
// retransmitted byte-identical (including the original FCS) with a fresh preamble.
// Status: read-only 32-bit register file (no write path into the gate).
module gate_bridge_core_v3 #(
    parameter int FIFO_AW = 12,
    parameter int MS_DIV = 125_000
) (
    input  logic        clk,          // 125 MHz core / TX clock
    input  logic        rst,
    // port A receive (rxc domain)
    input  logic        rxc_a, rrst_a,
    input  logic [7:0]  rxd_a,
    input  logic        rx_dv_a, rx_er_a, rx_ce_a,
    // port B receive
    input  logic        rxc_b, rrst_b,
    input  logic [7:0]  rxd_b,
    input  logic        rx_dv_b, rx_er_b, rx_ce_b,
    // transmit (core domain)
    output logic [7:0]  txd_a, txd_b,
    output logic        tx_en_a, tx_en_b,
    input  logic        tx_ce_a, tx_ce_b,     // byte request strobes from the RGMII TX
    // status read port (core domain, 1-cycle latency)
    input  logic [7:0]  st_addr,
    output logic [31:0] st_rdata,
    input  logic [31:0] st_ext [16]   // externally supplied status words (MDIO, clocks)
);
    // ------------------------------------------------ ingress
    logic [7:0]  d_data [2];
    logic        d_empty [2], d_ren [2];
    logic [11:0] q_len [2];
    logic        q_good [2], q_empty [2], q_ren [2];
    logic [31:0] rx_frames [2], rx_bad [2], rx_ovf [2];

    gate_eth_rx #(.AW(FIFO_AW)) u_rx_a (
        .rxc(rxc_a), .rrst_rx(rrst_a), .rxd(rxd_a), .rx_dv(rx_dv_a), .rx_er(rx_er_a), .rx_ce(rx_ce_a),
        .clk(clk), .rst(rst), .d_ren(d_ren[0]), .d_rdata(d_data[0]), .d_rempty(d_empty[0]),
        .q_ren(q_ren[0]), .q_len(q_len[0]), .q_good(q_good[0]), .q_rempty(q_empty[0]),
        .cnt_frames(rx_frames[0]), .cnt_bad(rx_bad[0]), .cnt_overflow(rx_ovf[0]));
    gate_eth_rx #(.AW(FIFO_AW)) u_rx_b (
        .rxc(rxc_b), .rrst_rx(rrst_b), .rxd(rxd_b), .rx_dv(rx_dv_b), .rx_er(rx_er_b), .rx_ce(rx_ce_b),
        .clk(clk), .rst(rst), .d_ren(d_ren[1]), .d_rdata(d_data[1]), .d_rempty(d_empty[1]),
        .q_ren(q_ren[1]), .q_len(q_len[1]), .q_good(q_good[1]), .q_rempty(q_empty[1]),
        .cnt_frames(rx_frames[1]), .cnt_bad(rx_bad[1]), .cnt_overflow(rx_ovf[1]));

    // ------------------------------------------------ time base for the gate (1 ms)
    logic [31:0] t_ms;
    logic [31:0] ms_div;
    logic [31:0] cyc;
    always_ff @(posedge clk) begin
        if (rst) begin t_ms <= 0; ms_div <= 0; cyc <= 0; end
        else begin
            cyc <= cyc + 1;
            if (ms_div == 32'(MS_DIV - 1)) begin ms_div <= 0; t_ms <= t_ms + 1; end
            else ms_div <= ms_div + 1;
        end
    end

    // ------------------------------------------------ shared gate core
    logic        g_valid, g_last, g_dir, g_fcs;
    logic [7:0]  g_data;
    logic        g_dvalid, g_fwd;
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

    // ------------------------------------------------ per-direction engines
    typedef enum logic [2:0] {E_IDLE, E_LOAD, E_DECIDE, E_TX, E_DROPWAIT} est_t;
    est_t es [2];
    logic [10:0] bidx [2], blen [2];
    logic        bgood [2];
    (* ram_style = "block" *) logic [7:0] buf0 [2048];
    (* ram_style = "block" *) logic [7:0] buf1 [2048];
    logic        owner;          // which direction holds gate_core
    logic        busy_gate;
    logic [31:0] t_start [2];
    logic        tx_go [2], tx_busy [2];
    logic [10:0] tx_len [2];
    logic [31:0] c_loaded [2], c_fwd [2], c_drop [2], c_tx [2];
    logic [31:0] c_rule [16];
    logic [31:0] lat_last, lat_min, lat_max;
    logic [31:0] last_dec, last_txid;
    logic        tx_start [2];
    logic        dec_seen [2], dec_fwd [2];
    logic [1:0]  dec_pk [2];
    logic [7:0]  dec_pfc [2], dec_pcode [2];
    logic [15:0] dec_pcsum [2];
    logic [10:0] dec_off_fc [2], dec_off_code [2], dec_off_csum [2];
    logic [1:0]  tx_pk [2];
    logic [7:0]  tx_pfc [2], tx_pcode [2];
    logic [15:0] tx_pcsum [2];
    logic [10:0] tx_off_fc [2], tx_off_code [2], tx_off_csum [2];
    logic [31:0] c_mut, c_rst;

    // gate input mux (registered by the engines)
    always_comb begin
        g_valid = 1'b0; g_last = 1'b0; g_dir = owner; g_fcs = 1'b0; g_data = 8'h00;
        for (int d = 0; d < 2; d++) begin
            if (busy_gate && owner == d[0] && es[d] == E_LOAD && !d_empty[d] &&
                blen[d] >= 11'd5 && bidx[d] < blen[d] - 11'd4) begin
                g_valid = 1'b1;
                g_data  = d_data[d];
                g_last  = (bidx[d] == blen[d] - 11'd5);
                g_fcs   = bgood[d];
            end
        end
    end

    always_comb begin
        for (int d = 0; d < 2; d++) begin
            d_ren[d] = (es[d] == E_LOAD) && !d_empty[d] && (bidx[d] < blen[d]) &&
                       ((blen[d] >= 11'd5 && bidx[d] >= blen[d] - 11'd4) || (busy_gate && owner == d[0]));
            q_ren[d] = 1'b0;
        end
        // descriptors are popped when an engine starts a frame
        for (int d = 0; d < 2; d++)
            if (es[d] == E_IDLE && !q_empty[d] && !tx_busy[d] && !busy_gate &&
                (d == 0 || q_empty[0] || es[0] != E_IDLE || tx_busy[0])) q_ren[d] = 1'b1;
    end

    for (genvar d = 0; d < 2; d++) begin : g_eng
        always_ff @(posedge clk) begin
            tx_go[d] <= 1'b0;
            if (rst) begin
                es[d] <= E_IDLE; c_loaded[d] <= 0; c_fwd[d] <= 0; c_drop[d] <= 0; dec_seen[d] <= 0;
            end else begin
                if (g_dvalid && owner == d[0]) begin
                    dec_seen[d] <= 1'b1; dec_fwd[d] <= g_fwd; dec_pk[d] <= g_patch;
                    dec_pfc[d] <= g_pfc; dec_pcode[d] <= g_pcode; dec_pcsum[d] <= g_pcsum;
                    dec_off_fc[d] <= g_off_fc; dec_off_code[d] <= g_off_code; dec_off_csum[d] <= g_off_csum;
                end
                case (es[d])
                E_IDLE: if (q_ren[d]) begin
                    blen[d] <= q_len[d][10:0]; bgood[d] <= q_good[d]; bidx[d] <= 0; dec_seen[d] <= 1'b0;
                    t_start[d] <= cyc; c_loaded[d] <= c_loaded[d] + 1;
                    es[d] <= E_LOAD;
                end
                E_LOAD: begin
                    if (d_ren[d]) begin
                        if (d == 0) buf0[bidx[d]] <= d_data[d]; else buf1[bidx[d]] <= d_data[d];
                        bidx[d] <= bidx[d] + 1;
                    end
                    if (bidx[d] == blen[d] || (d_ren[d] && bidx[d] + 1 == blen[d])) begin
                        // runts (< 5 bytes) never reach the gate and are dropped
                        es[d] <= (blen[d] < 11'd5) ? E_DROPWAIT : E_DECIDE;
                    end
                end
                E_DECIDE: if (dec_seen[d] || (g_dvalid && owner == d[0])) begin
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
                E_TX: if (!tx_busy[d] && !tx_go[d]) es[d] <= E_IDLE;
                E_DROPWAIT: begin c_drop[d] <= c_drop[d] + 1; es[d] <= E_IDLE; end
                default: es[d] <= E_IDLE;
                endcase
            end
        end
    end

    // gate ownership: taken when an engine pops a descriptor, released on its decision
    always_ff @(posedge clk) begin
        if (rst) begin busy_gate <= 0; owner <= 0; end
        else begin
            if (!busy_gate) begin
                if (q_ren[0]) begin busy_gate <= 1; owner <= 0; end
                else if (q_ren[1]) begin busy_gate <= 1; owner <= 1; end
            end else if (es[owner] == E_DROPWAIT || g_dvalid) begin
                busy_gate <= 0;
            end
        end
    end

    // decision statistics
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

    // ------------------------------------------------ transmit (direction 0 -> port B, 1 -> port A)
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
    assign txd_b = txd[0]; assign tx_en_b = txen[0];
    assign txd_a = txd[1]; assign tx_en_a = txen[1];
    // added latency: descriptor visible in the core domain -> first preamble byte out
    always_ff @(posedge clk) begin
        if (rst) begin lat_min <= 0; lat_max <= 0; lat_last <= 0; end
        else begin
            for (int d = 0; d < 2; d++) begin
                if (tx_start[d]) begin
                    lat_last <= cyc - t_start[d];
                    if (lat_min == 0 || cyc - t_start[d] < lat_min) lat_min <= cyc - t_start[d];
                    if (cyc - t_start[d] > lat_max) lat_max <= cyc - t_start[d];
                end
            end
        end
    end

    // ------------------------------------------------ status (read-only)
    logic [31:0] rxs [6];
    always_ff @(posedge clk) begin   // two-stage sampling of rx-domain counters (debug only)
        rxs[0] <= rx_frames[0]; rxs[1] <= rx_bad[0]; rxs[2] <= rx_ovf[0];
        rxs[3] <= rx_frames[1]; rxs[4] <= rx_bad[1]; rxs[5] <= rx_ovf[1];
    end
    always_ff @(posedge clk) begin
        case (st_addr)
            8'd0:  st_rdata <= 32'h6A7E_0001;
            8'd1:  st_rdata <= t_ms;
            8'd2:  st_rdata <= rxs[0];   8'd3: st_rdata <= rxs[1];   8'd4: st_rdata <= rxs[2];
            8'd5:  st_rdata <= rxs[3];   8'd6: st_rdata <= rxs[4];   8'd7: st_rdata <= rxs[5];
            8'd8:  st_rdata <= c_loaded[0]; 8'd9:  st_rdata <= c_fwd[0];
            8'd10: st_rdata <= c_drop[0];   8'd11: st_rdata <= c_tx[0];
            8'd12: st_rdata <= c_loaded[1]; 8'd13: st_rdata <= c_fwd[1];
            8'd14: st_rdata <= c_drop[1];   8'd15: st_rdata <= c_tx[1];
            8'd16: st_rdata <= lat_last; 8'd17: st_rdata <= lat_min; 8'd18: st_rdata <= lat_max;
            8'd19: st_rdata <= last_dec; 8'd20: st_rdata <= last_txid;
            8'd21: st_rdata <= {16'(g_lvl), g_v0[0]};
            8'd22: st_rdata <= {g_v0[1], g_v0[2]};
            8'd23: st_rdata <= {16'd0, g_v0[3]};
            8'd24: st_rdata <= c_rule2[0]; 8'd25: st_rdata <= c_rule2[1];
            8'd26: st_rdata <= c_rule2[2]; 8'd27: st_rdata <= c_rule2[3];
            8'd28: st_rdata <= c_mut;      8'd29: st_rdata <= c_rst;
            8'd30: st_rdata <= {12'd0, g_ndenied, g_nreads, g_npend, g_wild, g_unc, 3'd0, g_lvl_ok};
            8'd31: st_rdata <= g_slast;
            default: begin
                if (st_addr >= 8'd32 && st_addr < 8'd48) st_rdata <= c_rule[st_addr[3:0]];
                else if (st_addr >= 8'd48 && st_addr < 8'd64) st_rdata <= st_ext[st_addr[3:0]];
                else st_rdata <= 32'hDEAD_0000 | {24'd0, st_addr};
            end
        endcase
    end
endmodule
