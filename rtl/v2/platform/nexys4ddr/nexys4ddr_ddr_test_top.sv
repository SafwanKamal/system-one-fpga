// Nexys 4 DDR, v2 bring-up step 1: the DDR2 memory the v2 encoder streams its
// weights from.
//
// MIG DDR2 controller (ip/v2/nexys4ddr/mig_ddr2.prj) -> mig_memory_port (the v2
// memory port) -> ddr_selftest, which writes all 128 MiB, reads it back, counts
// mismatches and times both phases with the same 64-beat sequential bursts the
// encoder will use.
//
// Clocking: 100 MHz board clock -> MMCM -> 200 MHz MIG system clock (the MIG
// derives the 300 MHz DDR2 clock and the 75 MHz ui_clk from it). All test logic
// runs on ui_clk.
//
// Controls:
//   BTNC (reset)  restart everything, including MIG calibration
//   SW0           0: run the test once after calibration; 1: run it continuously
//
// Seven-segment display, decimal: left four digits = write MB/s, right four = read
// MB/s, from the last completed run (1 MB = 10^6 bytes). 16-bit DDR2 at 600 MT/s
// peaks at 1200 MB/s.
//
// LEDs:
//   0  MMCM locked                 4  last run passed (no mismatches)
//   1  MIG calibration complete    5  last run failed (mismatches)
//   2  test running                6  heartbeat (ui_clk alive)
//   3  write phase done            15..8  mismatch count, saturating at 255
module nexys4ddr_ddr_test_top (
    input  logic clk_100MHz,
    input  logic reset,                 // BTNC, active high
    input  logic SW0,

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

    output logic [15:0] LED,
    output logic [6:0]  segments_n,     // {CG, CF, CE, CD, CC, CB, CA}
    output logic        decimal_point_n,
    output logic [7:0]  anodes_n
);

    localparam integer UI_CLOCK_HZ = 75_000_000;
    localparam longint REGION_BYTES = 64'd134217728;
    localparam integer ADDRESS_WIDTH = 27;
    localparam integer DATA_WIDTH = 128;
    localparam integer BEATS_WIDTH = 16;

    // ---------------------------------------------------------------- clocking
    wire clk_input, clk_feedback, clk_feedback_buf, clk_200MHz_raw, clk_200MHz, clock_locked;

    IBUF input_clock_buffer (.I(clk_100MHz), .O(clk_input));
    MMCME2_BASE #(
        .CLKIN1_PERIOD(10.0), .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(10.0),          // 1000 MHz VCO
        .CLKOUT0_DIVIDE_F(5.0),          // 200 MHz
        .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_input), .CLKFBIN(clk_feedback_buf),
        .CLKFBOUT(clk_feedback), .CLKOUT0(clk_200MHz_raw),
        .LOCKED(clock_locked), .PWRDWN(1'b0), .RST(reset)
    );
    BUFG feedback_buffer (.I(clk_feedback), .O(clk_feedback_buf));
    BUFG mig_clock_buffer (.I(clk_200MHz_raw), .O(clk_200MHz));

    // ------------------------------------------------------------------- MIG
    wire ui_clk, ui_reset, calibrated;
    wire [ADDRESS_WIDTH-1:0] app_addr;
    wire [2:0] app_cmd;
    wire app_en, app_wdf_end, app_wdf_wren, app_rd_data_end, app_rd_data_valid;
    wire app_rdy, app_wdf_rdy;
    wire [DATA_WIDTH-1:0] app_wdf_data, app_rd_data;
    wire [DATA_WIDTH/8-1:0] app_wdf_mask;
    wire [11:0] temperature;

    mig_ddr2 mig_inst (
        .ddr2_dq(ddr2_dq), .ddr2_dqs_p(ddr2_dqs_p), .ddr2_dqs_n(ddr2_dqs_n),
        .ddr2_addr(ddr2_addr), .ddr2_ba(ddr2_ba), .ddr2_ras_n(ddr2_ras_n),
        .ddr2_cas_n(ddr2_cas_n), .ddr2_we_n(ddr2_we_n), .ddr2_ck_p(ddr2_ck_p),
        .ddr2_ck_n(ddr2_ck_n), .ddr2_cke(ddr2_cke), .ddr2_cs_n(ddr2_cs_n),
        .ddr2_dm(ddr2_dm), .ddr2_odt(ddr2_odt),
        .sys_clk_i(clk_200MHz),
        .sys_rst(clock_locked && !reset),           // active low
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
        .clk         (ui_clk),
        .reset       (ui_reset),
        .temperature (temperature)
    );

    // --------------------------------------------------------- memory port
    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic write_request_valid, write_request_ready, write_valid, write_ready;
    logic [ADDRESS_WIDTH-1:0] read_request_address, write_request_address;
    logic [BEATS_WIDTH-1:0] read_request_beats, write_request_beats;
    logic [DATA_WIDTH-1:0] read_data, write_data;

    mig_memory_port #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH)
    ) memory_port_inst (
        .clk(ui_clk), .reset(ui_reset),
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

    // ------------------------------------------------------------- self-test
    (* ASYNC_REG = "TRUE" *) logic [1:0] switch_sync_reg;
    (* ASYNC_REG = "TRUE" *) logic [1:0] calibrated_sync_reg;
    logic [31:0] run_counter_reg;
    logic started_reg;
    logic test_busy, test_write_done, test_done, test_passed;
    logic [31:0] error_count;
    logic [39:0] write_cycles, read_cycles;
    wire start = calibrated_sync_reg[1] && (!started_reg || (switch_sync_reg[1] && test_done));

    always_ff @(posedge ui_clk or posedge ui_reset) begin
        if (ui_reset) begin
            switch_sync_reg <= '0;
            calibrated_sync_reg <= '0;
            run_counter_reg <= '0;
            started_reg <= 1'b0;
        end else begin
            switch_sync_reg <= {switch_sync_reg[0], SW0};
            calibrated_sync_reg <= {calibrated_sync_reg[0], calibrated};
            run_counter_reg <= run_counter_reg + 1'b1;
            if (start) begin
                started_reg <= 1'b1;
            end
        end
    end

    ddr_selftest #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .DATA_WIDTH    (DATA_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH),
        .REGION_BYTES  (REGION_BYTES),
        .REQUEST_BEATS (64)
    ) selftest_inst (
        .clk(ui_clk), .reset(ui_reset), .start(start), .seed(run_counter_reg),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .busy(test_busy), .write_done(test_write_done), .done(test_done),
        .passed(test_passed), .error_count(error_count),
        .write_cycles(write_cycles), .read_cycles(read_cycles)
    );

    // ------------------------------------------------- bandwidth readout
    // MB/s = REGION_BYTES * UI_MHz / cycles
    localparam logic [39:0] BANDWIDTH_NUMERATOR = 40'(REGION_BYTES * (UI_CLOCK_HZ / 1_000_000));

    typedef enum logic [1:0] {
        MEASURE_WAIT,
        MEASURE_WRITE,
        MEASURE_READ
    } measure_t;

    measure_t measure_reg;
    logic divider_start, divider_busy, divider_done;
    logic [39:0] divider_quotient;
    logic [13:0] write_mbps_reg, read_mbps_reg;
    logic test_done_reg;
    logic pass_led_reg, fail_led_reg;
    logic [7:0] error_led_reg;

    sequential_divider #(
        .WIDTH (40)
    ) bandwidth_divider_inst (
        .clk(ui_clk), .reset(ui_reset), .start(divider_start),
        .dividend(BANDWIDTH_NUMERATOR),
        .divisor(measure_reg == MEASURE_WRITE ? write_cycles : read_cycles),
        .busy(divider_busy), .done(divider_done), .quotient(divider_quotient)
    );

    always_ff @(posedge ui_clk or posedge ui_reset) begin
        if (ui_reset) begin
            measure_reg <= MEASURE_WAIT;
            write_mbps_reg <= '0;
            read_mbps_reg <= '0;
            test_done_reg <= 1'b0;
            pass_led_reg <= 1'b0;
            fail_led_reg <= 1'b0;
            error_led_reg <= '0;
        end else begin
            test_done_reg <= test_done;
            case (measure_reg)
                MEASURE_WAIT: begin
                    if (test_done && !test_done_reg) begin
                        measure_reg <= MEASURE_WRITE;
                        pass_led_reg <= test_passed;
                        fail_led_reg <= !test_passed;
                        error_led_reg <= (error_count > 255) ? 8'd255 : error_count[7:0];
                    end
                end
                MEASURE_WRITE: begin
                    if (divider_done) begin
                        write_mbps_reg <= (divider_quotient > 9999) ? 14'd9999 : divider_quotient[13:0];
                        measure_reg <= MEASURE_READ;
                    end
                end
                MEASURE_READ: begin
                    if (divider_done) begin
                        read_mbps_reg <= (divider_quotient > 9999) ? 14'd9999 : divider_quotient[13:0];
                        measure_reg <= MEASURE_WAIT;
                    end
                end
                default: measure_reg <= MEASURE_WAIT;
            endcase
        end
    end

    // start a division on entry to each measure state
    logic [1:0] measure_prev_reg;
    always_ff @(posedge ui_clk or posedge ui_reset) begin
        if (ui_reset) begin
            measure_prev_reg <= MEASURE_WAIT;
        end else begin
            measure_prev_reg <= measure_reg;
        end
    end
    assign divider_start = (measure_reg != MEASURE_WAIT) && (measure_reg != measure_prev_reg)
                           && !divider_busy;

    seven_segment_display #(
        .CLOCK_HZ (UI_CLOCK_HZ)
    ) display_inst (
        .clk(ui_clk), .reset(ui_reset),
        .left_value(write_mbps_reg), .right_value(read_mbps_reg),
        .segments_n(segments_n), .decimal_point_n(decimal_point_n), .anodes_n(anodes_n)
    );

    assign LED[0] = clock_locked;
    assign LED[1] = calibrated;
    assign LED[2] = test_busy;
    assign LED[3] = test_write_done;
    assign LED[4] = pass_led_reg;
    assign LED[5] = fail_led_reg;
    assign LED[6] = run_counter_reg[25];
    assign LED[7] = 1'b0;
    assign LED[15:8] = error_led_reg;

endmodule
