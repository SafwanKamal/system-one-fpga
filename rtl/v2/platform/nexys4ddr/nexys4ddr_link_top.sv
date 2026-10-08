// Nexys 4 DDR, v2: read and write the DDR2 from the host over raw Ethernet
// (memory_link_core, bring-up step 2; this is how the encoder image gets into the
// DDR2) and, with ENCODER = 1, run the encoder on the link's RUN command
// (sysone_v2_core + encoder_system, step 5; the project's "encoder" top).
//
// Clocking: 100 MHz board clock -> MMCM (1000 MHz VCO)
//   CLKOUT0 200 MHz  MIG system clock (the MIG makes the 300 MHz DDR2 clock and the
//                    75 MHz ui_clk the memory side of the link runs on)
//   CLKOUT1  50 MHz  Ethernet / RMII, forwarded inverted to the PHY through an ODDR
//                    exactly as in v1's sysone_top
// The two sides meet only in memory_link_core's dual-clock FIFOs.
//
// Host side: scripts/v2/memory_link_client.py (write a file, read it back, compare).
//
// LEDs:
//   0  MMCM locked                     4  an FCS / framing error was seen (sticky)
//   1  MIG calibration complete         5  a frame was dropped, buffer full (sticky)
//   2  PHY out of reset                 6  a request was rejected (sticky)
//   3  memory side busy (stretched)     7  heartbeat
// Seven-segment display: left = commands accepted, right = replies sent (mod 10000).
// With ENCODER = 1, LED 3 also lights while the encoder runs.
// BTNC resets everything, including MIG calibration.
module nexys4ddr_link_top #(
    parameter integer ENCODER = 0,
    // 1: the packed 16 x 24 array (two products per DSP48E1; images built with
    // --tile 16x24), about 1.6x faster at 128 tokens; 0: the 16 x 12 array
    parameter integer ENCODER_PACKED = 0
) (
    input  logic clk_100MHz,
    input  logic reset,                 // BTNC, active high

    output wire  PHY_ref_clk,
    output logic PHY_reset_n,
    input  wire [1:0] rmii_rxd,
    input  wire  rmii_crs_dv,
    input  wire  rmii_rx_er,
    output wire [1:0] rmii_txd,
    output wire  rmii_tx_en,
    output wire  PHY_MDC,
    inout  wire  PHY_MDIO,

    inout  wire  [15:0] ddr2_dq,
    inout  wire  [1:0]  ddr2_dqs_p,
    inout  wire  [1:0]  ddr2_dqs_n,
    output wire  [12:0] ddr2_addr,
    output wire  [2:0]  ddr2_ba,
    output wire         ddr2_ras_n,
    output wire         ddr2_cas_n,
    output wire         ddr2_we_n,
    output wire  [0:0]  ddr2_ck_p,
    output wire  [0:0]  ddr2_ck_n,
    output wire  [0:0]  ddr2_cke,
    output wire  [0:0]  ddr2_cs_n,
    output wire  [1:0]  ddr2_dm,
    output wire  [0:0]  ddr2_odt,

    output logic [7:0]  LED,
    output logic [6:0]  segments_n,
    output logic        decimal_point_n,
    output logic [7:0]  anodes_n
);

    localparam integer UI_CLOCK_HZ = 75_000_000;
    localparam integer ADDRESS_WIDTH = 27;
    localparam integer BEATS_WIDTH = 16;

    // ---------------------------------------------------------------- clocking
    wire clk_input, clk_feedback, clk_feedback_buf, clock_locked;
    wire clk_200MHz_raw, clk_200MHz, clk_50MHz_raw, clk_50MHz;

    IBUF input_clock_buffer (.I(clk_100MHz), .O(clk_input));
    MMCME2_BASE #(
        .CLKIN1_PERIOD(10.0), .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(10.0),
        .CLKOUT0_DIVIDE_F(5.0),          // 200 MHz
        .CLKOUT1_DIVIDE(20),             // 50 MHz
        .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_input), .CLKFBIN(clk_feedback_buf),
        .CLKFBOUT(clk_feedback), .CLKOUT0(clk_200MHz_raw), .CLKOUT1(clk_50MHz_raw),
        .LOCKED(clock_locked), .PWRDWN(1'b0), .RST(reset)
    );
    BUFG feedback_buffer (.I(clk_feedback), .O(clk_feedback_buf));
    BUFG mig_clock_buffer (.I(clk_200MHz_raw), .O(clk_200MHz));
    BUFG ethernet_clock_buffer (.I(clk_50MHz_raw), .O(clk_50MHz));

    // the PHY samples halfway between our rising-edge data updates
    ODDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT(1'b0), .SRTYPE("SYNC"))
    PHY_clock_forward (
        .C(clk_50MHz), .CE(1'b1), .D1(1'b0), .D2(1'b1),
        .Q(PHY_ref_clk), .R(1'b0), .S(1'b0)
    );

    // --------------------------------------------------- Ethernet-side reset
    (* ASYNC_REG = "TRUE" *) logic [1:0] ethernet_reset_sync_reg = 2'b11;
    wire ethernet_core_reset = ethernet_reset_sync_reg[1];

    wire reset_request = reset || !clock_locked;

    always_ff @(posedge clk_50MHz or posedge reset_request) begin
        if (reset_request) begin
            ethernet_reset_sync_reg <= 2'b11;
        end else begin
            ethernet_reset_sync_reg <= {ethernet_reset_sync_reg[0], 1'b0};
        end
    end

    // 50 ms PHY reset with the reference clock running, then release (as v1)
    localparam logic [21:0] PHY_RESET_CYCLES = 22'd2_500_000;
    logic [21:0] PHY_timer_reg;
    logic PHY_reset_n_reg;

    always_ff @(posedge clk_50MHz or posedge ethernet_core_reset) begin
        if (ethernet_core_reset) begin
            PHY_timer_reg <= '0;
            PHY_reset_n_reg <= 1'b0;
        end else if (!PHY_reset_n_reg) begin
            if (PHY_timer_reg == PHY_RESET_CYCLES - 1'b1) begin
                PHY_reset_n_reg <= 1'b1;
            end else begin
                PHY_timer_reg <= PHY_timer_reg + 1'b1;
            end
        end
    end

    wire ethernet_reset = ethernet_core_reset || !PHY_reset_n_reg;

    // ------------------------------------------------------------------- MIG
    wire ui_clk, ui_reset, calibrated;
    wire [ADDRESS_WIDTH-1:0] app_addr;
    wire [2:0] app_cmd;
    wire app_en, app_wdf_end, app_wdf_wren, app_rd_data_end, app_rd_data_valid;
    wire app_rdy, app_wdf_rdy;
    wire [127:0] app_wdf_data, app_rd_data;
    wire [15:0] app_wdf_mask;
    wire [11:0] temperature;

    mig_ddr2 mig_inst (
        .ddr2_dq(ddr2_dq), .ddr2_dqs_p(ddr2_dqs_p), .ddr2_dqs_n(ddr2_dqs_n),
        .ddr2_addr(ddr2_addr), .ddr2_ba(ddr2_ba), .ddr2_ras_n(ddr2_ras_n),
        .ddr2_cas_n(ddr2_cas_n), .ddr2_we_n(ddr2_we_n), .ddr2_ck_p(ddr2_ck_p),
        .ddr2_ck_n(ddr2_ck_n), .ddr2_cke(ddr2_cke), .ddr2_cs_n(ddr2_cs_n),
        .ddr2_dm(ddr2_dm), .ddr2_odt(ddr2_odt),
        .sys_clk_i(clk_200MHz),
        .sys_rst(clock_locked && !reset),
        .app_addr(app_addr), .app_cmd(app_cmd), .app_en(app_en),
        .app_wdf_data(app_wdf_data), .app_wdf_end(app_wdf_end),
        .app_wdf_mask(app_wdf_mask), .app_wdf_wren(app_wdf_wren),
        .app_rd_data(app_rd_data), .app_rd_data_end(app_rd_data_end),
        .app_rd_data_valid(app_rd_data_valid), .app_rdy(app_rdy), .app_wdf_rdy(app_wdf_rdy),
        .app_sr_req(1'b0), .app_ref_req(1'b0), .app_zq_req(1'b0),
        .app_sr_active(), .app_ref_ack(), .app_zq_ack(),
        .ui_clk(ui_clk), .ui_clk_sync_rst(ui_reset),
        .device_temp_i(temperature),
        .init_calib_complete(calibrated)
    );

    xadc_temperature #(
        .CLOCK_HZ (UI_CLOCK_HZ)
    ) temperature_inst (
        .clk(ui_clk), .reset(ui_reset), .temperature(temperature)
    );

    // the memory side of the link starts once calibration is done
    (* ASYNC_REG = "TRUE" *) logic [1:0] calibrated_sync_reg;
    always_ff @(posedge ui_clk or posedge ui_reset) begin
        if (ui_reset) begin
            calibrated_sync_reg <= '0;
        end else begin
            calibrated_sync_reg <= {calibrated_sync_reg[0], calibrated};
        end
    end
    wire memory_reset = ui_reset || !calibrated_sync_reg[1];

    // ---------------------------------------------------------- memory port
    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic write_request_valid, write_request_ready, write_valid, write_ready;
    logic [ADDRESS_WIDTH-1:0] read_request_address, write_request_address;
    logic [BEATS_WIDTH-1:0] read_request_beats, write_request_beats;
    logic [127:0] read_data, write_data;

    mig_memory_port #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH)
    ) memory_port_inst (
        .clk(ui_clk), .reset(memory_reset),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .app_addr(app_addr), .app_cmd(app_cmd), .app_en(app_en),
        .app_wdf_data(app_wdf_data), .app_wdf_end(app_wdf_end), .app_wdf_mask(app_wdf_mask),
        .app_wdf_wren(app_wdf_wren), .app_rd_data(app_rd_data),
        .app_rd_data_end(app_rd_data_end), .app_rd_data_valid(app_rd_data_valid),
        .app_rdy(app_rdy), .app_wdf_rdy(app_wdf_rdy)
    );

    // ------------------------------------------------------------ the link
    logic accepted, rejected, replied, rx_error, dropped, memory_busy, encoder_busy;

    sysone_v2_core #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH),
        .ENCODER       (ENCODER),
        .TILE_OUT      (ENCODER_PACKED ? 24 : 12),
        .MAC_PACK      (ENCODER_PACKED),
        .ATTENTION_LANES(12),
        .ACCUMULATORS_IN_LUTS(ENCODER_PACKED),
        .DRAIN_LANES   (ENCODER_PACKED ? 2 : 1)
    ) link_inst (
        .ethernet_clk(clk_50MHz), .ethernet_reset(ethernet_reset),
        .rmii_rxd(rmii_rxd), .rmii_crs_dv(rmii_crs_dv), .rmii_rx_er(rmii_rx_er),
        .rmii_txd(rmii_txd), .rmii_tx_en(rmii_tx_en),
        .accepted_out(accepted), .rejected_out(rejected), .replied_out(replied),
        .rx_error_out(rx_error), .dropped_out(dropped),
        .memory_clk(ui_clk), .memory_reset(memory_reset),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .memory_busy_out(memory_busy), .encoder_busy_out(encoder_busy)
    );

    // ---------------------------------------------------------------- status
    logic [13:0] accepted_count_reg, replied_count_reg;
    logic rx_error_seen_reg, dropped_seen_reg, rejected_seen_reg;
    logic [25:0] heartbeat_reg;

    always_ff @(posedge clk_50MHz or posedge ethernet_reset) begin
        if (ethernet_reset) begin
            accepted_count_reg <= '0;
            replied_count_reg <= '0;
            rx_error_seen_reg <= 1'b0;
            dropped_seen_reg <= 1'b0;
            rejected_seen_reg <= 1'b0;
        end else begin
            if (accepted) accepted_count_reg <= (accepted_count_reg == 9999) ? '0 : accepted_count_reg + 1'b1;
            if (replied) replied_count_reg <= (replied_count_reg == 9999) ? '0 : replied_count_reg + 1'b1;
            rx_error_seen_reg <= rx_error_seen_reg || rx_error;
            dropped_seen_reg <= dropped_seen_reg || dropped;
            rejected_seen_reg <= rejected_seen_reg || rejected;
        end
    end

    always_ff @(posedge clk_50MHz) begin
        heartbeat_reg <= heartbeat_reg + 1'b1;
    end

    // memory busy, stretched to ~20 ms so a single command is visible
    (* ASYNC_REG = "TRUE" *) logic [1:0] busy_sync_reg;
    logic [19:0] busy_stretch_reg;
    always_ff @(posedge clk_50MHz) begin
        busy_sync_reg <= {busy_sync_reg[0], memory_busy || encoder_busy};
        busy_stretch_reg <= busy_sync_reg[1] ? '1 : (busy_stretch_reg != 0 ? busy_stretch_reg - 1'b1 : '0);
    end

    seven_segment_display #(
        .CLOCK_HZ (50_000_000)
    ) display_inst (
        .clk(clk_50MHz), .reset(ethernet_core_reset),
        .left_value(accepted_count_reg), .right_value(replied_count_reg),
        .segments_n(segments_n), .decimal_point_n(decimal_point_n), .anodes_n(anodes_n)
    );

    assign LED[0] = clock_locked;
    assign LED[1] = calibrated;
    assign LED[2] = PHY_reset_n_reg;
    assign LED[3] = (busy_stretch_reg != 0);
    assign LED[4] = rx_error_seen_reg;
    assign LED[5] = dropped_seen_reg;
    assign LED[6] = rejected_seen_reg;
    assign LED[7] = heartbeat_reg[25];

    // keep the board's default PHY auto-negotiation straps (as v1)
    assign PHY_MDC = 1'b0;
    assign PHY_MDIO = 1'bz;
    assign PHY_reset_n = PHY_reset_n_reg;

endmodule
