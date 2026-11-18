// Standalone prototype: authoritative finite-enum result register, independent
// of DDR and ARM progress. NOT integrated into any qualified/candidate bitstream.
// Trusted admission supplies contract identity (model/schema/build/environment).
module typed_publication_gate #(
    parameter integer LABEL_COUNT=8,
    parameter logic [15:0] MIN_CONFIDENCE=0
) (
    input logic clk, reset, start, ack, core_quiescent,
    input logic [63:0] request_id,
    input logic [255:0] contract_sha256,
    input logic [31:0] budget_cycles,
    input logic proposal_valid,
    input logic [63:0] proposal_request_id,
    input logic [255:0] proposal_contract_sha256,
    input logic [2:0] proposal_outcome,
    input logic [15:0] proposal_label, proposal_confidence,
    output logic ready, admitted, active, result_valid, quarantined,
    output logic [63:0] result_request_id,
    output logic [255:0] result_contract_sha256,
    output logic [2:0] result_outcome,
    output logic [15:0] result_label, result_confidence,
    output logic [31:0] elapsed
);
    localparam logic [2:0] ACCEPTED=1, CLARIFY=2, ABSTAIN=3,
        HARDWARE_FAULT=4, DEADLINE_EXCEEDED=5, INVALID_INPUT=6;
    logic [63:0] last_request;
    logic [31:0] limit_reg;
    // Same boolean checks, same edge. Preserve individual decision boundaries
    // so an unrelated valid flag need not propagate through a wide comparator.
    (* keep = "true" *) wire budget_is_zero = budget_cycles == 0;
    (* keep = "true" *) wire request_not_new = request_id <= last_request;
    (* keep = "true" *) wire contract_is_empty = contract_sha256 == 0;
    wire matching = proposal_valid && proposal_request_id==result_request_id
                    && proposal_contract_sha256==result_contract_sha256;
    assign ready = !active && !result_valid && !quarantined && core_quiescent;
    assign admitted = start && ready;
    initial assert(LABEL_COUNT>0 && LABEL_COUNT<=65536);
    always_ff @(posedge clk) begin
        if(reset) begin
            active<=0;result_valid<=0;quarantined<=0;elapsed<=0;limit_reg<=0;
            result_request_id<=0;result_contract_sha256<=0;last_request<=0;
            result_outcome<=0;result_label<=0;result_confidence<=0;
        end else begin
            if(ack && result_valid && !quarantined) begin
                result_valid<=0;result_outcome<=0;
                result_label<=0;result_confidence<=0;
            end
            if(admitted) begin
                result_request_id<=request_id;result_contract_sha256<=contract_sha256;
                result_label<=0;result_confidence<=0;elapsed<=0;
                limit_reg<=budget_cycles;
                if(budget_is_zero || request_not_new || contract_is_empty) begin
                    result_outcome<=INVALID_INPUT;result_valid<=1;
                end else begin
                    last_request<=request_id;active<=1;
                end
            end else if(active) begin
                elapsed<=elapsed+1'b1;
                if(matching) begin
                    active<=0;result_valid<=1;
                    // Failure variants always carry canonical empty payload.
                    if(!core_quiescent || proposal_outcome<ACCEPTED || proposal_outcome>HARDWARE_FAULT
                       || (proposal_outcome==ACCEPTED && int'(proposal_label)>=LABEL_COUNT)) begin
                        result_outcome<=HARDWARE_FAULT;quarantined<=1;
                    end else if(proposal_outcome==ACCEPTED) begin
                        if(proposal_confidence<MIN_CONFIDENCE) result_outcome<=ABSTAIN;
                        else begin
                            result_outcome<=ACCEPTED;
                            result_label<=proposal_label;result_confidence<=proposal_confidence;
                        end
                    end else begin
                        result_outcome<=proposal_outcome;
                        if(proposal_outcome==HARDWARE_FAULT) quarantined<=1;
                    end
                end else if(elapsed==limit_reg-1'b1) begin
                    active<=0;result_valid<=1;result_outcome<=DEADLINE_EXCEEDED;
                    quarantined<=1;
                end
            end
        end
    end
endmodule
