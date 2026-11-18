// Experimental SYS3 operation -> serial relative descriptors. The complete
// operation is validated before any descriptor is emitted; configuration is
// frozen across every chunk. Downstream retirement must be ordered (one chunk
// outstanding). A fault stops issuance; completed_bytes excludes that chunk.
module relative_read_chunker #(
    parameter integer BEATS_WIDTH = 16
) (
    input logic clk, reset,
    input logic operation_valid,
    output logic operation_ready,
    input logic [39:0] model_base,
    input logic [32:0] model_bytes,
    input logic [31:0] operation_offset,
    input logic [32:0] operation_bytes,
    output logic descriptor_valid,
    input logic descriptor_ready,
    output logic [39:0] descriptor_model_base,
    output logic [32:0] descriptor_model_bytes,
    output logic [31:0] descriptor_offset,
    output logic [32:0] descriptor_bytes,
    input logic completion_valid,
    output logic completion_ready,
    input logic [1:0] completion_code,
    output logic done_valid,
    input logic done_ready,
    output logic [1:0] done_code,
    output logic [32:0] completed_bytes
);
    localparam logic [32:0] MAX_BYTES = 33'(((64'd1<<BEATS_WIDTH)-1)*16);
    typedef enum logic [2:0] {IDLE, VALIDATE, ISSUE, WAIT_RETIRE, DONE} state_t;
    state_t state;
    logic checker_ready,checked_valid,checked_error;
    logic [39:0] checked_address;
    logic [32:0] checked_bytes,remaining,cursor;
    model_address_window whole_operation (
        .clk,.reset,.model_base,.model_bytes,
        .in_valid(operation_valid && operation_ready),.in_ready(checker_ready),
        .offset(operation_offset),.bytes(operation_bytes),.out_valid(checked_valid),
        .out_ready(state==VALIDATE && !reset),.address(checked_address),
        .length(checked_bytes),.out_error(checked_error));
    assign operation_ready = !reset && state==IDLE && checker_ready;
    assign descriptor_valid = !reset && state==ISSUE;
    assign descriptor_offset = cursor[31:0];
    assign descriptor_bytes = remaining > MAX_BYTES ? MAX_BYTES : remaining;
    assign completion_ready = !reset && state==WAIT_RETIRE;
    assign done_valid = !reset && state==DONE;
    always_ff @(posedge clk) begin
        if(reset) begin
            state<=IDLE;remaining<=0;cursor<=0;completed_bytes<=0;done_code<=0;
            descriptor_model_base<=0;descriptor_model_bytes<=0;
        end else case(state)
            IDLE: if(operation_valid && operation_ready) begin
                descriptor_model_base<=model_base;descriptor_model_bytes<=model_bytes;
                cursor<={1'b0,operation_offset};remaining<=operation_bytes;
                completed_bytes<=0;done_code<=0;state<=VALIDATE;
            end
            VALIDATE: if(checked_valid) begin
                if(checked_error) begin done_code<=1;state<=DONE;end
                else state<=ISSUE;
            end
            ISSUE: if(descriptor_ready) state<=WAIT_RETIRE;
            WAIT_RETIRE: if(completion_valid) begin
                if(completion_code!=0) begin done_code<=completion_code;state<=DONE;end
                else begin
                    completed_bytes<=completed_bytes+descriptor_bytes;
                    cursor<=cursor+descriptor_bytes;
                    remaining<=remaining-descriptor_bytes;
                    state<=remaining==descriptor_bytes ? DONE : ISSUE;
                end
            end
            DONE: if(done_ready) state<=IDLE;
            default: begin done_code<=3;state<=DONE;end
        endcase
    end
`ifndef SYNTHESIS
    always @(posedge clk) if(!reset && descriptor_valid &&
        (cursor[32] || descriptor_bytes==0 || descriptor_bytes[3:0]!=0))
        $fatal(1,"Chunk descriptor wrapped/truncated");
    initial if(BEATS_WIDTH<1 || BEATS_WIDTH>28)
        $fatal(1,"Chunk beat width must fit33-bit byte count");
`endif
endmodule
