// Reserve FIFO credits before issuing fixed-latency activation reads. Thus AXI
// write backpressure can never overflow the FIFO or change a held output word.
module result_streamer #(
    parameter integer ADDRESS_WIDTH = 15,
    parameter integer READ_LATENCY = 4,
    parameter integer DEPTH = 8
) (
    input logic clk, reset, start,
    input logic [ADDRESS_WIDTH-1:0] first_address,
    input logic [15:0] words,
    output logic [ADDRESS_WIDTH-1:0] read_address,
    input logic [127:0] read_data,
    output logic valid,
    input logic ready,
    output logic [127:0] data
);
    logic [15:0] left;
    logic [READ_LATENCY-1:0] pending;
    logic [$clog2(DEPTH):0] count, inflight;
    logic full, empty, issue;
    assign issue = left != 0 && (32'(count) + 32'(inflight) < DEPTH) && !start;
    assign valid = !empty && !start && !reset;
    stream_fifo_sync_clear #(.WIDTH(128), .DEPTH(DEPTH)) fifo_inst (
        .clk(clk), .reset(reset), .clear(start),
        .write_enable(pending[READ_LATENCY-1] && !start), .write_data(read_data),
        .full(full), .read_enable(valid && ready), .read_data(data), .empty(empty), .count(count)
    );
    always_ff @(posedge clk) begin
        if (reset || start) begin
            pending <= '0;
            inflight <= '0;
            left <= start ? words : 0;
            read_address <= first_address;
        end else begin
            pending <= READ_LATENCY'({pending, issue});
            inflight <= inflight + (issue ? 1'b1 : 1'b0) - (pending[READ_LATENCY-1] ? 1'b1 : 1'b0);
            if (issue) begin
                read_address <= read_address + 1'b1;
                left <= left - 1'b1;
            end
        end
    end
`ifndef SYNTHESIS
    always @(posedge clk) if (!reset && !start && pending[READ_LATENCY-1] && full)
        $fatal(1, "result_streamer credit reservation overflow");
`endif
endmodule
