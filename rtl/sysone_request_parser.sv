// Parses a committed request frame and feeds its text to sysone_core.
//
// Frame layout (see src/sysone/ethernet_protocol.py):
//   0..5   destination MAC    LOCAL_MAC or broadcast
//   6..11  source MAC         the host; the result goes back to it
//   12..13 EtherType          0x88B5
//   14     version            1
//   15     message type       0x10, classify request
//   16..19 sequence number    echoed in the result
//   20..21 text length
//   22..   text, then Ethernet padding, which is skipped
// Anything else is drained and counted on rejected_out.
//
// One request is in flight at a time. A new frame is not started until the previous
// decision is out and sysone_result_packet has copied it into the transmit buffer,
// so the sequence number, host MAC and logits of one request can never mix with the
// next one's.
module sysone_request_parser #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter logic [15:0] ETHERTYPE = 16'h88B5,
    parameter logic [7:0] PROTOCOL_VERSION = 8'd1,
    parameter logic [7:0] MESSAGE_REQUEST = 8'h10
) (
    input  logic clk,
    input  logic reset,

    // committed frame from ethernet_RX_buffer
    input  logic [7:0] data_in,
    input  logic valid_in,
    input  logic last_in,
    output logic ready_out,

    // message bytes to sysone_core
    output logic [7:0] core_data_out,
    output logic core_valid_out,
    output logic core_message_end_out,
    input  logic core_ready_in,

    input  logic decision_valid_in,
    input  logic result_busy_in,

    output logic [47:0] host_mac_out,
    output logic [31:0] sequence_number_out,
    output logic request_out,          // one clock: a request was handed to the core
    output logic rejected_out          // one clock: a frame was not a request for us
);

    localparam integer HEADER_BYTES = 22;

    typedef enum logic [2:0] {
        HEADER,
        TEXT,
        MESSAGE_END,
        DRAIN
    } state_t;

    state_t state_reg, state_next;

    logic [4:0] byte_index_reg, byte_index_next;
    logic local_match_reg, local_match_next;
    logic broadcast_match_reg, broadcast_match_next;
    logic header_ok_reg, header_ok_next;
    logic [47:0] host_mac_reg, host_mac_next;
    logic [31:0] sequence_number_reg, sequence_number_next;
    logic [15:0] text_length_reg, text_length_next;
    logic frame_consumed_reg, frame_consumed_next;
    logic in_flight_reg, in_flight_next;
    logic request_reg, request_next;
    logic rejected_reg, rejected_next;

    logic accept_header_byte;
    logic header_ok_with_byte;
    logic [15:0] text_length_with_byte;


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= HEADER;
            byte_index_reg <= '0;
            local_match_reg <= 1'b1;
            broadcast_match_reg <= 1'b1;
            header_ok_reg <= 1'b1;
            host_mac_reg <= '0;
            sequence_number_reg <= '0;
            text_length_reg <= '0;
            frame_consumed_reg <= 1'b0;
            in_flight_reg <= 1'b0;
            request_reg <= 1'b0;
            rejected_reg <= 1'b0;
        end else begin
            state_reg <= state_next;
            byte_index_reg <= byte_index_next;
            local_match_reg <= local_match_next;
            broadcast_match_reg <= broadcast_match_next;
            header_ok_reg <= header_ok_next;
            host_mac_reg <= host_mac_next;
            sequence_number_reg <= sequence_number_next;
            text_length_reg <= text_length_next;
            frame_consumed_reg <= frame_consumed_next;
            in_flight_reg <= in_flight_next;
            request_reg <= request_next;
            rejected_reg <= rejected_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        byte_index_next = byte_index_reg;
        local_match_next = local_match_reg;
        broadcast_match_next = broadcast_match_reg;
        header_ok_next = header_ok_reg;
        host_mac_next = host_mac_reg;
        sequence_number_next = sequence_number_reg;
        text_length_next = text_length_reg;
        frame_consumed_next = frame_consumed_reg;
        in_flight_next = in_flight_reg;
        request_next = 1'b0;
        rejected_next = 1'b0;

        ready_out = 1'b0;
        core_data_out = data_in;
        core_valid_out = 1'b0;
        core_message_end_out = 1'b0;

        accept_header_byte = 1'b0;
        header_ok_with_byte = header_ok_reg;
        text_length_with_byte = text_length_reg;

        if (decision_valid_in) begin
            in_flight_next = 1'b0;
        end

        case (state_reg)
            HEADER: begin
                // The first byte waits until the previous request is fully answered
                accept_header_byte = valid_in
                    && (byte_index_reg != 0 || (!in_flight_reg && !result_busy_in));
                ready_out = accept_header_byte;

                if (accept_header_byte) begin
                    byte_index_next = byte_index_reg + 1'b1;

                    if (byte_index_reg < 6) begin
                        if (data_in != LOCAL_MAC[47 - 8 * byte_index_reg -: 8]) begin
                            local_match_next = 1'b0;
                        end
                        if (data_in != 8'hFF) begin
                            broadcast_match_next = 1'b0;
                        end
                    end else if (byte_index_reg < 12) begin
                        host_mac_next = {host_mac_reg[39:0], data_in};
                    end else if (byte_index_reg == 12) begin
                        header_ok_with_byte = header_ok_reg && (data_in == ETHERTYPE[15:8]);
                    end else if (byte_index_reg == 13) begin
                        header_ok_with_byte = header_ok_reg && (data_in == ETHERTYPE[7:0]);
                    end else if (byte_index_reg == 14) begin
                        header_ok_with_byte = header_ok_reg && (data_in == PROTOCOL_VERSION);
                    end else if (byte_index_reg == 15) begin
                        header_ok_with_byte = header_ok_reg && (data_in == MESSAGE_REQUEST);
                    end else if (byte_index_reg < 20) begin
                        sequence_number_next = {sequence_number_reg[23:0], data_in};
                    end else begin
                        text_length_with_byte = {text_length_reg[7:0], data_in};
                        text_length_next = text_length_with_byte;
                    end

                    header_ok_next = header_ok_with_byte;

                    if (byte_index_reg == HEADER_BYTES - 1) begin
                        // The whole header is in: forward the text, or skip the frame
                        byte_index_next = '0;
                        frame_consumed_next = last_in;

                        if (header_ok_with_byte && (local_match_reg || broadcast_match_reg)) begin
                            if (text_length_with_byte == 0 || last_in) begin
                                state_next = MESSAGE_END;
                            end else begin
                                state_next = TEXT;
                            end
                        end else begin
                            rejected_next = 1'b1;
                            state_next = last_in ? HEADER : DRAIN;
                        end
                    end else if (last_in) begin
                        // shorter than a header
                        rejected_next = 1'b1;
                        byte_index_next = '0;
                        state_next = HEADER;
                    end

                    if (state_next == HEADER && byte_index_next == 0) begin
                        local_match_next = 1'b1;
                        broadcast_match_next = 1'b1;
                        header_ok_next = 1'b1;
                    end
                end
            end

            TEXT: begin
                core_valid_out = valid_in;
                ready_out = core_ready_in;

                if (valid_in && core_ready_in) begin
                    text_length_next = text_length_reg - 1'b1;

                    // a frame shorter than its length field ends the message early
                    if (text_length_reg == 1 || last_in) begin
                        frame_consumed_next = last_in;
                        state_next = MESSAGE_END;
                    end
                end
            end

            MESSAGE_END: begin
                core_valid_out = 1'b1;
                core_message_end_out = 1'b1;

                if (core_ready_in) begin
                    request_next = 1'b1;
                    in_flight_next = 1'b1;
                    state_next = frame_consumed_reg ? HEADER : DRAIN;
                    local_match_next = 1'b1;
                    broadcast_match_next = 1'b1;
                    header_ok_next = 1'b1;
                end
            end

            DRAIN: begin
                // skip padding, or the rest of a frame that was not for us
                ready_out = 1'b1;

                if (valid_in && last_in) begin
                    state_next = HEADER;
                    local_match_next = 1'b1;
                    broadcast_match_next = 1'b1;
                    header_ok_next = 1'b1;
                end
            end

            default: begin
                state_next = HEADER;
                byte_index_next = '0;
            end
        endcase
    end

    assign host_mac_out = host_mac_reg;
    assign sequence_number_out = sequence_number_reg;
    assign request_out = request_reg;
    assign rejected_out = rejected_reg;

endmodule
