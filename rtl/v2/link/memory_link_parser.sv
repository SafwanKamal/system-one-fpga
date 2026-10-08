// v2 memory link, receive side (Ethernet clock): turns committed frames from
// ethernet_RX_buffer into memory commands and write-data beats.
//
// Frame layout: src/sysone/v2/memory_protocol.py. Accepted:
//   0x20 write  -> its data bytes are packed into 128-bit beats (byte at the lowest
//                  address in bits [7:0]) and pushed to the write-data FIFO; once
//                  the frame has delivered all its beats, or ended early, a write
//                  command for the whole beats received is pushed
//   0x22 read   -> a read command is pushed after the header
//   0x24 run    -> exactly one beat (the run descriptor, see memory_protocol.py),
//                  taken like a write's data; then a run command
// Everything else, and requests that are unaligned, outside MEMORY_BYTES, or ask
// for 0 or more than MAX_BEATS beats, is drained and counted on rejected_out.
//
// Write data always reaches its FIFO before its command, so the executor on the
// memory side finds the beats waiting when it starts the write.
module memory_link_parser #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter logic [15:0] ETHERTYPE = 16'h88B5,
    parameter logic [7:0] PROTOCOL_VERSION = 8'd2,
    parameter logic [7:0] MESSAGE_WRITE = 8'h20,
    parameter logic [7:0] MESSAGE_READ = 8'h22,
    parameter logic [7:0] MESSAGE_RUN = 8'h24,
    parameter longint MEMORY_BYTES = 64'd134217728,
    parameter integer MAX_BEATS = 64
) (
    input logic clk,
    input logic reset,

    // committed frame from ethernet_RX_buffer
    input logic [7:0] data_in,
    input logic valid_in,
    input logic last_in,
    output logic ready_out,

    // write data beats (to the async FIFO towards the memory clock)
    output logic [127:0] beat_out,
    output logic beat_push_out,
    input logic beat_full_in,

    // commands: {is_run, is_read, sequence[31:0], address[31:0], beats[6:0], host_mac[47:0]}
    output logic [120:0] command_out,
    output logic command_push_out,
    input logic command_full_in,

    output logic accepted_out,          // one clock per command pushed
    output logic rejected_out           // one clock per frame dropped
);

    localparam integer HEADER_BYTES = 26;

    typedef enum logic [1:0] {
        HEADER,
        DATA,
        DRAIN
    } state_t;

    state_t state_reg, state_next;

    logic [4:0] byte_index_reg, byte_index_next;
    logic local_match_reg, local_match_next;
    logic broadcast_match_reg, broadcast_match_next;
    logic header_ok_reg, header_ok_next;
    logic is_read_reg, is_read_next;
    logic is_run_reg, is_run_next;
    logic [47:0] host_mac_reg, host_mac_next;
    logic [31:0] sequence_reg, sequence_next;
    logic [31:0] address_reg, address_next;
    logic [15:0] beats_reg, beats_next;
    logic [127:0] beat_reg, beat_next;
    logic [3:0] beat_byte_reg, beat_byte_next;
    logic [6:0] beats_received_reg, beats_received_next;
    logic accepted_reg, accepted_next;
    logic rejected_reg, rejected_next;

    logic accept;
    logic [15:0] beats_with_byte;
    logic header_ok_with_byte;
    logic request_valid;


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= HEADER;
            byte_index_reg <= '0;
            local_match_reg <= 1'b1;
            broadcast_match_reg <= 1'b1;
            header_ok_reg <= 1'b1;
            is_read_reg <= 1'b0;
            is_run_reg <= 1'b0;
            host_mac_reg <= '0;
            sequence_reg <= '0;
            address_reg <= '0;
            beats_reg <= '0;
            beat_reg <= '0;
            beat_byte_reg <= '0;
            beats_received_reg <= '0;
            accepted_reg <= 1'b0;
            rejected_reg <= 1'b0;
        end else begin
            state_reg <= state_next;
            byte_index_reg <= byte_index_next;
            local_match_reg <= local_match_next;
            broadcast_match_reg <= broadcast_match_next;
            header_ok_reg <= header_ok_next;
            is_read_reg <= is_read_next;
            is_run_reg <= is_run_next;
            host_mac_reg <= host_mac_next;
            sequence_reg <= sequence_next;
            address_reg <= address_next;
            beats_reg <= beats_next;
            beat_reg <= beat_next;
            beat_byte_reg <= beat_byte_next;
            beats_received_reg <= beats_received_next;
            accepted_reg <= accepted_next;
            rejected_reg <= rejected_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        byte_index_next = byte_index_reg;
        local_match_next = local_match_reg;
        broadcast_match_next = broadcast_match_reg;
        header_ok_next = header_ok_reg;
        is_read_next = is_read_reg;
        is_run_next = is_run_reg;
        host_mac_next = host_mac_reg;
        sequence_next = sequence_reg;
        address_next = address_reg;
        beats_next = beats_reg;
        beat_next = beat_reg;
        beat_byte_next = beat_byte_reg;
        beats_received_next = beats_received_reg;
        accepted_next = 1'b0;
        rejected_next = 1'b0;

        ready_out = 1'b0;
        beat_out = beat_reg;
        beat_push_out = 1'b0;
        command_out = {is_run_reg, is_read_reg, sequence_reg, address_reg, beats_received_reg, host_mac_reg};
        command_push_out = 1'b0;

        accept = 1'b0;
        beats_with_byte = beats_reg;
        header_ok_with_byte = header_ok_reg;
        request_valid = 1'b0;

        case (state_reg)
            HEADER: begin
                // the last header byte of a read waits for room for its command
                accept = valid_in && !(byte_index_reg == HEADER_BYTES - 1 && command_full_in);
                ready_out = accept;

                if (accept) begin
                    byte_index_next = byte_index_reg + 1'b1;

                    if (byte_index_reg < 6) begin
                        if (data_in != LOCAL_MAC[47 - 8 * byte_index_reg -: 8]) local_match_next = 1'b0;
                        if (data_in != 8'hFF) broadcast_match_next = 1'b0;
                    end else if (byte_index_reg < 12) begin
                        host_mac_next = {host_mac_reg[39:0], data_in};
                    end else if (byte_index_reg == 12) begin
                        header_ok_with_byte = header_ok_reg && (data_in == ETHERTYPE[15:8]);
                    end else if (byte_index_reg == 13) begin
                        header_ok_with_byte = header_ok_reg && (data_in == ETHERTYPE[7:0]);
                    end else if (byte_index_reg == 14) begin
                        header_ok_with_byte = header_ok_reg && (data_in == PROTOCOL_VERSION);
                    end else if (byte_index_reg == 15) begin
                        header_ok_with_byte = header_ok_reg
                                              && (data_in == MESSAGE_WRITE || data_in == MESSAGE_READ
                                                  || data_in == MESSAGE_RUN);
                        is_read_next = (data_in == MESSAGE_READ);
                        is_run_next = (data_in == MESSAGE_RUN);
                    end else if (byte_index_reg < 20) begin
                        sequence_next = {sequence_reg[23:0], data_in};
                    end else if (byte_index_reg < 24) begin
                        address_next = {address_reg[23:0], data_in};
                    end else begin
                        beats_with_byte = {beats_reg[7:0], data_in};
                        beats_next = beats_with_byte;
                    end
                    header_ok_next = header_ok_with_byte;

                    if (byte_index_reg == HEADER_BYTES - 1) begin
                        byte_index_next = '0;
                        request_valid = header_ok_with_byte && (local_match_reg || broadcast_match_reg)
                                        && (address_reg[3:0] == 4'h0)
                                        && (64'(address_reg) < MEMORY_BYTES)
                                        && (beats_with_byte != 0)
                                        && (beats_with_byte <= MAX_BEATS)
                                        && (!is_run_reg || beats_with_byte == 16'd1);
                        beats_received_next = '0;
                        beat_byte_next = '0;

                        if (!request_valid) begin
                            rejected_next = 1'b1;
                            state_next = last_in ? HEADER : DRAIN;
                        end else if (is_read_reg) begin
                            command_out = {1'b0, 1'b1, sequence_reg, address_reg, beats_with_byte[6:0],
                                           host_mac_reg};
                            command_push_out = 1'b1;
                            accepted_next = 1'b1;
                            state_next = last_in ? HEADER : DRAIN;
                        end else if (last_in) begin
                            rejected_next = 1'b1;              // a write with no data
                            state_next = HEADER;
                        end else begin
                            state_next = DATA;
                        end
                    end else if (last_in) begin
                        rejected_next = 1'b1;                  // shorter than a header
                        byte_index_next = '0;
                        state_next = HEADER;
                    end
                end
            end

            DATA: begin
                // a byte that completes a beat needs room for the beat, and if it is the
                // last beat (or the frame ends) room for the command as well
                accept = valid_in
                         && !(beat_byte_reg == 4'd15 && beat_full_in)
                         && !(command_full_in && (last_in
                              || (beat_byte_reg == 4'd15 && beats_received_reg + 1'b1 == beats_reg[6:0])));
                ready_out = accept;

                if (accept) begin
                    beat_next[8 * beat_byte_reg +: 8] = data_in;
                    beat_byte_next = beat_byte_reg + 1'b1;

                    if (beat_byte_reg == 4'd15) begin
                        beat_out = beat_next;
                        beat_push_out = 1'b1;
                        beats_received_next = beats_received_reg + 1'b1;
                    end

                    if ((beat_byte_reg == 4'd15 && beats_received_reg + 1'b1 == beats_reg[6:0])
                        || last_in) begin
                        // done: write the whole beats that arrived
                        if (beats_received_next != 0) begin
                            command_out = {is_run_reg, 1'b0, sequence_reg, address_reg, beats_received_next,
                                           host_mac_reg};
                            command_push_out = 1'b1;
                            accepted_next = 1'b1;
                        end else begin
                            rejected_next = 1'b1;
                        end
                        state_next = last_in ? HEADER : DRAIN;
                    end
                end
            end

            DRAIN: begin
                ready_out = 1'b1;
                if (valid_in && last_in) begin
                    state_next = HEADER;
                end
            end

            default: begin
                state_next = HEADER;
            end
        endcase

        if (state_next == HEADER && state_reg != HEADER
            || (state_reg == HEADER && state_next == HEADER && accept && byte_index_next == 0)) begin
            local_match_next = 1'b1;
            broadcast_match_next = 1'b1;
            header_ok_next = 1'b1;
        end
        if (state_reg == HEADER && accept && byte_index_reg == HEADER_BYTES - 1) begin
            local_match_next = 1'b1;
            broadcast_match_next = 1'b1;
            header_ok_next = 1'b1;
        end
    end

    assign accepted_out = accepted_reg;
    assign rejected_out = rejected_reg;

endmodule
