// sysone_core behind a raw-Ethernet request/result interface. Everything on one clock.
//
//   RMII RX -> ethernet_RX -> ethernet_RX_buffer -> sysone_request_parser -> sysone_core
//   sysone_core -> sysone_result_packet -> ethernet_TX_buffer -> ethernet_TX -> RMII TX
//
// The transmit side is Genome-Classifier's ethernet_TX_buffer and ethernet_TX (with
// rmii_TX and ethernet_CRC32) unchanged; they have been checked on this board.
//
// The whole design runs on the 50 MHz RMII clock, so there is no clock-domain
// crossing. That doubles sysone_core's compute time to about 34 us, against roughly
// 26 us to receive a request and 27 us to send the result at 100 Mbps. Moving the core
// to 100 MHz with a crossing is a later optimisation.
//
// The board-specific parts (clocking, PHY reset, pins) are in sysone_top, so this
// module simulates without any Xilinx primitives.
module sysone_ethernet_core #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,

    parameter integer ROW_NUMBER       = 16384,
    parameter integer DIMENSION        = 64,
    parameter integer HIDDEN           = 256,
    parameter integer CLASS_NUMBER     = 151,
    parameter integer MAXIMUM_FEATURES = 256,
    parameter integer POOL_GAIN        = 5,

    parameter string EMBEDDING_LOW_FILE     = "embedding_low.mem",
    parameter string EMBEDDING_HIGH_FILE    = "embedding_high.mem",
    parameter string RECIPROCAL_FILE        = "pool_reciprocals.mem",
    parameter string HIDDEN_WEIGHT_FILE     = "dense_hidden_weights.mem",
    parameter string HIDDEN_BIAS_FILE       = "dense_hidden_biases.mem",
    parameter string OUTPUT_WEIGHT_FILE     = "dense_output_weights.mem",
    parameter string OUTPUT_BIAS_FILE       = "dense_output_biases.mem",
    parameter string HIDDEN_MULTIPLIER_FILE = "requant_hidden_multipliers.mem",
    parameter string HIDDEN_REQUANT_FILE    = "requant_hidden_biases.mem",
    parameter string OUTPUT_MULTIPLIER_FILE = "requant_output_multipliers.mem",
    parameter string OUTPUT_REQUANT_FILE    = "requant_output_biases.mem"
) (
    input  logic clk,
    input  logic reset,

    input  logic [1:0] rmii_rxd,
    input  logic rmii_crs_dv,
    input  logic rmii_rx_er,

    output logic [1:0] rmii_txd,
    output logic rmii_tx_en,

    // status, for LEDs
    output logic busy_out,             // from a request reaching the core until its result is sent
    output logic served_toggle_out,    // flips once per result sent
    output logic rx_error_out,         // sticky: a frame failed its FCS or framing
    output logic dropped_out,          // sticky: a frame arrived while one was held
    output logic tx_error_out          // sticky: transmit underflow or buffer overflow
);

    // receive
    logic rx_frame_start, rx_valid, rx_frame_end, rx_frame_good, rx_crc_error;
    logic [7:0] rx_data;

    logic [7:0] request_data;
    logic request_valid, request_last, request_ready;
    logic rx_buffer_busy, rx_dropped;

    // parser <-> core
    logic [7:0] core_data;
    logic core_valid, core_message_end, core_ready;
    logic [47:0] host_mac;
    logic [31:0] sequence_number;
    logic request_accepted, request_rejected;

    // core outputs
    logic logit_valid;
    logic [7:0] logit_class;
    logic signed [15:0] logit_value;
    logic decision_valid;
    logic [7:0] decision_class;
    logic signed [15:0] top_logit, second_logit;
    logic [8:0] feature_count;
    logic overflow;
    logic feature_valid;
    logic [$clog2(ROW_NUMBER)-1:0] feature_index;

    // transmit
    logic [7:0] result_data, buffered_data;
    logic result_valid, result_last, result_ready, result_busy;
    logic buffered_valid, buffered_last, TX_ready;
    logic buffer_busy, buffer_overflow, TX_busy, TX_done, TX_underflow;

    logic busy_reg, busy_next;
    logic served_toggle_reg, served_toggle_next;
    logic rx_error_reg, rx_error_next;
    logic dropped_reg, dropped_next;
    logic tx_error_reg, tx_error_next;


    ethernet_RX receiver (
        .clk            (clk),
        .reset          (reset),
        .rmii_rxd       (rmii_rxd),
        .rmii_crs_dv    (rmii_crs_dv),
        .rmii_rx_er     (rmii_rx_er),
        .frame_start_out(rx_frame_start),
        .data_out       (rx_data),
        .valid_out      (rx_valid),
        .frame_end_out  (rx_frame_end),
        .frame_good_out (rx_frame_good),
        .crc_error_out  (rx_crc_error)
    );

    ethernet_RX_buffer receive_buffer (
        .clk           (clk),
        .reset         (reset),
        .frame_start_in(rx_frame_start),
        .data_in       (rx_data),
        .valid_in      (rx_valid),
        .frame_end_in  (rx_frame_end),
        .frame_good_in (rx_frame_good),
        .data_out      (request_data),
        .valid_out     (request_valid),
        .last_out      (request_last),
        .ready_in      (request_ready),
        .busy_out      (rx_buffer_busy),
        .dropped_out   (rx_dropped)
    );

    sysone_request_parser #(
        .LOCAL_MAC(LOCAL_MAC)
    ) request_parser_inst (
        .clk                 (clk),
        .reset               (reset),
        .data_in             (request_data),
        .valid_in            (request_valid),
        .last_in             (request_last),
        .ready_out           (request_ready),
        .core_data_out       (core_data),
        .core_valid_out      (core_valid),
        .core_message_end_out(core_message_end),
        .core_ready_in       (core_ready),
        .decision_valid_in   (decision_valid),
        .result_busy_in      (result_busy),
        .host_mac_out        (host_mac),
        .sequence_number_out (sequence_number),
        .request_out         (request_accepted),
        .rejected_out        (request_rejected)
    );

    sysone_core #(
        .ROW_NUMBER      (ROW_NUMBER),
        .DIMENSION       (DIMENSION),
        .HIDDEN          (HIDDEN),
        .CLASS_NUMBER    (CLASS_NUMBER),
        .MAXIMUM_FEATURES(MAXIMUM_FEATURES),
        .POOL_GAIN       (POOL_GAIN),

        .EMBEDDING_LOW_FILE    (EMBEDDING_LOW_FILE),
        .EMBEDDING_HIGH_FILE   (EMBEDDING_HIGH_FILE),
        .RECIPROCAL_FILE       (RECIPROCAL_FILE),
        .HIDDEN_WEIGHT_FILE    (HIDDEN_WEIGHT_FILE),
        .HIDDEN_BIAS_FILE      (HIDDEN_BIAS_FILE),
        .OUTPUT_WEIGHT_FILE    (OUTPUT_WEIGHT_FILE),
        .OUTPUT_BIAS_FILE      (OUTPUT_BIAS_FILE),
        .HIDDEN_MULTIPLIER_FILE(HIDDEN_MULTIPLIER_FILE),
        .HIDDEN_REQUANT_FILE   (HIDDEN_REQUANT_FILE),
        .OUTPUT_MULTIPLIER_FILE(OUTPUT_MULTIPLIER_FILE),
        .OUTPUT_REQUANT_FILE   (OUTPUT_REQUANT_FILE)
    ) sysone_core_inst (
        .clk               (clk),
        .reset             (reset),
        .data_in           (core_data),
        .valid_in          (core_valid),
        .message_end_in    (core_message_end),
        .ready_out         (core_ready),
        .logit_valid_out   (logit_valid),
        .logit_class_out   (logit_class),
        .logit_out         (logit_value),
        .decision_valid_out(decision_valid),
        .decision_class_out(decision_class),
        .top_logit_out     (top_logit),
        .second_logit_out  (second_logit),
        .feature_count_out (feature_count),
        .overflow_out      (overflow),
        .feature_valid_out (feature_valid),
        .feature_index_out (feature_index)
    );

    sysone_result_packet #(
        .CLASS_NUMBER(CLASS_NUMBER),
        .LOCAL_MAC   (LOCAL_MAC)
    ) result_packet_inst (
        .clk               (clk),
        .reset             (reset),
        .logit_valid_in    (logit_valid),
        .logit_class_in    (logit_class),
        .logit_in          (logit_value),
        .decision_valid_in (decision_valid),
        .decision_class_in (decision_class),
        .top_logit_in      (top_logit),
        .second_logit_in   (second_logit),
        .feature_count_in  (feature_count),
        .overflow_in       (overflow),
        .host_mac_in       (host_mac),
        .sequence_number_in(sequence_number),
        .data_out          (result_data),
        .valid_out         (result_valid),
        .last_out          (result_last),
        .ready_in          (result_ready),
        .busy_out          (result_busy)
    );

    ethernet_TX_buffer frame_buffer (
        .clk(clk), .reset(reset),
        .data_in(result_data), .valid_in(result_valid),
        .last_in(result_last), .ready_out(result_ready),
        .data_out(buffered_data), .valid_out(buffered_valid),
        .last_out(buffered_last), .ready_in(TX_ready),
        .tx_done_in(TX_done), .tx_underflow_in(TX_underflow),
        .busy_out(buffer_busy), .overflow_out(buffer_overflow)
    );

    ethernet_TX transmitter (
        .clk(clk), .reset(reset),
        .data_in(buffered_data), .valid_in(buffered_valid),
        .last_in(buffered_last), .ready_out(TX_ready),
        .rmii_txd(rmii_txd), .rmii_tx_en(rmii_tx_en),
        .busy_out(TX_busy), .done_out(TX_done),
        .underflow_out(TX_underflow)
    );


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            busy_reg <= 1'b0;
            served_toggle_reg <= 1'b0;
            rx_error_reg <= 1'b0;
            dropped_reg <= 1'b0;
            tx_error_reg <= 1'b0;
        end else begin
            busy_reg <= busy_next;
            served_toggle_reg <= served_toggle_next;
            rx_error_reg <= rx_error_next;
            dropped_reg <= dropped_next;
            tx_error_reg <= tx_error_next;
        end
    end

    always_comb begin
        busy_next = busy_reg;
        served_toggle_next = served_toggle_reg;
        rx_error_next = rx_error_reg || rx_crc_error;
        dropped_next = dropped_reg || rx_dropped;
        tx_error_next = tx_error_reg || TX_underflow || buffer_overflow;

        if (request_accepted) begin
            busy_next = 1'b1;
        end

        if (TX_done) begin
            busy_next = 1'b0;
            served_toggle_next = !served_toggle_reg;
        end
    end

    assign busy_out = busy_reg;
    assign served_toggle_out = served_toggle_reg;
    assign rx_error_out = rx_error_reg;
    assign dropped_out = dropped_reg;
    assign tx_error_out = tx_error_reg;

endmodule
