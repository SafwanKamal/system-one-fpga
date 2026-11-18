// Offline candidate: byte-addressed packed row -> established v2 memory port.
// One request in flight, 128-bit aligned reads, 16 signed codes per result.
// Memory port owns AXI burst splitting (including 4 KiB boundaries).
// The entire memory transaction domain must reset together; resetting only this
// adapter cannot cancel an already accepted AXI read. Sticky fault requires reset.
module packed_weight_fetch16_v1 #(
    parameter integer BITS=7,
    parameter integer ADDRESS_WIDTH=40
) (
    input logic clk, reset,
    input logic row_valid,
    output logic row_ready,
    input logic [ADDRESS_WIDTH-1:0] row_address,
    output logic read_request_valid,
    input logic read_request_ready,
    output logic [ADDRESS_WIDTH-1:0] read_request_address,
    output logic [15:0] read_request_beats,
    input logic read_valid,
    output logic read_ready,
    input logic [127:0] read_data,
    input logic read_last,
    input logic response_error,
    output logic out_valid,
    input logic out_ready,
    output logic [127:0] signed_bytes,
    output logic fault
);
    localparam integer ROW_BYTES=2*BITS;
    typedef enum logic [2:0] {IDLE,ISSUE,FIRST,SECOND,UNPACK,DELIVER,FAILED} state_t;
    state_t state;
    logic [3:0] offset;
    logic [255:0] gathered;
    logic unpack_ready, unpack_valid;
    wire [ADDRESS_WIDTH:0] last_address={1'b0,row_address}+ROW_BYTES-1;
    wire [255:0] shifted=gathered >> (offset*8);
    assign row_ready=!reset && state==IDLE && !fault && !response_error;
    assign read_request_valid=!reset && state==ISSUE && !fault && !response_error;
    assign read_ready=!reset && (state==FIRST || state==SECOND) && !fault && !response_error;
    assign unpack_valid=!reset && state==UNPACK && !fault && !response_error;
    // Gate publication immediately if the shared port reports an error.
    wire unpack_out_valid;
    assign out_valid=unpack_out_valid && !fault && !response_error && !reset;
    packed_weight_row16 #(.BITS(BITS)) unpack (
        .clk(clk), .reset(reset || fault || response_error),
        .in_valid(unpack_valid), .in_ready(unpack_ready), .packed_row(shifted[127:0]),
        .out_valid(unpack_out_valid), .out_ready(out_ready && !fault && !response_error),
        .signed_bytes(signed_bytes)
    );
    always_ff @(posedge clk) begin
        if(reset) begin
            state<=IDLE; fault<=0; offset<=0; gathered<=0;
            read_request_address<=0; read_request_beats<=0;
        end else if(response_error) begin
            fault<=1; state<=FAILED;
        end else begin
            case(state)
                IDLE: if(row_valid && row_ready) begin
                    if(last_address[ADDRESS_WIDTH]) begin
                        fault<=1; state<=FAILED;
                    end else begin
                        offset<=row_address[3:0];
                        read_request_address<={row_address[ADDRESS_WIDTH-1:4],4'b0};
                        read_request_beats<=({1'b0,row_address[3:0]}+ROW_BYTES>16)?2:1;
                        state<=ISSUE;
                    end
                end
                ISSUE: if(read_request_valid && read_request_ready) state<=FIRST;
                FIRST: if(read_valid && read_ready) begin
                    if(read_last != (read_request_beats==1)) begin
                        fault<=1; state<=FAILED;
                    end else begin
                        gathered<={128'b0,read_data};
                        state<=(read_request_beats==1)?UNPACK:SECOND;
                    end
                end
                SECOND: if(read_valid && read_ready) begin
                    if(!read_last) begin fault<=1; state<=FAILED; end
                    else begin gathered[255:128]<=read_data; state<=UNPACK; end
                end
                UNPACK: if(unpack_ready) state<=DELIVER;
                DELIVER: if(out_valid && out_ready) state<=IDLE;
                default: state<=FAILED;
            endcase
        end
    end
`ifndef SYNTHESIS
    initial begin
        if(BITS!=6 && BITS!=7 && BITS!=8) $fatal(1,"BITS must be 6, 7 or 8");
        if(ADDRESS_WIDTH<5) $fatal(1,"ADDRESS_WIDTH must be >=5");
    end
`endif
endmodule
