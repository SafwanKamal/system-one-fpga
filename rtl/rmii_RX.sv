// 100 Mbps RMII receive: dibits from the PHY in, frame bytes out.
//
// The receive-side counterpart of rmii_TX. It strips the preamble and start frame
// delimiter and assembles the following dibits, least significant first, into bytes.
// It does not check the FCS; ethernet_RX does.
//
// Sampling edge. The logic clock is 50 MHz and the PHY reference clock is the same
// clock forwarded inverted (see sysone_top), so the PHY's rising edge is our falling
// edge. The PHY launches RXD and CRS_DV on its rising edge and RMII says the MAC
// samples on the next one, so the pins are captured on our falling edge and then
// re-registered on the rising edge. That is the one negedge register in the design,
// and the half-period hop to the rising edge is internal.
//
// End of frame. At 100 Mbps the LAN8720A may toggle CRS_DV at the end of a frame
// while its FIFO still holds data: CRS_DV goes low on the first dibit of a nibble and
// high on the second. So a low CRS_DV only ends the frame when the next dibit is low
// too. That needs one dibit of lookahead, which is why everything below works on the
// older of two samples.
module rmii_RX (
    input  logic clk,
    input  logic reset,

    input  logic [1:0] rmii_rxd,
    input  logic rmii_crs_dv,
    input  logic rmii_rx_er,

    output logic frame_start_out,   // SFD seen; bytes of a new frame follow
    output logic [7:0] data_out,
    output logic valid_out,         // one clock per completed byte
    output logic frame_end_out,     // one clock after the last byte
    output logic frame_error_out    // with frame_end_out: RX_ER seen or a partial byte
);

    typedef enum logic [1:0] {
        IDLE,
        PREAMBLE,
        DATA
    } state_t;

    state_t state_reg, state_next;

    // falling-edge capture of the pins
    (* IOB = "TRUE" *)
    logic [1:0] rxd_capture_reg;

    (* IOB = "TRUE" *)
    logic crs_dv_capture_reg;

    (* IOB = "TRUE" *)
    logic rx_er_capture_reg;

    // rising-edge samples: _0 is the newer, _1 the older one that is being decoded
    logic [1:0] rxd_0_reg, rxd_1_reg;
    logic crs_dv_0_reg, crs_dv_1_reg;
    logic rx_er_0_reg, rx_er_1_reg;

    logic seen_preamble_reg, seen_preamble_next;
    logic [1:0] dibit_count_reg, dibit_count_next;
    logic [7:0] shift_reg, shift_next;
    logic error_reg, error_next;

    logic frame_start_reg, frame_start_next;
    logic [7:0] data_reg, data_next;
    logic valid_reg, valid_next;
    logic frame_end_reg, frame_end_next;
    logic frame_error_reg, frame_error_next;

    logic dibit_valid;


    always_ff @(negedge clk or posedge reset) begin
        if (reset) begin
            rxd_capture_reg <= 2'b00;
            crs_dv_capture_reg <= 1'b0;
            rx_er_capture_reg <= 1'b0;
        end else begin
            rxd_capture_reg <= rmii_rxd;
            crs_dv_capture_reg <= rmii_crs_dv;
            rx_er_capture_reg <= rmii_rx_er;
        end
    end


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            rxd_0_reg <= 2'b00;
            rxd_1_reg <= 2'b00;
            crs_dv_0_reg <= 1'b0;
            crs_dv_1_reg <= 1'b0;
            rx_er_0_reg <= 1'b0;
            rx_er_1_reg <= 1'b0;
            state_reg <= IDLE;
            seen_preamble_reg <= 1'b0;
            dibit_count_reg <= '0;
            shift_reg <= '0;
            error_reg <= 1'b0;
            frame_start_reg <= 1'b0;
            data_reg <= '0;
            valid_reg <= 1'b0;
            frame_end_reg <= 1'b0;
            frame_error_reg <= 1'b0;
        end else begin
            rxd_0_reg <= rxd_capture_reg;
            rxd_1_reg <= rxd_0_reg;
            crs_dv_0_reg <= crs_dv_capture_reg;
            crs_dv_1_reg <= crs_dv_0_reg;
            rx_er_0_reg <= rx_er_capture_reg;
            rx_er_1_reg <= rx_er_0_reg;
            state_reg <= state_next;
            seen_preamble_reg <= seen_preamble_next;
            dibit_count_reg <= dibit_count_next;
            shift_reg <= shift_next;
            error_reg <= error_next;
            frame_start_reg <= frame_start_next;
            data_reg <= data_next;
            valid_reg <= valid_next;
            frame_end_reg <= frame_end_next;
            frame_error_reg <= frame_error_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        seen_preamble_next = seen_preamble_reg;
        dibit_count_next = dibit_count_reg;
        shift_next = shift_reg;
        error_next = error_reg;

        frame_start_next = 1'b0;
        data_next = data_reg;
        valid_next = 1'b0;
        frame_end_next = 1'b0;
        frame_error_next = 1'b0;

        // A low CRS_DV followed by a high one is the end-of-frame toggle, not the end
        dibit_valid = crs_dv_1_reg || crs_dv_0_reg;

        case (state_reg)
            IDLE: begin
                seen_preamble_next = 1'b0;

                if (crs_dv_1_reg) begin
                    state_next = PREAMBLE;
                end
            end

            PREAMBLE: begin
                // RXD is 00 until the PHY has locked, then 01 dibits, then 11 ends the SFD
                if (!dibit_valid) begin
                    state_next = IDLE;
                end else if (rxd_1_reg == 2'b01) begin
                    seen_preamble_next = 1'b1;
                end else if (rxd_1_reg == 2'b11 && seen_preamble_reg) begin
                    frame_start_next = 1'b1;
                    dibit_count_next = '0;
                    error_next = 1'b0;
                    state_next = DATA;
                end else if (rxd_1_reg == 2'b10) begin
                    // 10 during carrier is a false carrier indication
                    state_next = IDLE;
                end
            end

            DATA: begin
                if (!dibit_valid) begin
                    // Frames end on a byte boundary; anything else is reported as an error
                    frame_end_next = 1'b1;
                    frame_error_next = error_reg || (dibit_count_reg != 0);
                    state_next = IDLE;
                end else begin
                    shift_next = {rxd_1_reg, shift_reg[7:2]};
                    dibit_count_next = dibit_count_reg + 1'b1;

                    if (rx_er_1_reg) begin
                        error_next = 1'b1;
                    end

                    if (dibit_count_reg == 2'd3) begin
                        data_next = {rxd_1_reg, shift_reg[7:2]};
                        valid_next = 1'b1;
                    end
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign frame_start_out = frame_start_reg;
    assign data_out = data_reg;
    assign valid_out = valid_reg;
    assign frame_end_out = frame_end_reg;
    assign frame_error_out = frame_error_reg;

endmodule
