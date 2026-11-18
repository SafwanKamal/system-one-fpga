    reg p_past_valid=0;
    always @(posedge clk) begin
        p_past_valid<=1;
        if(!p_past_valid) assume(reset);
        if(p_past_valid && !$past(reset)) begin
            if(admitted) begin
                assert(environment_ready && shape_ok && bank[4]!=0);
                assert(admission_tokens>0 && admission_tokens<=128 && admission_count>0);
                assert({1'b0,admission_first}+{1'b0,admission_count}<={1'b0,admission_tokens});
            end
            if($past(admitted)) begin
                assert({owned_tokens,owned_first,owned_count}==
                       $past({admission_tokens,admission_first,admission_count}));
            end else assert({owned_tokens,owned_first,owned_count}==
                            $past({owned_tokens,owned_first,owned_count}));
            if($past(start && !shape_ok)) assert(valid && !active && outcome==6);
        end
    end
