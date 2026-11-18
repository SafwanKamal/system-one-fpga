// Experimental FWFT FIFO with registered full/empty flags computed from next
// pointers. Same acceptance/latency semantics as sync_fifo, including rejecting
// writes at full even during a simultaneous read. No extra interface cycle.
module sync_fifo_registered_flags #(
    parameter integer WIDTH = 128,
    parameter integer DEPTH = 64
) (
    input logic clk, reset,
    input logic write_enable,
    input logic [WIDTH-1:0] write_data,
    output logic full,
    input logic read_enable,
    output logic [WIDTH-1:0] read_data,
    output logic empty,
    output logic [$clog2(DEPTH):0] count
);
    localparam integer AW = $clog2(DEPTH);
    logic [WIDTH-1:0] memory [0:DEPTH-1];
    logic [AW:0] wp, rp, wn, rn;
    logic do_write, do_read;
    assign do_write = write_enable && !full;
    assign do_read = read_enable && !empty;
    assign wn = wp + (do_write ? (AW+1)'(1) : (AW+1)'(0));
    assign rn = rp + (do_read ? (AW+1)'(1) : (AW+1)'(0));
    assign count = wp-rp;
    assign read_data = memory[rp[AW-1:0]];
    always_ff @(posedge clk)
        if (do_write) memory[wp[AW-1:0]] <= write_data;
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            wp <= 0; rp <= 0; full <= 0; empty <= 1;
        end else begin
            wp <= wn; rp <= rn;
            full <= wn == {~rn[AW],rn[AW-1:0]};
            empty <= wn == rn;
        end
    end
    initial if (DEPTH < 2 || (DEPTH & (DEPTH-1)) != 0)
        $fatal(1,"Registered-flag FIFO needs power-of-two depth >=2");
endmodule
