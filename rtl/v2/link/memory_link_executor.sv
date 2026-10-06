// v2 memory link, memory side (memory controller clock): executes the commands the
// parser queued, on the v2 memory port.
//
//   write: request, then the beats from the write-data FIFO; an acknowledgement
//          descriptor is queued once every beat has been accepted
//   read:  request; returned beats go to the read-data FIFO (read_ready follows
//          that FIFO's room, so nothing is lost if the Ethernet side is slow); the
//          descriptor is queued after the last beat, so the responder never has to
//          wait for data in the middle of a frame
//
// Command / descriptor word: {is_read, sequence[31:0], address[31:0], beats[6:0],
// host_mac[47:0]}.
module memory_link_executor #(
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer DATA_WIDTH = 128,
    parameter integer BEATS_WIDTH = 16
) (
    input logic clk,
    input logic reset,

    input logic [119:0] command_in,
    input logic command_empty_in,
    output logic command_pop_out,

    input logic [DATA_WIDTH-1:0] beat_in,
    input logic beat_empty_in,
    output logic beat_pop_out,

    output logic [DATA_WIDTH-1:0] read_beat_out,
    output logic read_beat_push_out,
    input logic read_beat_full_in,

    output logic [119:0] response_out,
    output logic response_push_out,
    input logic response_full_in,

    // v2 memory port
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [BEATS_WIDTH-1:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [DATA_WIDTH-1:0] read_data,
    input logic read_last,

    output logic write_request_valid,
    input logic write_request_ready,
    output logic [ADDRESS_WIDTH-1:0] write_request_address,
    output logic [BEATS_WIDTH-1:0] write_request_beats,
    output logic write_valid,
    input logic write_ready,
    output logic [DATA_WIDTH-1:0] write_data,

    output logic busy_out
);

    typedef enum logic [2:0] {
        IDLE,
        WRITE_REQUEST,
        WRITE_DATA,
        READ_REQUEST,
        READ_DATA,
        RESPOND
    } state_t;

    state_t state_reg, state_next;
    logic [119:0] command_reg, command_next;
    logic [6:0] left_reg, left_next;

    wire is_read = command_reg[119];
    wire [31:0] address = command_reg[86:55];
    wire [6:0] beats = command_reg[54:48];


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            command_reg <= '0;
            left_reg <= '0;
        end else begin
            state_reg <= state_next;
            command_reg <= command_next;
            left_reg <= left_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        command_next = command_reg;
        left_next = left_reg;

        command_pop_out = 1'b0;
        beat_pop_out = 1'b0;
        read_beat_push_out = 1'b0;
        response_push_out = 1'b0;
        read_request_valid = 1'b0;
        write_request_valid = 1'b0;
        write_valid = 1'b0;
        read_ready = 1'b0;

        case (state_reg)
            IDLE: begin
                if (!command_empty_in) begin
                    command_pop_out = 1'b1;
                    command_next = command_in;
                    left_next = command_in[54:48];
                    state_next = command_in[119] ? READ_REQUEST : WRITE_REQUEST;
                end
            end

            WRITE_REQUEST: begin
                write_request_valid = 1'b1;
                if (write_request_ready) begin
                    state_next = WRITE_DATA;
                end
            end

            WRITE_DATA: begin
                write_valid = !beat_empty_in;
                if (write_valid && write_ready) begin
                    beat_pop_out = 1'b1;
                    left_next = left_reg - 1'b1;
                    if (left_reg == 1) begin
                        state_next = RESPOND;
                    end
                end
            end

            READ_REQUEST: begin
                read_request_valid = 1'b1;
                if (read_request_ready) begin
                    state_next = READ_DATA;
                end
            end

            READ_DATA: begin
                read_ready = !read_beat_full_in;
                if (read_valid && read_ready) begin
                    read_beat_push_out = 1'b1;
                    left_next = left_reg - 1'b1;
                    if (left_reg == 1) begin
                        state_next = RESPOND;
                    end
                end
            end

            RESPOND: begin
                if (!response_full_in) begin
                    response_push_out = 1'b1;
                    state_next = IDLE;
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign read_request_address = ADDRESS_WIDTH'(address);
    assign read_request_beats = BEATS_WIDTH'(beats);
    assign write_request_address = ADDRESS_WIDTH'(address);
    assign write_request_beats = BEATS_WIDTH'(beats);
    assign write_data = beat_in;
    assign read_beat_out = read_data;
    assign response_out = command_reg;
    assign busy_out = (state_reg != IDLE);

endmodule
