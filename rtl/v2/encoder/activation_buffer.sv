// On-chip activation buffer: DEPTH words of 128 bits, one read port with one clock
// of latency and one write port with byte enables (simple dual-port block RAM).
//
// Layout used by every encoder engine: token t occupies ROW_WORDS consecutive words
// starting at word t * ROW_WORDS; element e of an INT8 buffer is byte e of the row,
// element e of an INT16 buffer is bytes 2e (low) and 2e + 1 (high). The byte at the
// lowest address is bits [7:0] of a word, as in external memory.
//
// DEPTH may be a power of two or the sum of two (3072 = 2048 + 1024 for MiniLM's 384
// wide rows): the buffer is then two RAMs, so the tools never round a 3K-deep memory
// up to 4K of block RAM.
module activation_buffer #(
    parameter integer DEPTH = 4096,
    parameter integer ADDRESS_WIDTH = $clog2(DEPTH)
) (
    input logic clk,

    input logic [ADDRESS_WIDTH-1:0] read_address,
    output logic [127:0] read_data,

    input logic write_enable,
    input logic [ADDRESS_WIDTH-1:0] write_address,
    input logic [127:0] write_data,
    input logic [15:0] write_byte_enable
);

    localparam integer BIG = 1 << ($clog2(DEPTH + 1) - 1);  // largest power of two <= DEPTH
    localparam integer SMALL = DEPTH - BIG;                  // 0 or a power of two

    logic [127:0] big_memory [0:BIG-1];
    logic [127:0] big_data;

    always_ff @(posedge clk) begin
        big_data <= big_memory[read_address[$clog2(BIG)-1:0]];
        if (write_enable && (write_address < BIG)) begin
            for (int b = 0; b < 16; b++) begin
                if (write_byte_enable[b]) begin
                    big_memory[write_address[$clog2(BIG)-1:0]][8*b +: 8] <= write_data[8*b +: 8];
                end
            end
        end
    end

    if (SMALL == 0) begin : gen_single
        assign read_data = big_data;
    end else begin : gen_split
        localparam integer SMALL_BITS = (SMALL > 1) ? $clog2(SMALL) : 1;
        logic [127:0] small_memory [0:SMALL-1];
        logic [127:0] small_data;
        logic read_small;
        logic [ADDRESS_WIDTH-1:0] small_read, small_write;

        assign small_read = read_address - ADDRESS_WIDTH'(BIG);
        assign small_write = write_address - ADDRESS_WIDTH'(BIG);

        always_ff @(posedge clk) begin
            read_small <= (read_address >= BIG);
            small_data <= small_memory[small_read[SMALL_BITS-1:0]];
            if (write_enable && (write_address >= BIG)) begin
                for (int b = 0; b < 16; b++) begin
                    if (write_byte_enable[b]) begin
                        small_memory[small_write[SMALL_BITS-1:0]][8*b +: 8] <= write_data[8*b +: 8];
                    end
                end
            end
        end

        assign read_data = read_small ? small_data : big_data;

`ifndef SYNTHESIS
        initial begin
            if ((SMALL & (SMALL - 1)) != 0) $fatal(1, "activation_buffer: DEPTH %0d is not 2^a + 2^b", DEPTH);
        end
`endif
    end

endmodule
