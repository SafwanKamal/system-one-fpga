// v2 memory link: external memory read/write over 100 Mb/s raw Ethernet.
//
//   RMII -> ethernet_RX -> ethernet_RX_buffer -> memory_link_parser --+
//        (Ethernet clock)                         commands, write data |  async FIFOs
//   memory port <- memory_link_executor <------------------------------+
//        (memory clock)                    replies, read data          |  async FIFOs
//   RMII <- ethernet_TX <- ethernet_TX_buffer <- memory_link_responder <+
//
// The Ethernet receive/transmit blocks are v1's (Genome-Classifier's TX path and the
// v1 RX path), unchanged. This module has no board-specific parts, so it simulates
// without Xilinx primitives and is the same on every v2 board: only the memory
// port behind it changes (mig_memory_port on the Nexys 4 DDR, axi_memory_port on
// the KR260).
//
// The link exists to load weights and to check memory from the host; it is not on
// the inference path, and its throughput says nothing about the encoder's.
module memory_link_core #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter longint MEMORY_BYTES = 64'd134217728,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16
) (
    // Ethernet clock domain
    input logic ethernet_clk,
    input logic ethernet_reset,
    input logic [1:0] rmii_rxd,
    input logic rmii_crs_dv,
    input logic rmii_rx_er,
    output logic [1:0] rmii_txd,
    output logic rmii_tx_en,

    output logic accepted_out,           // one ethernet_clk per command accepted
    output logic rejected_out,           // one ethernet_clk per frame dropped
    output logic replied_out,            // one ethernet_clk per reply frame queued
    output logic rx_error_out,           // one ethernet_clk per FCS / framing error
    output logic dropped_out,            // one ethernet_clk per frame lost to a full buffer

    // memory clock domain
    input logic memory_clk,
    input logic memory_reset,

    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,

    output logic write_request_valid,
    input logic write_request_ready,
    output logic [ADDRESS_WIDTH-1:0] write_request_address,
    output logic [BEATS_WIDTH-1:0] write_request_beats,
    output logic write_valid,
    input logic write_ready,
    output logic [127:0] write_data,

    // run port (memory clock): RUN commands, see memory_link_executor
    output logic run_start_out,
    output logic [127:0] run_descriptor_out,
    output logic run_active_out,
    input logic run_done_in,
    input logic [127:0] run_result_in,

    output logic memory_busy_out
);

    // ---- receive
    logic rx_frame_start, rx_valid, rx_frame_end, rx_frame_good, rx_crc_error;
    logic [7:0] rx_data;
    logic [7:0] frame_data;
    logic frame_valid, frame_last, frame_ready;
    logic rx_buffer_busy;

    ethernet_RX receiver (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .rmii_rxd(rmii_rxd), .rmii_crs_dv(rmii_crs_dv), .rmii_rx_er(rmii_rx_er),
        .frame_start_out(rx_frame_start), .data_out(rx_data), .valid_out(rx_valid),
        .frame_end_out(rx_frame_end), .frame_good_out(rx_frame_good),
        .crc_error_out(rx_crc_error)
    );

    ethernet_RX_buffer receive_buffer (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .frame_start_in(rx_frame_start), .data_in(rx_data), .valid_in(rx_valid),
        .frame_end_in(rx_frame_end), .frame_good_in(rx_frame_good),
        .data_out(frame_data), .valid_out(frame_valid), .last_out(frame_last),
        .ready_in(frame_ready), .busy_out(rx_buffer_busy), .dropped_out(dropped_out)
    );

    // ---- crossing FIFOs
    logic [127:0] beat_w, beat_r, read_beat_w, read_beat_r;
    logic beat_push, beat_full, beat_empty, beat_pop;
    logic read_beat_push, read_beat_full, read_beat_empty, read_beat_pop;
    logic [120:0] command_w, command_r, response_w, response_r;
    logic command_push, command_full, command_empty, command_pop;
    logic response_push, response_full, response_empty, response_pop;

    memory_link_parser #(
        .LOCAL_MAC    (LOCAL_MAC),
        .MEMORY_BYTES (MEMORY_BYTES)
    ) parser_inst (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .data_in(frame_data), .valid_in(frame_valid), .last_in(frame_last), .ready_out(frame_ready),
        .beat_out(beat_w), .beat_push_out(beat_push), .beat_full_in(beat_full),
        .command_out(command_w), .command_push_out(command_push), .command_full_in(command_full),
        .accepted_out(accepted_out), .rejected_out(rejected_out)
    );

    async_fifo #(.WIDTH(128), .DEPTH(128)) write_data_fifo_inst (
        .write_clk(ethernet_clk), .write_reset(ethernet_reset), .write_enable(beat_push),
        .write_data(beat_w), .full(beat_full), .write_count(),
        .read_clk(memory_clk), .read_reset(memory_reset), .read_enable(beat_pop),
        .read_data(beat_r), .empty(beat_empty)
    );

    async_fifo #(.WIDTH(121), .DEPTH(8)) command_fifo_inst (
        .write_clk(ethernet_clk), .write_reset(ethernet_reset), .write_enable(command_push),
        .write_data(command_w), .full(command_full), .write_count(),
        .read_clk(memory_clk), .read_reset(memory_reset), .read_enable(command_pop),
        .read_data(command_r), .empty(command_empty)
    );

    memory_link_executor #(
        .ADDRESS_WIDTH (ADDRESS_WIDTH),
        .BEATS_WIDTH   (BEATS_WIDTH)
    ) executor_inst (
        .clk(memory_clk), .reset(memory_reset),
        .command_in(command_r), .command_empty_in(command_empty), .command_pop_out(command_pop),
        .beat_in(beat_r), .beat_empty_in(beat_empty), .beat_pop_out(beat_pop),
        .read_beat_out(read_beat_w), .read_beat_push_out(read_beat_push),
        .read_beat_full_in(read_beat_full),
        .response_out(response_w), .response_push_out(response_push),
        .response_full_in(response_full),
        .read_request_valid(read_request_valid), .read_request_ready(read_request_ready),
        .read_request_address(read_request_address), .read_request_beats(read_request_beats),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid), .write_request_ready(write_request_ready),
        .write_request_address(write_request_address), .write_request_beats(write_request_beats),
        .write_valid(write_valid), .write_ready(write_ready), .write_data(write_data),
        .run_start_out(run_start_out), .run_descriptor_out(run_descriptor_out),
        .run_active_out(run_active_out), .run_done_in(run_done_in), .run_result_in(run_result_in),
        .busy_out(memory_busy_out)
    );

    async_fifo #(.WIDTH(128), .DEPTH(128)) read_data_fifo_inst (
        .write_clk(memory_clk), .write_reset(memory_reset), .write_enable(read_beat_push),
        .write_data(read_beat_w), .full(read_beat_full), .write_count(),
        .read_clk(ethernet_clk), .read_reset(ethernet_reset), .read_enable(read_beat_pop),
        .read_data(read_beat_r), .empty(read_beat_empty)
    );

    async_fifo #(.WIDTH(121), .DEPTH(8)) response_fifo_inst (
        .write_clk(memory_clk), .write_reset(memory_reset), .write_enable(response_push),
        .write_data(response_w), .full(response_full), .write_count(),
        .read_clk(ethernet_clk), .read_reset(ethernet_reset), .read_enable(response_pop),
        .read_data(response_r), .empty(response_empty)
    );

    // ---- transmit
    logic [7:0] reply_data, buffered_data;
    logic reply_valid, reply_last, reply_ready;
    logic buffered_valid, buffered_last, TX_ready;
    logic buffer_busy, buffer_overflow, TX_busy, TX_done, TX_underflow;

    memory_link_responder #(
        .LOCAL_MAC (LOCAL_MAC)
    ) responder_inst (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .response_in(response_r), .response_empty_in(response_empty), .response_pop_out(response_pop),
        .read_beat_in(read_beat_r), .read_beat_empty_in(read_beat_empty),
        .read_beat_pop_out(read_beat_pop),
        .data_out(reply_data), .valid_out(reply_valid), .last_out(reply_last),
        .ready_in(reply_ready), .sent_out(replied_out)
    );

    ethernet_TX_buffer frame_buffer (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .data_in(reply_data), .valid_in(reply_valid), .last_in(reply_last), .ready_out(reply_ready),
        .data_out(buffered_data), .valid_out(buffered_valid), .last_out(buffered_last),
        .ready_in(TX_ready), .tx_done_in(TX_done), .tx_underflow_in(TX_underflow),
        .busy_out(buffer_busy), .overflow_out(buffer_overflow)
    );

    ethernet_TX transmitter (
        .clk(ethernet_clk), .reset(ethernet_reset),
        .data_in(buffered_data), .valid_in(buffered_valid), .last_in(buffered_last),
        .ready_out(TX_ready), .rmii_txd(rmii_txd), .rmii_tx_en(rmii_tx_en),
        .busy_out(TX_busy), .done_out(TX_done), .underflow_out(TX_underflow)
    );

    assign rx_error_out = rx_crc_error;

endmodule
