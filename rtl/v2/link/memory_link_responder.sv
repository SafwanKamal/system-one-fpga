// v2 memory link, transmit side (Ethernet clock): one reply frame per executed
// command, into ethernet_TX_buffer (which adds nothing; ethernet_TX pads and
// appends the FCS).
//
//   0..5 host MAC, 6..11 LOCAL_MAC, 12..13 EtherType, 14 version 2,
//   15 type (0x21 write ack / 0x23 read data / 0x25 run done), 16..19 sequence,
//   20..23 address, 24..25 beats, then for a read or a run the beats from the
//   read-data FIFO, byte at the lowest address first (bits [7:0] of each beat first).
module memory_link_responder #(
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter logic [15:0] ETHERTYPE = 16'h88B5,
    parameter logic [7:0] PROTOCOL_VERSION = 8'd2,
    parameter logic [7:0] MESSAGE_WRITE_ACK = 8'h21,
    parameter logic [7:0] MESSAGE_READ_DATA = 8'h23,
    parameter logic [7:0] MESSAGE_RUN_DONE = 8'h25
) (
    input logic clk,
    input logic reset,

    input logic [120:0] response_in,
    input logic response_empty_in,
    output logic response_pop_out,

    input logic [127:0] read_beat_in,
    input logic read_beat_empty_in,
    output logic read_beat_pop_out,

    output logic [7:0] data_out,
    output logic valid_out,
    output logic last_out,
    input logic ready_in,

    output logic sent_out                     // one clock per reply frame handed over
);

    localparam integer HEADER_BYTES = 26;

    typedef enum logic [1:0] {
        IDLE,
        HEADER,
        DATA
    } state_t;

    state_t state_reg, state_next;
    logic [120:0] response_reg, response_next;
    logic [4:0] byte_index_reg, byte_index_next;
    logic [3:0] beat_byte_reg, beat_byte_next;
    logic [6:0] beats_left_reg, beats_left_next;
    logic sent_reg, sent_next;

    wire is_run = response_reg[120];
    wire is_read = response_reg[119];
    wire has_data = is_read | is_run;
    wire [31:0] sequence_number = response_reg[118:87];
    wire [31:0] address = response_reg[86:55];
    wire [6:0] beats = response_reg[54:48];
    wire [47:0] host_mac = response_reg[47:0];
    logic [7:0] header_byte;


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            response_reg <= '0;
            byte_index_reg <= '0;
            beat_byte_reg <= '0;
            beats_left_reg <= '0;
            sent_reg <= 1'b0;
        end else begin
            state_reg <= state_next;
            response_reg <= response_next;
            byte_index_reg <= byte_index_next;
            beat_byte_reg <= beat_byte_next;
            beats_left_reg <= beats_left_next;
            sent_reg <= sent_next;
        end
    end


    always_comb begin
        case (byte_index_reg)
            5'd0, 5'd1, 5'd2, 5'd3, 5'd4, 5'd5:
                header_byte = host_mac[47 - 8 * byte_index_reg -: 8];
            5'd6, 5'd7, 5'd8, 5'd9, 5'd10, 5'd11:
                header_byte = LOCAL_MAC[47 - 8 * (byte_index_reg - 6) -: 8];
            5'd12: header_byte = ETHERTYPE[15:8];
            5'd13: header_byte = ETHERTYPE[7:0];
            5'd14: header_byte = PROTOCOL_VERSION;
            5'd15: header_byte = is_run ? MESSAGE_RUN_DONE : is_read ? MESSAGE_READ_DATA : MESSAGE_WRITE_ACK;
            5'd16: header_byte = sequence_number[31:24];
            5'd17: header_byte = sequence_number[23:16];
            5'd18: header_byte = sequence_number[15:8];
            5'd19: header_byte = sequence_number[7:0];
            5'd20: header_byte = address[31:24];
            5'd21: header_byte = address[23:16];
            5'd22: header_byte = address[15:8];
            5'd23: header_byte = address[7:0];
            5'd24: header_byte = 8'h00;
            default: header_byte = {1'b0, beats};
        endcase
    end


    always_comb begin
        state_next = state_reg;
        response_next = response_reg;
        byte_index_next = byte_index_reg;
        beat_byte_next = beat_byte_reg;
        beats_left_next = beats_left_reg;
        sent_next = 1'b0;

        response_pop_out = 1'b0;
        read_beat_pop_out = 1'b0;
        data_out = header_byte;
        valid_out = 1'b0;
        last_out = 1'b0;

        case (state_reg)
            IDLE: begin
                if (!response_empty_in) begin
                    response_pop_out = 1'b1;
                    response_next = response_in;
                    byte_index_next = '0;
                    state_next = HEADER;
                end
            end

            HEADER: begin
                valid_out = 1'b1;
                last_out = (byte_index_reg == HEADER_BYTES - 1) && !has_data;
                if (ready_in) begin
                    byte_index_next = byte_index_reg + 1'b1;
                    if (byte_index_reg == HEADER_BYTES - 1) begin
                        if (has_data) begin
                            beat_byte_next = '0;
                            beats_left_next = beats;
                            state_next = DATA;
                        end else begin
                            sent_next = 1'b1;
                            state_next = IDLE;
                        end
                    end
                end
            end

            DATA: begin
                data_out = read_beat_in[8 * beat_byte_reg +: 8];
                valid_out = !read_beat_empty_in;
                last_out = (beat_byte_reg == 4'd15) && (beats_left_reg == 1);
                if (valid_out && ready_in) begin
                    beat_byte_next = beat_byte_reg + 1'b1;
                    if (beat_byte_reg == 4'd15) begin
                        read_beat_pop_out = 1'b1;
                        beats_left_next = beats_left_reg - 1'b1;
                        if (beats_left_reg == 1) begin
                            sent_next = 1'b1;
                            state_next = IDLE;
                        end
                    end
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign sent_out = sent_reg;

endmodule
