// Loopback test build in simulation: both ports' TX pins are wired to their own RX pins
// (with the PHY's 2 ns clock delay), the MDIO models accept the loopback BMCR, the
// test injector replays its ROM, and the status counters are printed for comparison
// with build/v2/agent-gate-bridge/inject/expected.json.
module gate_loop_tb;
    logic clk125 = 0;
    always #4 clk125 = ~clk125;
    logic rst = 1;

    logic a_txc, b_txc, a_tx_ctl, b_tx_ctl;
    logic [3:0] a_td, b_td;
    logic a_rxc, b_rxc;
    assign #2 a_rxc = a_txc;          // PHY loopback: clock returned with RX delay
    assign #2 b_rxc = b_txc;
    logic a_rst_n, b_rst_n, a_mdc, b_mdc, a_mdio_o, b_mdio_o, a_mdio_t, b_mdio_t, a_mdio_i, b_mdio_i;
    logic [7:0] st_addr = 0;
    logic [31:0] st_rdata;
    string rom;

    gate_bridge_io #(.MDIO_DIV(2), .MDIO_RESET_CYC(50), .MDIO_SETTLE_CYC(100), .MDIO_POLL_CYC(3000),
                     .MS_DIV(32'h7FFF_FFFF), .LOOPBACK(1'b1), .TEST_INJECT(1'b1),
                     .INJ_ROM_FILE("gate_inject_rom.hex"), .INJ_START_CYC(1000), .INJ_GAP_CYC(12500)) dut (
        .clk125(clk125), .rst(rst), .clk_status(32'h3),
        .a_rxc(a_rxc), .a_rd(a_td), .a_rx_ctl(a_tx_ctl), .a_txc(a_txc), .a_td(a_td), .a_tx_ctl(a_tx_ctl),
        .a_rst_n(a_rst_n), .a_mdc(a_mdc), .a_mdio_o(a_mdio_o), .a_mdio_t(a_mdio_t), .a_mdio_i(a_mdio_i),
        .b_rxc(b_rxc), .b_rd(b_td), .b_rx_ctl(b_tx_ctl), .b_txc(b_txc), .b_td(b_td), .b_tx_ctl(b_tx_ctl),
        .b_rst_n(b_rst_n), .b_mdc(b_mdc), .b_mdio_o(b_mdio_o), .b_mdio_t(b_mdio_t), .b_mdio_i(b_mdio_i),
        .st_addr(st_addr), .st_rdata(st_rdata));

    mdio_phy_model #(.ADDR(4)) pa (.mdc(a_mdc), .mdio_t(a_mdio_t), .mdio_o(a_mdio_o), .mdio_i(a_mdio_i));
    mdio_phy_model #(.ADDR(6)) pb (.mdc(b_mdc), .mdio_t(b_mdio_t), .mdio_o(b_mdio_o), .mdio_i(b_mdio_i));

    task automatic rd(input logic [7:0] a, output logic [31:0] v);
        @(negedge clk125); st_addr = a; @(posedge clk125); @(posedge clk125); #1; v = st_rdata;
    endtask

    initial begin
        logic [31:0] v;
        int t;
        repeat (10) @(posedge clk125);
        rst = 0;
        t = 0;
        do begin
            repeat (5000) @(posedge clk125);
            rd(8'd57, v);
            t++;
        end while (!v[29] && t < 40000);
        repeat (5000) @(posedge clk125);
        $display("BMCR A=%h B=%h (expect 6100 at 100 Mb/s)", pa.regs[0], pb.regs[0]);
        $display("injector status %h", v);
        for (int a = 2; a < 48; a++) begin
            if (a < 16 || a >= 32) begin rd(a[7:0], v); $display("STATUS %0d %0d", a, v); end
        end
        rd(8'd21, v); $display("STATUS_LVL_ACT0 %h", v);
        rd(8'd22, v); $display("STATUS_ACT12 %h", v);
        rd(8'd23, v); $display("STATUS_ACT3 %h", v);
        $finish;
    end
endmodule
