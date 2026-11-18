// Offline candidate integrating byte-addressed DDR fetch, unpack and raw dot.
// Activations are latched with the row descriptor. Memory and arithmetic domain
// must reset together. A shared memory error suppresses all pending publication.
module packed_weight_fetch_dot16_v1 #(
    parameter integer BITS=7, ADDRESS_WIDTH=40
) (
    input logic clk,reset,row_valid,
    output logic row_ready,
    input logic [ADDRESS_WIDTH-1:0] row_address,
    input logic [127:0] activations,
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [15:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,response_error,
    output logic out_valid,
    input logic out_ready,
    output logic signed [19:0] out_sum,
    output logic fault
);
    logic [127:0] active_values,weight_values;
    logic fetch_valid,dot_ready,dot_valid;
    always_ff @(posedge clk) begin
        if(reset) active_values<=0;
        else if(row_valid && row_ready) active_values<=activations;
    end
    packed_weight_fetch16_v1 #(.BITS(BITS),.ADDRESS_WIDTH(ADDRESS_WIDTH)) fetch (
        .clk(clk),.reset(reset),.row_valid(row_valid),.row_ready(row_ready),.row_address(row_address),
        .read_request_valid(read_request_valid),.read_request_ready(read_request_ready),
        .read_request_address(read_request_address),.read_request_beats(read_request_beats),
        .read_valid(read_valid),.read_ready(read_ready),.read_data(read_data),.read_last(read_last),
        .response_error(response_error),.out_valid(fetch_valid),.out_ready(dot_ready),
        .signed_bytes(weight_values),.fault(fault)
    );
    signed_int8_dot16_v1 dot (
        .clk(clk),.reset(reset || fault || response_error),.in_valid(fetch_valid),.in_ready(dot_ready),
        .activations(active_values),.weights(weight_values),.out_valid(dot_valid),
        .out_ready(out_ready),.out_sum(out_sum)
    );
    assign out_valid=dot_valid && !fault && !response_error && !reset;
endmodule
