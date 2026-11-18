// KR260 top for the agent gate bridge (Verilog wrapper so it can be a block-design
// module reference).  Clocking is independent of the PS: 25 MHz HPA_CLK0P -> MMCM ->
// 125 MHz core/TX clock.  The PS sees only a read-only AXI4-Lite status window; writes
// are answered with SLVERR and change nothing.
module gate_bridge_top #(
    parameter LOOPBACK = 0,                 // test build only
    parameter TEST_INJECT = 0,              // test build only
    parameter INJ_ROM_FILE = "gate_inject_rom.hex",
    parameter integer INJ_START_CYC = 125000000,
    parameter integer INJ_GAP_CYC = 2500,
    parameter integer RX_IDELAY_PS = 0,       // RGMII RX data/ctl delay (needs IDELAYCTRL)
    parameter ADV_1000 = 0                    // 0: 10/100 Mb/s build (1000 needs a deskewed RX clock)
) (
    input  wire        clk25,
    input  wire        ext_rst_n,          // e.g. PS pl_resetn0 (phase 2 only)
    // port A = pl_gem2 (J10B), agent side
    input  wire        a_rxc,
    input  wire [3:0]  a_rd,
    input  wire        a_rx_ctl,
    output wire        a_txc,
    output wire [3:0]  a_td,
    output wire        a_tx_ctl,
    output wire        a_rst_n,
    output wire        a_mdc,
    inout  wire        a_mdio,
    // port B = pl_gem3 (J10A), plant side
    input  wire        b_rxc,
    input  wire [3:0]  b_rd,
    input  wire        b_rx_ctl,
    output wire        b_txc,
    output wire [3:0]  b_td,
    output wire        b_tx_ctl,
    output wire        b_rst_n,
    output wire        b_mdc,
    inout  wire        b_mdio,
    // AXI4-Lite slave (status, read-only), clocked by clk125_out
    output wire        clk125_out,
    output wire        locked_out,
    input  wire        s_axi_aresetn,
    input  wire [9:0]  s_axi_araddr,
    input  wire        s_axi_arvalid,
    output reg         s_axi_arready,
    output reg  [31:0] s_axi_rdata,
    output reg  [1:0]  s_axi_rresp,
    output reg         s_axi_rvalid,
    input  wire        s_axi_rready,
    input  wire [9:0]  s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output reg         s_axi_awready,
    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output reg         s_axi_wready,
    output reg  [1:0]  s_axi_bresp,
    output reg         s_axi_bvalid,
    input  wire        s_axi_bready
);
    // ---------------- clocks
    wire clk25_b, fb, fb_b, clk125_u, clk125, locked;
    BUFG u_b25 (.I(clk25), .O(clk25_b));
    MMCME4_BASE #(
        .CLKIN1_PERIOD(40.0), .DIVCLK_DIVIDE(1), .CLKFBOUT_MULT_F(40.0),   // VCO 1000 MHz
        .CLKOUT0_DIVIDE_F(8.0),                                           // 125 MHz
        .CLKOUT1_DIVIDE(3)                                                // 333.3 MHz IDELAYCTRL reference
    ) u_mmcm (
        .CLKIN1(clk25_b), .CLKFBIN(fb_b), .CLKFBOUT(fb), .CLKOUT0(clk125_u), .LOCKED(locked),
        .RST(1'b0), .PWRDWN(1'b0),
        .CLKFBOUTB(), .CLKOUT0B(), .CLKOUT1(clk333_u), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
        .CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6());
    BUFG u_bfb (.I(fb), .O(fb_b));
    BUFG u_b125 (.I(clk125_u), .O(clk125));
    wire clk333_u, clk333, idly_rdy;
    generate if (RX_IDELAY_PS > 0) begin : g_idlyctrl
        BUFG u_b333 (.I(clk333_u), .O(clk333));
        // IDELAYCTRL RST: asynchronous assert, synchronous release in the REFCLK domain
        (* ASYNC_REG = "TRUE" *) reg [7:0] ir = 8'hFF;
        always @(posedge clk333 or negedge locked)
            if (!locked) ir <= 8'hFF; else ir <= {ir[6:0], 1'b0};
        IDELAYCTRL #(.SIM_DEVICE("ULTRASCALE")) u_idlyctrl (.REFCLK(clk333), .RST(ir[7]), .RDY(idly_rdy));
    end else begin : g_noidly
        assign idly_rdy = 1'b0;
    end endgenerate
    assign clk125_out = clk125;
    assign locked_out = locked;

    wire a_rxc_b, b_rxc_b;
    BUFG u_brxa (.I(a_rxc), .O(a_rxc_b));
    BUFG u_brxb (.I(b_rxc), .O(b_rxc_b));

    // core reset: MMCM lock and the external reset, synchronized to clk125
    (* ASYNC_REG = "TRUE" *) reg [3:0] rst_s = 4'hF;
    always @(posedge clk125 or negedge locked)
        if (!locked) rst_s <= 4'hF;
        else rst_s <= {rst_s[2:0], ~ext_rst_n};
    wire rst = rst_s[3];

    // ---------------- MDIO pads
    wire a_mdio_o, a_mdio_t, a_mdio_i, b_mdio_o, b_mdio_t, b_mdio_i;
    IOBUF u_ioa (.I(a_mdio_o), .T(a_mdio_t), .O(a_mdio_i), .IO(a_mdio));
    IOBUF u_iob (.I(b_mdio_o), .T(b_mdio_t), .O(b_mdio_i), .IO(b_mdio));

    // ---------------- bridge
    reg  [7:0]  st_addr;
    wire [31:0] st_rdata;
    gate_bridge_io #(.LOOPBACK(LOOPBACK), .TEST_INJECT(TEST_INJECT), .INJ_ROM_FILE(INJ_ROM_FILE),
                     .INJ_START_CYC(INJ_START_CYC), .INJ_GAP_CYC(INJ_GAP_CYC),
                     .RX_IDELAY_PS(RX_IDELAY_PS), .ADV_1000(ADV_1000)) u_io (
        .clk125(clk125), .rst(rst), .clk_status({29'd0, idly_rdy, ext_rst_n, locked}),
        .a_rxc(a_rxc_b), .a_rd(a_rd), .a_rx_ctl(a_rx_ctl), .a_txc(a_txc), .a_td(a_td), .a_tx_ctl(a_tx_ctl),
        .a_rst_n(a_rst_n), .a_mdc(a_mdc), .a_mdio_o(a_mdio_o), .a_mdio_t(a_mdio_t), .a_mdio_i(a_mdio_i),
        .b_rxc(b_rxc_b), .b_rd(b_rd), .b_rx_ctl(b_rx_ctl), .b_txc(b_txc), .b_td(b_td), .b_tx_ctl(b_tx_ctl),
        .b_rst_n(b_rst_n), .b_mdc(b_mdc), .b_mdio_o(b_mdio_o), .b_mdio_t(b_mdio_t), .b_mdio_i(b_mdio_i),
        .st_addr(st_addr), .st_rdata(st_rdata));

    // ---------------- AXI4-Lite: reads return status word [addr/4]; writes -> SLVERR
    reg [1:0] rphase;
    always @(posedge clk125) begin
        if (!s_axi_aresetn) begin
            s_axi_arready <= 1'b0; s_axi_rvalid <= 1'b0; s_axi_rresp <= 2'b00; rphase <= 2'd0;
            s_axi_awready <= 1'b0; s_axi_wready <= 1'b0; s_axi_bvalid <= 1'b0; s_axi_bresp <= 2'b10;
        end else begin
            // read: accept address, wait two cycles for the registered status mux
            s_axi_arready <= 1'b0;
            case (rphase)
                2'd0: if (s_axi_arvalid && !s_axi_rvalid) begin
                          s_axi_arready <= 1'b1; st_addr <= s_axi_araddr[9:2]; rphase <= 2'd1;
                      end
                2'd1: rphase <= 2'd2;
                2'd2: begin s_axi_rdata <= st_rdata; s_axi_rvalid <= 1'b1; s_axi_rresp <= 2'b00; rphase <= 2'd3; end
                2'd3: if (s_axi_rready) begin s_axi_rvalid <= 1'b0; rphase <= 2'd0; end
            endcase
            // write: accept and reject
            s_axi_awready <= 1'b0; s_axi_wready <= 1'b0;
            if (s_axi_awvalid && s_axi_wvalid && !s_axi_bvalid && !s_axi_awready) begin
                s_axi_awready <= 1'b1; s_axi_wready <= 1'b1; s_axi_bvalid <= 1'b1; s_axi_bresp <= 2'b10;
            end else if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 1'b0;
        end
    end
endmodule
