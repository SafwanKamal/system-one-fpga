// Everything between the pins and the gate except clock generation and pad buffers
// (simulatable).  Port A = agent side (pl_gem2, J10B), port B = plant side (pl_gem3, J10A).
module gate_bridge_io #(
    parameter int MDIO_DIV = 25,
    parameter int MDIO_RESET_CYC = 1_250_000,
    parameter int MDIO_SETTLE_CYC = 12_500_000,
    parameter int MDIO_POLL_CYC = 1_250_000,
    parameter int MS_DIV = 125_000,
    // ---- test builds only (production: LOOPBACK = 0, TEST_INJECT = 0)
    parameter bit    LOOPBACK = 1'b0,
    parameter bit    TEST_INJECT = 1'b0,
    parameter string INJ_ROM_FILE = "gate_inject_rom.hex",
    parameter int    INJ_START_CYC = 125_000_000,
    parameter int    INJ_GAP_CYC = 2500,
    parameter logic [15:0] RGMIICTL = 16'h00D3,
    parameter bit    ADV_1000 = 1'b0,
    parameter int    RX_IDELAY_PS = 0        // hardware: data/ctl input delay (needs IDELAYCTRL)
) (
    input  logic        clk125,
    input  logic        rst,           // core-domain synchronous reset
    input  logic [31:0] clk_status,
    // port A
    input  logic        a_rxc, input logic [3:0] a_rd, input logic a_rx_ctl,
    output logic        a_txc, output logic [3:0] a_td, output logic a_tx_ctl,
    output logic        a_rst_n, a_mdc, a_mdio_o, a_mdio_t, input logic a_mdio_i,
    // port B
    input  logic        b_rxc, input logic [3:0] b_rd, input logic b_rx_ctl,
    output logic        b_txc, output logic [3:0] b_td, output logic b_tx_ctl,
    output logic        b_rst_n, b_mdc, b_mdio_o, b_mdio_t, input logic b_mdio_i,
    // status
    input  logic [7:0]  st_addr,
    output logic [31:0] st_rdata
);
    logic [7:0] rxd_a, rxd_b, txd_a, txd_b;
    logic       dv_a, er_a, dv_b, er_b, en_a, en_b, ce_rx_a, ce_rx_b, ce_tx_a, ce_tx_b;
    logic [1:0] spd_a, spd_b;

    gate_rgmii_rx #(.IDELAY_PS(RX_IDELAY_PS)) u_rxa (.rxc(a_rxc), .rd(a_rd), .rx_ctl(a_rx_ctl), .speed(spd_a), .rxd(rxd_a), .rx_dv(dv_a), .rx_er(er_a), .rx_ce(ce_rx_a));
    gate_rgmii_rx #(.IDELAY_PS(RX_IDELAY_PS)) u_rxb (.rxc(b_rxc), .rd(b_rd), .rx_ctl(b_rx_ctl), .speed(spd_b), .rxd(rxd_b), .rx_dv(dv_b), .rx_er(er_b), .rx_ce(ce_rx_b));
    logic [7:0] otxd_a, otxd_b;
    logic       oen_a, oen_b;
    gate_rgmii_tx u_txa (.clk(clk125), .speed(spd_a), .txd(otxd_a), .tx_en(oen_a), .tx_ce(ce_tx_a), .txc(a_txc), .td(a_td), .tx_ctl(a_tx_ctl));
    gate_rgmii_tx u_txb (.clk(clk125), .speed(spd_b), .txd(otxd_b), .tx_en(oen_b), .tx_ce(ce_tx_b), .txc(b_txc), .td(b_td), .tx_ctl(b_tx_ctl));

    // reset synchronizers into each receive clock domain
    (* ASYNC_REG = "TRUE" *) logic [2:0] ra_s = 3'b111, rb_s = 3'b111;
    always_ff @(posedge a_rxc) ra_s <= {ra_s[1:0], rst};
    always_ff @(posedge b_rxc) rb_s <= {rb_s[1:0], rst};

    logic [31:0] ext [16];
    logic [31:0] ma_ctrl, ma_id, ma_stat, ma_cfg, mb_ctrl, mb_id, mb_stat, mb_cfg;
    logic        inj_active, inj_port, inj_en, inj_done;
    logic [7:0]  inj_txd;
    logic [31:0] inj_sent;

    gate_mdio #(.DIV(MDIO_DIV), .RESET_CYC(MDIO_RESET_CYC), .SETTLE_CYC(MDIO_SETTLE_CYC),
                .POLL_CYC(MDIO_POLL_CYC), .LOOPBACK(LOOPBACK), .RGMIICTL(RGMIICTL), .ADV_1000(ADV_1000)) u_mdio_a (
        .clk(clk125), .rst(rst), .phy_rst_n(a_rst_n), .mdc(a_mdc), .mdio_o(a_mdio_o),
        .mdio_t(a_mdio_t), .mdio_i(a_mdio_i), .st_ctrl(ma_ctrl), .st_id(ma_id), .st_stat(ma_stat),
        .st_cfg(ma_cfg));
    gate_mdio #(.DIV(MDIO_DIV), .RESET_CYC(MDIO_RESET_CYC), .SETTLE_CYC(MDIO_SETTLE_CYC),
                .POLL_CYC(MDIO_POLL_CYC), .LOOPBACK(LOOPBACK), .RGMIICTL(RGMIICTL), .ADV_1000(ADV_1000)) u_mdio_b (
        .clk(clk125), .rst(rst), .phy_rst_n(b_rst_n), .mdc(b_mdc), .mdio_o(b_mdio_o),
        .mdio_t(b_mdio_t), .mdio_i(b_mdio_i), .st_ctrl(mb_ctrl), .st_id(mb_id), .st_stat(mb_stat),
        .st_cfg(mb_cfg));

    always_comb begin
        for (int i = 0; i < 16; i++) ext[i] = 32'h0;
        ext[0] = clk_status;
        ext[1] = ma_ctrl; ext[2] = ma_id; ext[3] = ma_stat; ext[4] = ma_cfg;
        ext[5] = mb_ctrl; ext[6] = mb_id; ext[7] = mb_stat; ext[8] = mb_cfg;
        ext[9] = {TEST_INJECT, LOOPBACK, inj_done, 5'd0, inj_sent[23:0]};
    end

    // negotiated speed per port (PHYSTS[15:14]); loopback test builds run at 1000 Mb/s
    localparam logic [1:0] LOOP_SPD = ADV_1000 ? 2'b10 : 2'b01;
    assign spd_a = LOOPBACK ? LOOP_SPD : ma_ctrl[6:5];
    assign spd_b = LOOPBACK ? LOOP_SPD : mb_ctrl[6:5];

    // ---- test-only injector (absent from production builds)
    if (TEST_INJECT) begin : g_inj
        logic [31:0] wait_cnt;
        logic        go;
        always_ff @(posedge clk125) begin
            if (rst) begin wait_cnt <= 0; go <= 0; end
            else if (ma_ctrl[8] && mb_ctrl[8]) begin            // both PHYs configured
                if (wait_cnt == 32'(INJ_START_CYC)) go <= 1; else wait_cnt <= wait_cnt + 1;
            end
        end
        gate_test_injector #(.ROM_FILE(INJ_ROM_FILE), .GAP_CYC(INJ_GAP_CYC)) u_inj (
            .clk(clk125), .rst(rst), .start(go), .ce(inj_port ? ce_tx_b : ce_tx_a), .active(inj_active), .port(inj_port),
            .txd(inj_txd), .txen(inj_en), .n_sent(inj_sent), .done(inj_done));
    end else begin : g_noinj
        assign inj_active = 1'b0; assign inj_port = 1'b0; assign inj_txd = 8'h00;
        assign inj_en = 1'b0; assign inj_sent = 32'd0; assign inj_done = 1'b0;
    end
    assign otxd_a = (inj_active && !inj_port) ? inj_txd : txd_a;
    assign oen_a  = (inj_active && !inj_port) ? inj_en  : en_a;
    assign otxd_b = (inj_active &&  inj_port) ? inj_txd : txd_b;
    assign oen_b  = (inj_active &&  inj_port) ? inj_en  : en_b;

    gate_bridge_core #(.MS_DIV(MS_DIV)) u_core (
        .clk(clk125), .rst(rst),
        .rxc_a(a_rxc), .rrst_a(ra_s[2]), .rxd_a(rxd_a), .rx_dv_a(dv_a), .rx_er_a(er_a), .rx_ce_a(ce_rx_a),
        .rxc_b(b_rxc), .rrst_b(rb_s[2]), .rxd_b(rxd_b), .rx_dv_b(dv_b), .rx_er_b(er_b), .rx_ce_b(ce_rx_b),
        .txd_a(txd_a), .txd_b(txd_b), .tx_en_a(en_a), .tx_en_b(en_b), .tx_ce_a(ce_tx_a), .tx_ce_b(ce_tx_b),
        .st_addr(st_addr), .st_rdata(st_rdata), .st_ext(ext));
endmodule
