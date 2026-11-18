// Formal environment for the original standalone gate. No assumed ARM progress.
module gate_properties(input clk);
    (* anyseq *) reg reset,start,ack,core_quiescent,proposal_valid;
    (* anyseq *) reg [63:0] request_id,proposal_request_id;
    (* anyseq *) reg [255:0] contract_sha256,proposal_contract_sha256;
    (* anyseq *) reg [31:0] budget_cycles;
    (* anyseq *) reg [2:0] proposal_outcome;
    (* anyseq *) reg [15:0] proposal_label,proposal_confidence;
    wire ready,admitted,active,result_valid,quarantined;
    wire [63:0] result_request_id;
    wire [255:0] result_contract_sha256;
    wire [2:0] result_outcome;
    wire [15:0] result_label,result_confidence;
    wire [31:0] elapsed;
    typed_publication_gate #(.LABEL_COUNT(18),.MIN_CONFIDENCE(0)) dut(.*);
    reg past_valid=0;
    reg [31:0] captured_budget;
    always @(posedge clk) begin
        past_valid<=1;
        if(!past_valid) assume(reset);
        if(admitted) captured_budget<=budget_cycles;
        if(past_valid && !$past(reset)) begin
            assert(!(active && result_valid));
            if(active) begin
                assert(captured_budget>0);
                assert(elapsed<captured_budget);
            end
            if(result_valid) begin
                assert(result_outcome>=1 && result_outcome<=6);
                if(result_outcome==1) begin
                    assert(result_label<18);
                    assert(result_request_id>0 && result_contract_sha256!=0);
                    assert(!quarantined);
                end else begin
                    assert(result_label==0 && result_confidence==0);
                end
            end
            if($past(active)) begin
                assert(elapsed==$past(elapsed)+32'd1);
                assert(active || result_valid);
                assert(result_request_id==$past(result_request_id));
                assert(result_contract_sha256==$past(result_contract_sha256));
                assert(captured_budget==$past(captured_budget));
                if($past(elapsed)==$past(captured_budget)-32'd1)
                    assert(result_valid && !active);
            end
            if($past(result_valid && !(ack && !quarantined))) begin
                assert(result_valid);
                assert({result_request_id,result_contract_sha256,result_outcome,
                        result_label,result_confidence,elapsed,quarantined} ==
                       $past({result_request_id,result_contract_sha256,result_outcome,
                        result_label,result_confidence,elapsed,quarantined}));
            end
        end
    end
endmodule
