// Builds the result frame for one decision and hands it to ethernet_TX_buffer.
//
// Frame layout (see src/sysone/ethernet_protocol.py), FCS added by ethernet_TX:
//   0..5   destination MAC    the requesting host
//   6..11  source MAC         LOCAL_MAC
//   12..13 EtherType          0x88B5
//   14     version            1
//   15     message type       0x11, classify result
//   16..19 sequence number    from the request
//   20     class              argmax
//   21     flags              bit 0: message buffer overflow
//   22..23 feature count
//   24..25 top logit
//   26..27 second logit
//   28..   CLASS_NUMBER logits, int16 big-endian, in class order
//
// All logits are sent, not only the argmax, because calibration lives in them: the
// host's softmax(logits * s_out) is the calibrated probability vector.
//
// The logits arrive one per clock before the decision and are kept in a small
// LUTRAM. busy_out stays high from the decision until the last byte has been
// accepted by the transmit buffer, and sysone_request_parser waits for it before
// starting the next request.
module sysone_result_packet #(
    parameter integer CLASS_NUMBER = 151,
    parameter logic [47:0] LOCAL_MAC = 48'h02_00_00_00_00_02,
    parameter logic [15:0] ETHERTYPE = 16'h88B5,
    parameter logic [7:0] PROTOCOL_VERSION = 8'd1,
    parameter logic [7:0] MESSAGE_RESULT = 8'h11
) (
    input  logic clk,
    input  logic reset,

    input  logic logit_valid_in,
    input  logic [7:0] logit_class_in,
    input  logic signed [15:0] logit_in,

    input  logic decision_valid_in,
    input  logic [7:0] decision_class_in,
    input  logic signed [15:0] top_logit_in,
    input  logic signed [15:0] second_logit_in,
    input  logic [8:0] feature_count_in,
    input  logic overflow_in,
    input  logic [47:0] host_mac_in,
    input  logic [31:0] sequence_number_in,

    // frame to ethernet_TX_buffer
    output logic [7:0] data_out,
    output logic valid_out,
    output logic last_out,
    input  logic ready_in,

    output logic busy_out
);

    localparam integer HEADER_BYTES = 28;
    localparam integer FRAME_BYTES = HEADER_BYTES + 2 * CLASS_NUMBER;
    localparam integer INDEX_WIDTH = $clog2(FRAME_BYTES);

    typedef enum logic {
        IDLE,
        SEND
    } state_t;

    state_t state_reg, state_next;

    logic signed [15:0] logit_memory [0:CLASS_NUMBER-1];

    logic [INDEX_WIDTH-1:0] byte_index_reg, byte_index_next;
    logic [47:0] host_mac_reg, host_mac_next;
    logic [31:0] sequence_number_reg, sequence_number_next;
    logic [7:0] class_reg, class_next;
    logic [7:0] flags_reg, flags_next;
    logic [15:0] feature_count_reg, feature_count_next;
    logic [15:0] top_logit_reg, top_logit_next;
    logic [15:0] second_logit_reg, second_logit_next;

    logic [15:0] logit_word;
    logic [INDEX_WIDTH-1:0] logit_byte_index;


    // written as the logits stream past; LUTRAM, so no reset
    always_ff @(posedge clk) begin
        if (logit_valid_in) begin
            logit_memory[logit_class_in] <= logit_in;
        end
    end


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            byte_index_reg <= '0;
            host_mac_reg <= '0;
            sequence_number_reg <= '0;
            class_reg <= '0;
            flags_reg <= '0;
            feature_count_reg <= '0;
            top_logit_reg <= '0;
            second_logit_reg <= '0;
        end else begin
            state_reg <= state_next;
            byte_index_reg <= byte_index_next;
            host_mac_reg <= host_mac_next;
            sequence_number_reg <= sequence_number_next;
            class_reg <= class_next;
            flags_reg <= flags_next;
            feature_count_reg <= feature_count_next;
            top_logit_reg <= top_logit_next;
            second_logit_reg <= second_logit_next;
        end
    end


    // The byte at byte_index_reg, like frame_byte() in Genome's ethernet test tops
    always_comb begin
        logit_byte_index = byte_index_reg - HEADER_BYTES;
        logit_word = logit_memory[logit_byte_index[INDEX_WIDTH-1:1]];

        case (byte_index_reg)
            0:  data_out = host_mac_reg[47:40];
            1:  data_out = host_mac_reg[39:32];
            2:  data_out = host_mac_reg[31:24];
            3:  data_out = host_mac_reg[23:16];
            4:  data_out = host_mac_reg[15:8];
            5:  data_out = host_mac_reg[7:0];
            6:  data_out = LOCAL_MAC[47:40];
            7:  data_out = LOCAL_MAC[39:32];
            8:  data_out = LOCAL_MAC[31:24];
            9:  data_out = LOCAL_MAC[23:16];
            10: data_out = LOCAL_MAC[15:8];
            11: data_out = LOCAL_MAC[7:0];
            12: data_out = ETHERTYPE[15:8];
            13: data_out = ETHERTYPE[7:0];
            14: data_out = PROTOCOL_VERSION;
            15: data_out = MESSAGE_RESULT;
            16: data_out = sequence_number_reg[31:24];
            17: data_out = sequence_number_reg[23:16];
            18: data_out = sequence_number_reg[15:8];
            19: data_out = sequence_number_reg[7:0];
            20: data_out = class_reg;
            21: data_out = flags_reg;
            22: data_out = feature_count_reg[15:8];
            23: data_out = feature_count_reg[7:0];
            24: data_out = top_logit_reg[15:8];
            25: data_out = top_logit_reg[7:0];
            26: data_out = second_logit_reg[15:8];
            27: data_out = second_logit_reg[7:0];
            // logits, high byte first
            default: data_out = logit_byte_index[0] ? logit_word[7:0] : logit_word[15:8];
        endcase
    end


    always_comb begin
        state_next = state_reg;
        byte_index_next = byte_index_reg;
        host_mac_next = host_mac_reg;
        sequence_number_next = sequence_number_reg;
        class_next = class_reg;
        flags_next = flags_reg;
        feature_count_next = feature_count_reg;
        top_logit_next = top_logit_reg;
        second_logit_next = second_logit_reg;

        valid_out = 1'b0;
        last_out = 1'b0;

        case (state_reg)
            IDLE: begin
                if (decision_valid_in) begin
                    host_mac_next = host_mac_in;
                    sequence_number_next = sequence_number_in;
                    class_next = decision_class_in;
                    flags_next = {7'd0, overflow_in};
                    feature_count_next = {7'd0, feature_count_in};
                    top_logit_next = top_logit_in;
                    second_logit_next = second_logit_in;
                    byte_index_next = '0;
                    state_next = SEND;
                end
            end

            SEND: begin
                valid_out = 1'b1;
                last_out = (byte_index_reg == FRAME_BYTES - 1);

                if (ready_in) begin
                    if (byte_index_reg == FRAME_BYTES - 1) begin
                        byte_index_next = '0;
                        state_next = IDLE;
                    end else begin
                        byte_index_next = byte_index_reg + 1'b1;
                    end
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    // high in the decision clock too, so the parser never starts in between
    assign busy_out = (state_reg != IDLE) || decision_valid_in;

endmodule
