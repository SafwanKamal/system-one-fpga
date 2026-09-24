// Nexys 4 DDR: System One classifier behind 100 Mbps raw Ethernet.
//
// A host sends classify-request frames (EtherType 0x88B5) with the text; the board
// answers each with a result frame carrying the class, the top two logits and all
// 151 logits. See src/sysone/ethernet_protocol.py and scripts/sysone_ethernet_client.py.
//
// Clocking, PHY clock forwarding and reset are the same as Genome-Classifier's
// ethernet_test_top_hardened, which is the arrangement known to work on this board:
// 100 MHz in -> MMCM -> 50 MHz logic clock, forwarded inverted to the PHY through
// an ODDR so the PHY samples our transmit data halfway between updates. On receive,
// the PHY launches on its rising edge, which is our falling edge, and rmii_RX
// captures on the next falling edge.
//
// LEDs:
//   0  MMCM locked
//   1  PHY out of reset
//   2  toggles once per result sent
//   3  a frame arrived while one was held, or transmit underflow/overflow (sticky)
//   4  a frame failed its FCS or framing (sticky; any bad frame on the wire sets it)
//   5  on while a request is being processed
module sysone_top (
    input  logic clk_100MHz,
    input  logic reset,
    output wire  PHY_ref_clk,
    output logic PHY_reset_n,
    input  wire [1:0] rmii_rxd,
    input  wire  rmii_crs_dv,
    input  wire  rmii_rx_er,
    output wire [1:0] rmii_txd,
    output wire  rmii_tx_en,
    output wire  PHY_MDC,
    inout  wire  PHY_MDIO,
    output logic [5:0] LED
);

    `include "model_parameters.svh"

    wire clk_input, clk_feedback, clk_feedback_buf;
    wire clk_50MHz_raw, clk_50MHz, clock_locked;
    wire reset_request = reset || !clock_locked;
    (* ASYNC_REG = "TRUE" *) logic [1:0] reset_sync_reg = 2'b11;
    wire core_reset = reset_sync_reg[1];

    // 100 mhz input -> 1000 mhz vco -> 50 mhz logic clock
    // The xilinx clocking primitives keep every clock on the dedicated clock routing,
    // so there is no variable LUT delay in the clock paths.
    IBUF input_clock_buffer (.I(clk_100MHz), .O(clk_input));
    MMCME2_BASE #(
        .CLKIN1_PERIOD(10.0), .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(10.0), .CLKOUT0_DIVIDE_F(20.0),
        .CLKOUT0_PHASE(0.0), .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_input), .CLKFBIN(clk_feedback_buf),
        .CLKFBOUT(clk_feedback), .CLKOUT0(clk_50MHz_raw),
        .LOCKED(clock_locked), .PWRDWN(1'b0), .RST(reset)
    );
    BUFG feedback_buffer (.I(clk_feedback), .O(clk_feedback_buf));
    BUFG logic_clock_buffer (.I(clk_50MHz_raw), .O(clk_50MHz));

    // phy samples halfway between our rising-edge data updates
    ODDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT(1'b0), .SRTYPE("SYNC"))
    PHY_clock_forward (
        .C(clk_50MHz), .CE(1'b1), .D1(1'b0), .D2(1'b1),
        .Q(PHY_ref_clk), .R(1'b0), .S(1'b0)
    );

    // assert asynchronously; release on the 50 mhz clock
    always_ff @(posedge clk_50MHz or posedge reset_request) begin
        if (reset_request)
            reset_sync_reg <= 2'b11;
        else
            reset_sync_reg <= {reset_sync_reg[0], 1'b0};
    end


    // 50 ms PHY reset with the reference clock running, then release
    localparam logic [21:0] PHY_RESET_CYCLES = 22'd2_500_000;

    logic [21:0] PHY_timer_reg, PHY_timer_next;
    logic PHY_reset_n_reg, PHY_reset_n_next;

    logic busy, served_toggle, rx_error, dropped, tx_error;

    always_ff @(posedge clk_50MHz or posedge core_reset) begin
        if (core_reset) begin
            PHY_timer_reg <= '0;
            PHY_reset_n_reg <= 1'b0;
        end else begin
            PHY_timer_reg <= PHY_timer_next;
            PHY_reset_n_reg <= PHY_reset_n_next;
        end
    end

    always_comb begin
        PHY_timer_next = PHY_timer_reg;
        PHY_reset_n_next = PHY_reset_n_reg;

        if (!PHY_reset_n_reg) begin
            if (PHY_timer_reg == PHY_RESET_CYCLES - 1'b1) begin
                PHY_reset_n_next = 1'b1;
            end else begin
                PHY_timer_next = PHY_timer_reg + 1'b1;
            end
        end
    end


    // The core is held in reset with the PHY, so it never sees a half-received frame
    sysone_ethernet_core #(
        .ROW_NUMBER      (MODEL_ROW_NUMBER),
        .DIMENSION       (MODEL_DIMENSION),
        .HIDDEN          (MODEL_HIDDEN),
        .CLASS_NUMBER    (MODEL_CLASS_NUMBER),
        .MAXIMUM_FEATURES(MODEL_MAXIMUM_FEATURES),
        .POOL_GAIN       (MODEL_POOL_GAIN)
    ) sysone_ethernet_core_inst (
        .clk              (clk_50MHz),
        .reset            (core_reset || !PHY_reset_n_reg),
        .rmii_rxd         (rmii_rxd),
        .rmii_crs_dv      (rmii_crs_dv),
        .rmii_rx_er       (rmii_rx_er),
        .rmii_txd         (rmii_txd),
        .rmii_tx_en       (rmii_tx_en),
        .busy_out         (busy),
        .served_toggle_out(served_toggle),
        .rx_error_out     (rx_error),
        .dropped_out      (dropped),
        .tx_error_out     (tx_error)
    );


    // retain the board's default phy auto-negotiation straps
    assign PHY_MDC = 1'b0;
    assign PHY_MDIO = 1'bz;
    assign PHY_reset_n = PHY_reset_n_reg;
    assign LED = {busy, rx_error, dropped || tx_error, served_toggle, PHY_reset_n_reg, clock_locked};

endmodule
