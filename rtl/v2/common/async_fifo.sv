// Dual-clock FIFO (Gray-coded pointers, two-flop synchronisers), first-word
// fall-through on the read side.
//
// For the crossings between the 50 MHz Ethernet clock and the memory controller's
// ui_clk. DEPTH must be a power of two. `write_count` (write side) and `empty` /
// `full` are conservative: a pointer seen through the synchroniser is two clocks
// old, so the FIFO can look fuller or emptier than it is, never the other way.
//
// Both resets must be asserted together at start-up (they may be released at
// different times; each side only resets its own pointers).
module async_fifo #(
    parameter integer WIDTH = 128,
    parameter integer DEPTH = 64
) (
    input logic write_clk,
    input logic write_reset,
    input logic write_enable,
    input logic [WIDTH-1:0] write_data,
    output logic full,
    output logic [$clog2(DEPTH):0] write_count,

    input logic read_clk,
    input logic read_reset,
    input logic read_enable,
    output logic [WIDTH-1:0] read_data,
    output logic empty
);

    localparam integer ADDRESS_WIDTH = $clog2(DEPTH);

    logic [WIDTH-1:0] memory [0:DEPTH-1];

    logic [ADDRESS_WIDTH:0] write_binary_reg, write_gray_reg;
    logic [ADDRESS_WIDTH:0] read_binary_reg, read_gray_reg;
    (* ASYNC_REG = "TRUE" *) logic [ADDRESS_WIDTH:0] read_gray_sync1_reg, read_gray_sync2_reg;
    (* ASYNC_REG = "TRUE" *) logic [ADDRESS_WIDTH:0] write_gray_sync1_reg, write_gray_sync2_reg;

    wire do_write = write_enable && !full;
    wire do_read = read_enable && !empty;
    wire [ADDRESS_WIDTH:0] write_binary_next = write_binary_reg + (do_write ? 1'b1 : 1'b0);
    wire [ADDRESS_WIDTH:0] read_binary_next = read_binary_reg + (do_read ? 1'b1 : 1'b0);


    function automatic logic [ADDRESS_WIDTH:0] to_binary(input logic [ADDRESS_WIDTH:0] gray);
        logic [ADDRESS_WIDTH:0] b;
        b[ADDRESS_WIDTH] = gray[ADDRESS_WIDTH];
        for (int i = ADDRESS_WIDTH - 1; i >= 0; i--) begin
            b[i] = b[i + 1] ^ gray[i];
        end
        return b;
    endfunction


    // storage: written on the write clock, read asynchronously (distributed RAM)
    always_ff @(posedge write_clk) begin
        if (do_write) begin
            memory[write_binary_reg[ADDRESS_WIDTH-1:0]] <= write_data;
        end
    end

    assign read_data = memory[read_binary_reg[ADDRESS_WIDTH-1:0]];


    always_ff @(posedge write_clk or posedge write_reset) begin
        if (write_reset) begin
            write_binary_reg <= '0;
            write_gray_reg <= '0;
            read_gray_sync1_reg <= '0;
            read_gray_sync2_reg <= '0;
        end else begin
            write_binary_reg <= write_binary_next;
            write_gray_reg <= write_binary_next ^ (write_binary_next >> 1);
            read_gray_sync1_reg <= read_gray_reg;
            read_gray_sync2_reg <= read_gray_sync1_reg;
        end
    end

    always_ff @(posedge read_clk or posedge read_reset) begin
        if (read_reset) begin
            read_binary_reg <= '0;
            read_gray_reg <= '0;
            write_gray_sync1_reg <= '0;
            write_gray_sync2_reg <= '0;
        end else begin
            read_binary_reg <= read_binary_next;
            read_gray_reg <= read_binary_next ^ (read_binary_next >> 1);
            write_gray_sync1_reg <= write_gray_reg;
            write_gray_sync2_reg <= write_gray_sync1_reg;
        end
    end

    assign write_count = write_binary_reg - to_binary(read_gray_sync2_reg);
    assign full = (write_count == DEPTH[ADDRESS_WIDTH:0]);
    assign empty = (read_gray_reg == write_gray_sync2_reg);

endmodule
