// Single-clock FIFO with first-word fall-through output.
//
// Used between the memory controller and anything that reads weights: the
// controller returns read data whether or not the consumer is ready, so the
// requester reserves FIFO space before it issues a read (see mig_memory_port.sv)
// and this FIFO absorbs the burst.
//
// DEPTH must be a power of two. `count` is the number of words stored, which the
// requester compares against DEPTH to know how many reads may be in flight.
module sync_fifo #(
    parameter integer WIDTH = 128,
    parameter integer DEPTH = 64
) (
    input logic clk,
    input logic reset,

    input logic write_enable,
    input logic [WIDTH-1:0] write_data,
    output logic full,

    input logic read_enable,
    output logic [WIDTH-1:0] read_data,
    output logic empty,

    output logic [$clog2(DEPTH):0] count
);

    localparam integer ADDRESS_WIDTH = $clog2(DEPTH);

    logic [WIDTH-1:0] memory [0:DEPTH-1];
    logic [ADDRESS_WIDTH:0] write_pointer_reg, write_pointer_next;
    logic [ADDRESS_WIDTH:0] read_pointer_reg, read_pointer_next;

    wire do_write = write_enable && !full;
    wire do_read = read_enable && !empty;


    // Separate clocked block with no reset, so the storage maps to distributed or block RAM
    always_ff @(posedge clk) begin
        if (do_write) begin
            memory[write_pointer_reg[ADDRESS_WIDTH-1:0]] <= write_data;
        end
    end


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            write_pointer_reg <= '0;
            read_pointer_reg <= '0;
        end else begin
            write_pointer_reg <= write_pointer_next;
            read_pointer_reg <= read_pointer_next;
        end
    end


    always_comb begin
        write_pointer_next = write_pointer_reg + (do_write ? 1'b1 : 1'b0);
        read_pointer_next = read_pointer_reg + (do_read ? 1'b1 : 1'b0);
    end

    assign count = write_pointer_reg - read_pointer_reg;
    assign full = (count == DEPTH[ADDRESS_WIDTH:0]);
    assign empty = (count == '0);
    assign read_data = memory[read_pointer_reg[ADDRESS_WIDTH-1:0]];

endmodule
