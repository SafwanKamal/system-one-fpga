// Completion and ownership adapter. Does not control the encoder datapath.
module typed_epoch_tracker (
    input logic clk, reset, admitted, retired,
    input logic [63:0] admission_session, admission_request_id,
    input logic run_done, busy, memory_drained, memory_error,
    input logic [7:0] run_status,
    output logic owned, complete,
    output wire success,
    output logic fault_seen, done_seen,
    output logic [63:0] session, request_id
);
    assign success=complete && !fault_seen && !memory_error;
    always_ff @(posedge clk) begin
        if(reset) begin
            owned<=0;complete<=0;fault_seen<=0;done_seen<=0;session<=0;request_id<=0;
        end else if(admitted) begin
            owned<=1;complete<=0;fault_seen<=0;done_seen<=0;
            session<=admission_session;request_id<=admission_request_id;
        end else if(owned) begin
            if(memory_error) fault_seen<=1;
            if(run_done) begin
                done_seen<=1;
                if(run_status!=0) fault_seen<=1;
            end
            // Observe one complete drain edge after the encoder's done pulse.
            if(done_seen && !busy && memory_drained) complete<=1;
            // Only the endpoint's legal ACK may retire ownership.
            if(retired && complete && !busy && memory_drained && !fault_seen && !memory_error) begin
                owned<=0;complete<=0;done_seen<=0;
            end
        end
    end
endmodule
