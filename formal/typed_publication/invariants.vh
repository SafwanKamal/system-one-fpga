    // Included ONLY in a hashed formal-instrumented copy, before endmodule.
    reg f_past_valid=0;
    always @(posedge clk) begin
        f_past_valid<=1;
        if(!f_past_valid) assume(reset);
        if(f_past_valid && !$past(reset)) begin
            assert(!(active && result_valid));
            if(active) begin
                assert(limit_reg>0 && elapsed<limit_reg);
                assert(result_label==0 && result_confidence==0);
                assert(result_request_id>0 && result_request_id==last_request);
                assert(result_contract_sha256!=0 && !quarantined);
            end
            if(quarantined) begin
                assert(result_valid && !active);
                assert(result_outcome==4 || result_outcome==5);
            end
            if(result_valid) begin
                assert(result_outcome>=1 && result_outcome<=6);
                if(result_outcome==1) begin
                    assert(result_label<LABEL_COUNT && result_confidence>=MIN_CONFIDENCE);
                    assert(result_request_id>0 && result_request_id==last_request);
                    assert(result_contract_sha256!=0 && !quarantined);
                end else assert(result_label==0 && result_confidence==0);
            end
            if($past(active)) begin
                assert(elapsed==$past(elapsed)+32'd1);
                assert(active || result_valid);
                assert(limit_reg==$past(limit_reg));
                assert({result_request_id,result_contract_sha256}==
                       $past({result_request_id,result_contract_sha256}));
                if($past(elapsed)==$past(limit_reg)-32'd1) assert(result_valid && !active);
            end
            if($past(admitted)) begin
                assert(elapsed==0);
                if($past(budget_cycles)!=0 && $past(request_id)>$past(last_request) &&
                   $past(contract_sha256)!=0) assert(active && !result_valid);
                else assert(result_valid && result_outcome==6 && !active);
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
