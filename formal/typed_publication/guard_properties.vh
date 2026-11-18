    reg f_past_valid=0;
    always @(posedge clk) begin
        f_past_valid<=1;
        if(!f_past_valid) assume(reset);
        if(f_past_valid && !$past(reset)) begin
            if(session_configured) assert(result_session!=0);
            if(active) begin
                assert(session_configured && result_contract==CONTRACT);
                assert(result_request_id!=0 && result_request_id==last_seen_request);
                assert(!result_valid && result_label==0 && result_reserved_score==0);
            end
            if(result_valid) begin
                assert(result_reserved_score==0);
                if(result_outcome==1) begin
                    assert(result_label<18 && result_contract==CONTRACT);
                    assert(result_request_id!=0 && result_request_id==last_seen_request);
                end else assert(result_label==0);
            end
            if($past(session_configured)) begin
                assert(session_configured && result_session==$past(result_session));
            end
            if($past(gate_admitted && request_id>last_seen_request))
                assert(last_seen_request==$past(request_id));
            else assert(last_seen_request==$past(last_seen_request));
            if($past(admitted)) begin
                assert(active && !result_valid && elapsed==0);
                assert(result_request_id==$past(request_id));
                assert(result_contract==CONTRACT);
            end
            if($past(active && proposal_valid && proposal_session==result_session &&
                     proposal_request_id==result_request_id && proposal_contract==result_contract &&
                     proposal_outcome==1)) begin
                assert(result_valid && !active);
                if($past(!successful_epoch || !live_quiet || proposal_reserved_score!=0 || proposal_label>=18))
                    assert(result_outcome==4 && quarantined && result_label==0);
                else assert(result_outcome==1 && result_label==$past(proposal_label));
            end
        end
    end
