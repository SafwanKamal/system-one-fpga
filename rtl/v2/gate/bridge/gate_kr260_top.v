// KR260 chip top: the PS block design (board preset, AXI master for the status window)
// plus the gate bridge on the two PL Ethernet PHYs.
module gate_kr260_top #(
    parameter LOOPBACK = 0,
    parameter TEST_INJECT = 0,
    parameter INJ_ROM_FILE = "gate_inject_rom.hex"
) (
    input  wire       clk25,
    input  wire       a_rxc, input wire [3:0] a_rd, input wire a_rx_ctl,
    output wire       a_txc, output wire [3:0] a_td, output wire a_tx_ctl,
    output wire       a_rst_n, output wire a_mdc, inout wire a_mdio,
    input  wire       b_rxc, input wire [3:0] b_rd, input wire b_rx_ctl,
    output wire       b_txc, output wire [3:0] b_td, output wire b_tx_ctl,
    output wire       b_rst_n, output wire b_mdc, inout wire b_mdio
);
    wire        clk125, locked, aresetn, pl_resetn;
    wire [39:0] araddr, awaddr;
    wire        arvalid, arready, rvalid, rready, awvalid, awready, wvalid, wready, bvalid, bready;
    wire [31:0] rdata, wdata;
    wire [1:0]  rresp, bresp;
    wire [3:0]  wstrb;

    system_wrapper u_ps (
        .axi_clk(clk125), .axi_locked(locked), .axi_aresetn(aresetn), .pl_resetn(pl_resetn),
        .M_AXI_araddr(araddr), .M_AXI_arprot(), .M_AXI_arready(arready), .M_AXI_arvalid(arvalid),
        .M_AXI_rdata(rdata), .M_AXI_rready(rready), .M_AXI_rresp(rresp), .M_AXI_rvalid(rvalid),
        .M_AXI_awaddr(awaddr), .M_AXI_awprot(), .M_AXI_awready(awready), .M_AXI_awvalid(awvalid),
        .M_AXI_wdata(wdata), .M_AXI_wready(wready), .M_AXI_wstrb(wstrb), .M_AXI_wvalid(wvalid),
        .M_AXI_bready(bready), .M_AXI_bresp(bresp), .M_AXI_bvalid(bvalid));

    gate_bridge_top #(.LOOPBACK(LOOPBACK), .TEST_INJECT(TEST_INJECT), .INJ_ROM_FILE(INJ_ROM_FILE)) u_gate (
        .clk25(clk25), .ext_rst_n(pl_resetn),
        .a_rxc(a_rxc), .a_rd(a_rd), .a_rx_ctl(a_rx_ctl), .a_txc(a_txc), .a_td(a_td), .a_tx_ctl(a_tx_ctl),
        .a_rst_n(a_rst_n), .a_mdc(a_mdc), .a_mdio(a_mdio),
        .b_rxc(b_rxc), .b_rd(b_rd), .b_rx_ctl(b_rx_ctl), .b_txc(b_txc), .b_td(b_td), .b_tx_ctl(b_tx_ctl),
        .b_rst_n(b_rst_n), .b_mdc(b_mdc), .b_mdio(b_mdio),
        .clk125_out(clk125), .locked_out(locked), .s_axi_aresetn(aresetn),
        .s_axi_araddr(araddr[9:0]), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .s_axi_awaddr(awaddr[9:0]), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready));
endmodule
