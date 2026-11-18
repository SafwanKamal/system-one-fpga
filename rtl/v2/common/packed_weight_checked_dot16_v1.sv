// Candidate checked descriptor -> DDR fetch -> unpack -> raw signed dot.
// One transaction at a time; rejection produces a completion with out_error
// and no memory request. Runtime fetch fault is fail-stop and needs domain reset.
// No timeout, row-tail activation masking, matrix accumulation or requantization.
module packed_weight_checked_dot16_v1 #(
    parameter integer BITS=7
) (
    input logic clk,reset,in_valid,
    output logic in_ready,
    input logic [39:0] matrix_base,region_base,
    input logic [40:0] region_bytes,
    input logic [31:0] rows,columns,row_index,input_tile,
    input logic [127:0] activations,
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [39:0] read_request_address,
    output logic [15:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,response_error,
    output logic out_valid,
    input logic out_ready,
    output logic signed [19:0] out_sum,
    output logic [3:0] out_error,
    output logic fault
);
    typedef enum logic [1:0] {IDLE,CHECK,RUN,REJECTED} state_t;
    state_t state;
    logic descriptor_ready,descriptor_valid,descriptor_accept;
    logic [39:0] checked_address;
    logic [3:0] checked_error,rejection;
    logic [127:0] saved_activations;
    logic row_valid,row_ready,dot_valid;
    logic signed [19:0] dot_sum;
    assign in_ready=!reset && state==IDLE && descriptor_ready && !fault && !response_error;
    packed_weight_row_descriptor_v1 #(.BITS(BITS)) descriptor (
        .clk(clk),.reset(reset),.in_valid(in_valid && in_ready),.in_ready(descriptor_ready),
        .matrix_base(matrix_base),.region_base(region_base),.region_bytes(region_bytes),
        .rows(rows),.columns(columns),.row_index(row_index),.input_tile(input_tile),
        .out_valid(descriptor_valid),.out_ready(descriptor_accept),
        .row_address(checked_address),.out_error(checked_error)
    );
    assign row_valid=!reset && state==CHECK && descriptor_valid && checked_error==0;
    assign descriptor_accept=state==CHECK && descriptor_valid && (checked_error!=0 || row_ready);
    packed_weight_fetch_dot16_v1 #(.BITS(BITS)) fetch_dot (
        .clk(clk),.reset(reset),.row_valid(row_valid),.row_ready(row_ready),.row_address(checked_address),
        .activations(saved_activations),.read_request_valid(read_request_valid),
        .read_request_ready(read_request_ready),.read_request_address(read_request_address),
        .read_request_beats(read_request_beats),.read_valid(read_valid),.read_ready(read_ready),
        .read_data(read_data),.read_last(read_last),.response_error(response_error),
        .out_valid(dot_valid),.out_ready(out_ready && state==RUN),.out_sum(dot_sum),.fault(fault)
    );
    assign out_valid=!reset && !fault && !response_error &&
                     ((state==RUN && dot_valid) || state==REJECTED);
    assign out_sum=(state==RUN)?dot_sum:20'sd0;
    assign out_error=(state==REJECTED)?rejection:4'b0;
    always_ff @(posedge clk) begin
        if(reset) begin state<=IDLE;rejection<=0;saved_activations<=0;end
        else case(state)
            IDLE: if(in_valid && in_ready) begin saved_activations<=activations;state<=CHECK;end
            CHECK: if(descriptor_accept) begin
                if(checked_error!=0) begin rejection<=checked_error;state<=REJECTED;end
                else state<=RUN;
            end
            RUN: if(out_valid && out_ready) state<=IDLE;
            REJECTED: if(out_valid && out_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
endmodule
