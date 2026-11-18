    // Formal-only instrumentation. All external inputs are unconstrained.
    reg f_past_valid=0;
    always @(posedge clk) begin
        f_past_valid<=1;
        if(!f_past_valid) assume(reset);
        if(f_past_valid && !$past(reset)) begin
            if($past(s_bvalid && !s_bready)) begin
                assert(s_bvalid);
                assert(s_bresp==$past(s_bresp));
            end
            if($past(s_rvalid && !s_rready)) begin
                assert(s_rvalid);
                assert({s_rdata,s_rresp}==$past({s_rdata,s_rresp}));
            end
            if($past(s_awvalid && s_awready)) begin
                assert(aw_full && aw==$past(s_awaddr));
            end
            if($past(s_wvalid && s_wready)) begin
                assert(w_full && {wd,ws}==$past({s_wdata,s_wstrb}));
            end
            if($past(execute)) begin
                assert(s_bvalid && !aw_full && !w_full);
            end
            if($past(s_arvalid && s_arready)) begin
                assert(s_rvalid && s_rdata==$past(read_value));
                assert(s_rresp==($past(read_ok) ? 0 : 2));
            end
        end
    end
