// Isolated synchronous endpoint. No connection to the qualified encoder yet.
module typed_intent_guard #(
    parameter logic [255:0] CONTRACT = 256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2
) (
    input logic clk, reset, install_session,
    input logic [63:0] session_value,
    input logic start, ack,
    input logic [63:0] request_id,
    input logic [255:0] request_contract,
    input logic [31:0] budget_cycles,
    input logic proposal_valid,
    input logic [63:0] proposal_session, proposal_request_id,
    input logic [255:0] proposal_contract,
    input logic [2:0] proposal_outcome,
    input logic [15:0] proposal_label, proposal_reserved_score,
    // These must come from trusted completion/ownership logic for this epoch.
    // live_quiet must include outstanding AXI and FIFO contents, not telemetry.
    input logic core_complete, core_success, live_quiet,
    input logic [63:0] core_session, core_request_id,
    output logic session_configured,
    output logic [63:0] result_session,
    output wire ready, admitted, active, result_valid, quarantined,
    output wire [63:0] result_request_id,
    output wire [255:0] result_contract,
    output wire [2:0] result_outcome,
    output wire [15:0] result_label, result_reserved_score,
    output wire [31:0] elapsed
);
    // Preserve bounded reduction boundaries rather than one long carry chain.
    // Every one of the 256 bits is checked combinationally on the SAME edge.
    // No register, bypass, delayed permission or truncated digest is introduced.
    (* keep = "true" *) wire [31:0] request_contract_byte_equal;
    (* keep = "true" *) wire [3:0] request_contract_group_equal;
    for(genvar b=0;b<32;b++) begin : gen_contract_bytes
        assign request_contract_byte_equal[b] = request_contract[8*b+:8] == CONTRACT[8*b+:8];
    end
    for(genvar g=0;g<4;g++) begin : gen_contract_groups
        assign request_contract_group_equal[g] = &request_contract_byte_equal[8*g+:8];
    end
    wire request_contract_ok = &request_contract_group_equal;

    wire gate_ready,gate_admitted;
    logic [63:0] last_seen_request;
    // Keep the sequence decision independent of profile-valid control fan-in.
    (* keep = "true" *) wire request_is_new = request_id > last_seen_request;
    wire successful_epoch = core_complete && core_success &&
        core_session==result_session && core_request_id==result_request_id;
    wire [2:0] checked_outcome =
        (proposal_reserved_score!=0 ||
         (proposal_outcome==1 && !successful_epoch)) ? 3'd4 : proposal_outcome;
    assign ready = gate_ready && session_configured;
    // Only this validated pulse may launch the encoder / transfer ownership.
    // Invalid START frames produce a terminal INVALID without a launch.
    assign admitted = gate_admitted && budget_cycles!=0 &&
        request_is_new && request_contract_ok;
    always_ff @(posedge clk) begin
        if(reset) begin session_configured<=0;result_session<=0;last_seen_request<=0;end
        else begin
            if(install_session && !session_configured && session_value!=0) begin
                session_configured<=1;result_session<=session_value;
            end
            // Consume increasing identities even when the frame is INVALID.
            if(gate_admitted && request_is_new) last_seen_request<=request_id;
        end
    end
    typed_publication_gate #(.LABEL_COUNT(18),.MIN_CONFIDENCE(0)) gate (
        .clk(clk),.reset(reset),.start(start && session_configured),.ack(ack),
        .core_quiescent(live_quiet),.request_id(request_id),
        .contract_sha256(request_contract_ok ? CONTRACT : 256'd0),
        .budget_cycles(request_is_new ? budget_cycles : 32'd0),
        .proposal_valid(proposal_valid && proposal_session==result_session),
        .proposal_request_id(proposal_request_id),.proposal_contract_sha256(proposal_contract),
        .proposal_outcome(checked_outcome),.proposal_label(proposal_label),.proposal_confidence(16'd0),
        .ready(gate_ready),.admitted(gate_admitted),.active(active),.result_valid(result_valid),
        .quarantined(quarantined),.result_request_id(result_request_id),
        .result_contract_sha256(result_contract),.result_outcome(result_outcome),
        .result_label(result_label),.result_confidence(result_reserved_score),.elapsed(elapsed)
    );
endmodule
