    reg f_past_valid=0;
    always @(posedge clk) begin
        f_past_valid<=1;
        if(!f_past_valid) assume(reset);
        if(f_past_valid && !$past(reset)) begin
            if(complete) assert(owned && done_seen);
            if(success) assert(complete && !fault_seen && !memory_error);
            if($past(admitted)) begin
                assert(owned && !complete && !done_seen && !fault_seen);
                assert(session==$past(admission_session) && request_id==$past(admission_request_id));
            end else begin
                assert(session==$past(session) && request_id==$past(request_id));
                if($past(owned && (memory_error || (run_done && run_status!=0)))) assert(fault_seen);
                if($past(owned && fault_seen)) assert(owned && fault_seen);
                if(!$past(complete) && complete) begin
                    assert($past(owned && done_seen && !busy && memory_drained));
                end
                if($past(owned && retired && complete && !busy && memory_drained && !fault_seen && !memory_error))
                    assert(!owned && !complete && !done_seen);
                if($past(owned && retired && (!complete || busy || !memory_drained || fault_seen || memory_error)))
                    assert(owned);
            end
        end
    end
