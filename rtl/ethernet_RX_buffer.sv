// Holds one received frame until its FCS is known, then replays it without the FCS.
//
// The receive-side counterpart of ethernet_TX_buffer, with the same structure: a
// block-RAM frame memory, a collect state, a one-clock prefetch and a transmit state
// with valid/ready. A frame is only replayed if ethernet_RX reports it good, so the
// request parser never sees a byte of a corrupted frame. Bad frames are discarded
// by resetting the byte count.
//
// There is one frame of storage. A frame that starts while the previous one is
// still being replayed is dropped and counted on dropped_out; the host resends on a
// timeout. Requests are small and answered in order, so this is enough for now.
module ethernet_RX_buffer #(
    parameter int ADDR_WIDTH = 11,
    parameter int MAX_FRAME_BYTES = 1518
)(
    input logic clk,
    input logic reset,

    // incoming frame from ethernet_RX
    input  logic frame_start_in,
    input  logic [7:0] data_in,
    input  logic valid_in,
    input  logic frame_end_in,
    input  logic frame_good_in,

    // committed frame, destination MAC through payload (no FCS)
    output logic [7:0] data_out,
    output logic valid_out,
    output logic last_out,
    input  logic ready_in,

    output logic busy_out,
    output logic dropped_out
);

    localparam int BUFFER_DEPTH = 1 << ADDR_WIDTH;
    localparam int FCS_BYTES = 4;

    typedef enum logic [1:0] {
        collect, prefetch, transmit
    } state_t;

    state_t state_reg, state_next;

    logic [ADDR_WIDTH:0] byte_count_reg, byte_count_next;
    logic [ADDR_WIDTH-1:0] read_address_reg, read_address_next;
    logic receiving_reg, receiving_next;
    logic dropped_reg, dropped_next;

    (* ram_style = "block" *)
    logic [7:0] frame_memory [0:BUFFER_DEPTH-1];

    logic memory_write_enable, memory_read_enable;
    logic [ADDR_WIDTH-1:0] memory_write_address;
    logic [ADDR_WIDTH-1:0] memory_read_address;
    logic [7:0] memory_data_reg;

    // clocked memory access without resetting the array or its read output
    // Separate structure to ensure BRAM inference
    always_ff @(posedge clk) begin
        if (memory_write_enable)
            frame_memory[memory_write_address] <= data_in;

        if (memory_read_enable)
            memory_data_reg <= frame_memory[memory_read_address];
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= collect;
            byte_count_reg <= 0;
            read_address_reg <= 0;
            receiving_reg <= 1'b0;
            dropped_reg <= 1'b0;
        end else begin
            state_reg <= state_next;
            byte_count_reg <= byte_count_next;
            read_address_reg <= read_address_next;
            receiving_reg <= receiving_next;
            dropped_reg <= dropped_next;
        end
    end

    always_comb begin
        state_next = state_reg;
        byte_count_next = byte_count_reg;
        read_address_next = read_address_reg;
        receiving_next = receiving_reg;
        dropped_next = 1'b0;

        valid_out = 1'b0;

        memory_write_enable = 1'b0;
        memory_read_enable = 1'b0;
        memory_write_address = byte_count_reg[ADDR_WIDTH-1:0];
        memory_read_address = read_address_reg;

        case (state_reg)
            collect: begin
                // only bytes of a frame whose start was seen here are stored
                if (frame_start_in) begin
                    receiving_next = 1'b1;
                    byte_count_next = 0;
                end else if (receiving_reg && valid_in) begin
                    if (byte_count_reg < MAX_FRAME_BYTES) begin
                        memory_write_enable = 1'b1;
                        byte_count_next = byte_count_reg + 1'b1;
                    end else begin
                        // oversized: stop storing, and the length check below rejects it
                        receiving_next = 1'b0;
                        byte_count_next = 0;
                    end
                end

                if (frame_end_in && receiving_reg) begin
                    receiving_next = 1'b0;

                    // commit only a good frame with at least one byte besides the FCS
                    if (frame_good_in && byte_count_reg > FCS_BYTES) begin
                        byte_count_next = byte_count_reg - FCS_BYTES;
                        read_address_next = 0;
                        state_next = prefetch;
                    end else begin
                        byte_count_next = 0;
                    end
                end
            end

            prefetch: begin
                // the first byte and transmit state become valid at this edge
                memory_read_enable = 1'b1;
                state_next = transmit;
            end

            transmit: begin
                valid_out = 1'b1;

                if (ready_in) begin
                    if ({1'b0, read_address_reg} == byte_count_reg - 1'b1) begin
                        byte_count_next = 0;
                        read_address_next = 0;
                        state_next = collect;
                    end else begin
                        // consume the current byte and fetch the next at once
                        memory_read_enable = 1'b1;
                        memory_read_address = read_address_reg + 1'b1;
                        read_address_next = read_address_reg + 1'b1;
                    end
                end
            end

            default: begin
                byte_count_next = 0;
                read_address_next = 0;
                state_next = collect;
            end
        endcase

        // a frame arriving while one is held cannot be stored
        if (state_reg != collect && frame_start_in) begin
            dropped_next = 1'b1;
        end

        // prevent transfers during reset while leaving the memory unreset
        if (reset) begin
            valid_out = 1'b0;
            memory_write_enable = 1'b0;
            memory_read_enable = 1'b0;
        end
    end

    assign data_out = memory_data_reg;
    assign last_out = (state_reg == transmit) && ({1'b0, read_address_reg} == byte_count_reg - 1'b1);
    assign busy_out = (state_reg != collect);
    assign dropped_out = dropped_reg;

    // synthesis translate_off
    initial begin
        if (MAX_FRAME_BYTES < 1 || MAX_FRAME_BYTES > BUFFER_DEPTH)
            $fatal(1, "MAX_FRAME_BYTES must fit within BUFFER_DEPTH");
    end
    // synthesis translate_on

endmodule
