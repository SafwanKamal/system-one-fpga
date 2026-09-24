// 100 Mbps full-duplex receive framing: checks the FCS and the minimum length.
//
// The receive-side counterpart of ethernet_TX, using the same ethernet_CRC32. The
// bytes are passed straight through; whether the frame was good is only known at
// its end, so ethernet_RX_buffer holds the frame and commits or discards it on
// frame_end_out.
//
// FCS check. Running the CRC over the whole frame including its FCS leaves the
// fixed residue 0xDEBB20E3 in the register, whatever the data. ethernet_CRC32
// outputs the complement of its register, so a good frame reads 0x2144DF1C.
module ethernet_RX #(
    parameter int MINIMUM_FRAME_BYTES = 64     // destination through FCS
) (
    input  logic clk,
    input  logic reset,

    input  logic [1:0] rmii_rxd,
    input  logic rmii_crs_dv,
    input  logic rmii_rx_er,

    output logic frame_start_out,
    output logic [7:0] data_out,       // destination MAC through FCS
    output logic valid_out,
    output logic frame_end_out,
    output logic frame_good_out,       // with frame_end_out
    output logic crc_error_out         // one clock: a frame failed its FCS or framing
);

    localparam logic [31:0] GOOD_CRC_OUTPUT = 32'h2144DF1C;

    logic rmii_frame_start, rmii_valid, rmii_frame_end, rmii_frame_error;
    logic [7:0] rmii_data;

    logic [31:0] crc_value;

    logic [10:0] byte_count_reg, byte_count_next;
    logic frame_good_reg, frame_good_next;
    logic crc_error_reg, crc_error_next;
    logic frame_end_reg, frame_end_next;

    rmii_RX deserializer (
        .clk            (clk),
        .reset          (reset),
        .rmii_rxd       (rmii_rxd),
        .rmii_crs_dv    (rmii_crs_dv),
        .rmii_rx_er     (rmii_rx_er),
        .frame_start_out(rmii_frame_start),
        .data_out       (rmii_data),
        .valid_out      (rmii_valid),
        .frame_end_out  (rmii_frame_end),
        .frame_error_out(rmii_frame_error)
    );

    ethernet_CRC32 crc_calculator (
        .clk      (clk),
        .reset    (reset),
        .clear_in (rmii_frame_start),
        .data_in  (rmii_data),
        .enable_in(rmii_valid),
        .crc_out  (crc_value)
    );

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            byte_count_reg <= 0;
            frame_good_reg <= 1'b0;
            crc_error_reg <= 1'b0;
            frame_end_reg <= 1'b0;
        end else begin
            byte_count_reg <= byte_count_next;
            frame_good_reg <= frame_good_next;
            crc_error_reg <= crc_error_next;
            frame_end_reg <= frame_end_next;
        end
    end

    always_comb begin
        byte_count_next = byte_count_reg;
        frame_good_next = 1'b0;
        crc_error_next = 1'b0;
        frame_end_next = 1'b0;

        if (rmii_frame_start) begin
            byte_count_next = 0;
        end else if (rmii_valid && byte_count_reg != 11'h7FF) begin
            // saturate; only the minimum length matters here
            byte_count_next = byte_count_reg + 1'b1;
        end

        // The CRC register takes the last byte on the same edge as the rmii end
        // pulse is registered, so it is settled when frame_end is seen here.
        if (rmii_frame_end) begin
            frame_end_next = 1'b1;
            frame_good_next = !rmii_frame_error
                && (crc_value == GOOD_CRC_OUTPUT)
                && (byte_count_reg >= MINIMUM_FRAME_BYTES);
            crc_error_next = !frame_good_next;
        end
    end

    // bytes pass through with the deserializer's timing
    assign frame_start_out = rmii_frame_start;
    assign data_out = rmii_data;
    assign valid_out = rmii_valid;
    assign frame_end_out = frame_end_reg;
    assign frame_good_out = frame_good_reg;
    assign crc_error_out = crc_error_reg;

endmodule
