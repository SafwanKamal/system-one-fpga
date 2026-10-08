// The v2 board core without board-specific parts: the memory link (Ethernet <->
// external memory, rtl/v2/link) and, with ENCODER = 1, the encoder behind the link's
// RUN command (rtl/v2/encoder/encoder_system.sv). Same ports as memory_link_core;
// a board top adds clocking, its memory controller adapter and status outputs.
//
// One memory port: the link's executor owns it, except while a RUN command is
// executing (run_active), when the encoder system does. The executor waits for the
// run to finish, so the two never compete.
//
// With ENCODER = 0 a RUN command is answered at once with status 0x80 (no encoder
// in this bitstream), so hosts can tell the builds apart.
module sysone_v2_core #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter longint MEMORY_BYTES = 64'd134217728,
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer ENCODER = 1,
    parameter integer TILE_OUT = 12,
    parameter integer MAX_TOKENS = 128,
    parameter integer MAX_HEAD_DIM = 64,
    parameter integer MAX_HIDDEN = 384,
    // the encoder's array options (encoder_layer): 16 x 12 plain by default; the packed
    // option is TILE_OUT 24, MAC_PACK 1, ATTENTION_LANES 12, ACCUMULATORS_IN_LUTS 1,
    // DRAIN_LANES 2 and needs images built with --tile 16x24
    parameter integer MAC_PACK = 0,
    parameter integer ATTENTION_LANES = TILE_OUT,
    parameter integer ACCUMULATORS_IN_LUTS = 0,
    parameter integer DRAIN_LANES = 1
) (
    // Ethernet clock domain
    input logic ethernet_clk,
    input logic ethernet_reset,
    input logic [1:0] rmii_rxd,
    input logic rmii_crs_dv,
    input logic rmii_rx_er,
    output logic [1:0] rmii_txd,
    output logic rmii_tx_en,

    output logic accepted_out,
    output logic rejected_out,
    output logic replied_out,
    output logic rx_error_out,
    output logic dropped_out,

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

    output logic memory_busy_out,
    output logic encoder_busy_out
);

    logic run_start, run_active, run_done;
    logic [127:0] run_descriptor, run_result;

    // the link's memory port
    logic link_read_request_valid, link_read_ready, link_write_request_valid, link_write_valid;
    logic [ADDRESS_WIDTH-1:0] link_read_request_address, link_write_request_address;
    logic [BEATS_WIDTH-1:0] link_read_request_beats, link_write_request_beats;
    logic [127:0] link_write_data;

    memory_link_core #(
        .LOCAL_MAC(LOCAL_MAC),
        .MEMORY_BYTES(MEMORY_BYTES),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH)
    ) link_inst (
        .ethernet_clk(ethernet_clk), .ethernet_reset(ethernet_reset),
        .rmii_rxd(rmii_rxd), .rmii_crs_dv(rmii_crs_dv), .rmii_rx_er(rmii_rx_er),
        .rmii_txd(rmii_txd), .rmii_tx_en(rmii_tx_en),
        .accepted_out(accepted_out), .rejected_out(rejected_out), .replied_out(replied_out),
        .rx_error_out(rx_error_out), .dropped_out(dropped_out),
        .memory_clk(memory_clk), .memory_reset(memory_reset),
        .read_request_valid(link_read_request_valid),
        .read_request_ready(read_request_ready && !run_active),
        .read_request_address(link_read_request_address),
        .read_request_beats(link_read_request_beats),
        .read_valid(read_valid && !run_active), .read_ready(link_read_ready),
        .read_data(read_data), .read_last(read_last),
        .write_request_valid(link_write_request_valid),
        .write_request_ready(write_request_ready && !run_active),
        .write_request_address(link_write_request_address),
        .write_request_beats(link_write_request_beats),
        .write_valid(link_write_valid), .write_ready(write_ready && !run_active),
        .write_data(link_write_data),
        .run_start_out(run_start), .run_descriptor_out(run_descriptor),
        .run_active_out(run_active), .run_done_in(run_done), .run_result_in(run_result),
        .memory_busy_out(memory_busy_out)
    );

    if (ENCODER != 0) begin : gen_encoder
        logic encoder_read_request_valid, encoder_read_ready;
        logic encoder_write_request_valid, encoder_write_valid;
        logic [ADDRESS_WIDTH-1:0] encoder_read_request_address, encoder_write_request_address;
        logic [BEATS_WIDTH-1:0] encoder_read_request_beats, encoder_write_request_beats;
        logic [127:0] encoder_write_data;

        encoder_system #(
            .TILE_OUT(TILE_OUT),
            .MAX_TOKENS(MAX_TOKENS),
            .MAX_HEAD_DIM(MAX_HEAD_DIM),
            .MAX_HIDDEN(MAX_HIDDEN),
            .MAC_PACK(MAC_PACK),
            .ATTENTION_LANES(ATTENTION_LANES),
            .ACCUMULATORS_IN_LUTS(ACCUMULATORS_IN_LUTS),
            .DRAIN_LANES(DRAIN_LANES),
            .ADDRESS_WIDTH(ADDRESS_WIDTH),
            .BEATS_WIDTH(BEATS_WIDTH)
        ) encoder_system_inst (
            .clk(memory_clk),
            .reset(memory_reset),
            .run_start(run_start),
            .run_descriptor(run_descriptor),
            .run_done(run_done),
            .run_result(run_result),
            .busy(encoder_busy_out),
            .read_request_valid(encoder_read_request_valid),
            .read_request_ready(read_request_ready && run_active),
            .read_request_address(encoder_read_request_address),
            .read_request_beats(encoder_read_request_beats),
            .read_valid(read_valid && run_active),
            .read_ready(encoder_read_ready),
            .read_data(read_data),
            .read_last(read_last),
            .write_request_valid(encoder_write_request_valid),
            .write_request_ready(write_request_ready && run_active),
            .write_request_address(encoder_write_request_address),
            .write_request_beats(encoder_write_request_beats),
            .write_valid(encoder_write_valid),
            .write_ready(write_ready && run_active),
            .write_data(encoder_write_data)
        );

        always_comb begin
            if (run_active) begin
                read_request_valid = encoder_read_request_valid;
                read_request_address = encoder_read_request_address;
                read_request_beats = encoder_read_request_beats;
                read_ready = encoder_read_ready;
                write_request_valid = encoder_write_request_valid;
                write_request_address = encoder_write_request_address;
                write_request_beats = encoder_write_request_beats;
                write_valid = encoder_write_valid;
                write_data = encoder_write_data;
            end else begin
                read_request_valid = link_read_request_valid;
                read_request_address = link_read_request_address;
                read_request_beats = link_read_request_beats;
                read_ready = link_read_ready;
                write_request_valid = link_write_request_valid;
                write_request_address = link_write_request_address;
                write_request_beats = link_write_request_beats;
                write_valid = link_write_valid;
                write_data = link_write_data;
            end
        end
    end else begin : gen_no_encoder
        logic done_reg;
        always_ff @(posedge memory_clk or posedge memory_reset) begin
            if (memory_reset) done_reg <= 1'b0;
            else done_reg <= run_start;
        end
        assign run_done = done_reg;
        assign run_result = {56'd0, 8'h80, 64'd0};
        assign encoder_busy_out = 1'b0;
        assign read_request_valid = link_read_request_valid;
        assign read_request_address = link_read_request_address;
        assign read_request_beats = link_read_request_beats;
        assign read_ready = link_read_ready;
        assign write_request_valid = link_write_request_valid;
        assign write_request_address = link_write_request_address;
        assign write_request_beats = link_write_request_beats;
        assign write_valid = link_write_valid;
        assign write_data = link_write_data;
    end

endmodule
