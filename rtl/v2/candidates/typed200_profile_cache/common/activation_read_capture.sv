// Experimental cut between physical activation RAM outputs and the shared
// consumer mux. Adds one cycle over a registered mux; caller must delay its
// aligned physical selector by the same cycle. No reset is needed for data:
// consumers qualify reads using their existing latency/tag pipeline.
module activation_read_capture #(
    parameter integer BUFFERS = 7,
    parameter integer PORTS = 4,
    parameter integer WIDTH = 128,
    parameter integer SELECT_WIDTH = $clog2(BUFFERS)
) (
    input logic clk,
    input logic [WIDTH-1:0] physical_data [0:BUFFERS-1],
    input logic [SELECT_WIDTH-1:0] physical_select [0:PORTS-1],
    output logic [WIDTH-1:0] port_data [0:PORTS-1]
);
    // Preserve the physical cut during isolated synthesis. Placement must
    // establish locality; this attribute alone does not guarantee a short wire.
    for (genvar b = 0; b < BUFFERS; b++) begin : gen_capture
        (* DONT_TOUCH = "TRUE" *) logic [WIDTH-1:0] local_data;
        always_ff @(posedge clk) local_data <= physical_data[b];
    end
    logic [SELECT_WIDTH-1:0] delayed_select [0:PORTS-1];
    logic [WIDTH-1:0] captured_data [0:BUFFERS-1];
    for (genvar b = 0; b < BUFFERS; b++) begin : gen_connect
        assign captured_data[b] = gen_capture[b].local_data;
    end
    always_ff @(posedge clk) begin
        for (int p = 0; p < PORTS; p++) begin
            delayed_select[p] <= physical_select[p];
            // Invalid selectors are deterministic zero, never array OOB.
            port_data[p] <= (delayed_select[p] < BUFFERS)
                ? captured_data[delayed_select[p]] : '0;
        end
    end
endmodule
