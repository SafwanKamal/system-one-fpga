    localparam logic [255:0] CONTRACT=256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2;
    logic hold_b=0,inject_b_error=0,inject_r_error=0;
    logic [63:0] boot_session=1;
    int observed_launches=0,paired_done=0,early_done_with_pending_b=0;
    logic [31:0] reference_encoder_clocks,reference_request_clocks;
    always @(posedge clk) if(reset_n) begin
        if(dut.run_start) observed_launches++;
        assert(dut.run_done==reference_inst.run_done && dut.busy==reference_inst.busy);
        assert({m_araddr,m_arlen,m_arsize,m_arburst,m_arvalid,m_rready,
                m_awaddr,m_awlen,m_awsize,m_awburst,m_awvalid,m_wdata,m_wstrb,m_wlast,m_wvalid,m_bready}===
               {ref_m_araddr,ref_m_arlen,ref_m_arsize,ref_m_arburst,ref_m_arvalid,ref_m_rready,
                ref_m_awaddr,ref_m_awlen,ref_m_awsize,ref_m_awburst,ref_m_awvalid,
                ref_m_wdata,ref_m_wstrb,ref_m_wlast,ref_m_wvalid,ref_m_bready})
            else $fatal(1,"Qualified/candidate AXI trace differs");
        if(dut.run_done) begin
            assert(dut.run_result===reference_inst.run_result);
            reference_encoder_clocks<=reference_inst.run_result[31:0];
            reference_request_clocks<=reference_inst.run_result[63:32];
            paired_done++;
            if(!dut.memory_drained)early_done_with_pending_b++;
        end
        if(dut.core_success)assert(dut.core_complete && !memory_error);
        if(dut.core_complete)assert(dut.epoch_inst.done_seen);
        if(dut.publication_inst.valid && dut.publication_inst.outcome==1) begin
            assert(dut.publication_inst.label<18 && !memory_error && dut.core_complete);
        end
    end
    task provision;
        reset_n=0;hold_b=0;inject_b_error=0;inject_r_error=0;
        repeat(5)@(negedge clk);reset_n=1;boot_session++;
        repeat(3)@(negedge clk);
        axil_write(8'h08,boot_session[31:0]);axil_write(8'h0c,boot_session[63:32]);axil_write(0,1);
    endtask
    task frame(input int id,input int n,input int budget=32'h7fffffff,input int first=0,input int count=-1);
        axil_write(8'h10,32'(id));axil_write(8'h14,0);axil_write(8'h18,32'(budget));
        axil_write(8'h1c,{16'(first),16'(n)});axil_write(8'h78,32'((count==-1)?n:count));
        for(int i=0;i<8;i++)axil_write(8'(32+4*i),CONTRACT[32*i+:32]);
    endtask
    task proposal(input int id,input int label=3,input int tag=1,input bit stale=0);
        axil_write(8'h40,boot_session[31:0]+32'(stale));axil_write(8'h44,boot_session[63:32]);
        axil_write(8'h48,32'(id));axil_write(8'h4c,0);
        for(int i=0;i<8;i++)axil_write(8'(80+4*i),CONTRACT[32*i+:32]);
        axil_write(8'h70,(32'(label)<<16)|32'(tag));axil_write(8'h74,0);
        axil_write(0,4);
    endtask
    task terminal(input int expected);
        logic [31:0] v;
        axil_read(4,v);assert(v[2] && !v[1]);
        axil_read(8'hb0,v);assert(v[2:0]==3'(expected));
        if(expected!=1)assert(v[31:16]==0);
        axil_read(8'hb4,v);assert(v==0);
    endtask
    task wait_complete;
        while(!dut.core_complete)@(negedge clk);
        assert(dut.live_quiet && !dut.busy);
    endtask
    task load_case(input int c,output int fd,output int n,output int hidden,output longint result_address);
        int r;
        longint program_address,ids_address;
        logic [127:0] word;
        fd=$fopen($sformatf("%s/case_%0d.txt",DIR,c),"r");assert(fd!=0);
        r=$fscanf(fd,"%d %d %d %d %d",n,hidden,program_address,ids_address,result_address);
        assert(r==5 && hidden==384 && program_address==1610613760 && ids_address==1645215744 && result_address==1645219840);
        for(int w=0;w<(2*n+15)/16;w++)begin
            r=$fscanf(fd,"%h",word);assert(r==1);
            model_inst.memory[AW'(ids_address+16*w)]=word;
        end
    endtask
    task compare_case(input int fd,input int n,input int hidden,input longint result_address,inout int total);
        int r;
        logic [127:0] word,got;
        for(int w=0;w<n*hidden/16;w++)begin
            r=$fscanf(fd,"%h",word);assert(r==1);
            got=model_inst.memory[AW'(result_address+16*w)];
            assert(got===word)else $fatal(1,"Golden X differs at word %0d",w);
            total++;
        end
        $fclose(fd);
    endtask
    initial begin
        int fd,n,hidden,total,launches_before,r;
        longint result_address;
        logic [31:0] value,ec,rc,age;
        awvalid=0;wvalid=0;bready=0;arvalid=0;rready=0;awaddr=0;araddr=0;wdata=0;
        total=0;
        provision();
        axil_read(8'hc0,value);assert(value==32'h54590201);
        // Every normal case compares every driven AXI cycle and raw completion
        // counters against the qualified source under identical bus responses.
        for(int c=0;c<8;c++)begin
            load_case(c,fd,n,hidden,result_address);
            frame(c+1,n);axil_write(0,2);wait_complete();
            assert(!memory_error && dut.core_success);
            compare_case(fd,n,hidden,result_address,total);
            axil_read(8'hd0,ec);axil_read(8'hd4,rc);
            assert(ec==reference_encoder_clocks && rc==reference_request_clocks)
                else $fatal(1,"Completion counters differ: %0d/%0d vs %0d/%0d",ec,rc,reference_encoder_clocks,reference_request_clocks);
            proposal(c+1);terminal(1);axil_read(8'hb8,age);
            assert(age>rc); // endpoint includes drain + ARM proposal transfer
            axil_write(0,8);assert(!dut.owned);
            $display("MATCH case %0d T%0d: every output/AXI cycle and core/request counts %0d/%0d; publication age %0d",c,n,ec,rc,age);
        end
        // Delay final B past raw run_done. Completion must remain unavailable.
        provision();load_case(0,fd,n,hidden,result_address);hold_b=1;
        frame(1,n);axil_write(0,2);
        while(!dut.done_seen)@(negedge clk);
        repeat(20)begin @(negedge clk);assert(!dut.core_complete && !dut.live_quiet);end
        assert(!dut.busy && !dut.memory_drained && !memory_error);
        hold_b=0;wait_complete();compare_case(fd,n,hidden,result_address,total);
        proposal(1);terminal(1);axil_write(0,8);
        // An early Accepted proposal while a final B is pending fails closed.
        provision();load_case(0,fd,n,hidden,result_address);hold_b=1;
        frame(1,n);axil_write(0,2);while(!dut.done_seen)@(negedge clk);
        proposal(1);terminal(4);assert(dut.quarantined && dut.owned);
        hold_b=0;wait_complete();terminal(4);compare_case(fd,n,hidden,result_address,total);
        // BRESP error after raw completion is retained and prevents acceptance.
        provision();load_case(0,fd,n,hidden,result_address);hold_b=1;
        frame(1,n);axil_write(0,2);while(!dut.done_seen)@(negedge clk);
        inject_b_error=1;hold_b=0;wait_complete();
        assert(memory_error && !dut.core_success && dut.fault_seen);
        proposal(1);terminal(4);compare_case(fd,n,hidden,result_address,total);
        // RRESP error: returned data may look correct, but typed success is forbidden.
        provision();load_case(0,fd,n,hidden,result_address);inject_r_error=1;
        frame(1,n);axil_write(0,2);wait_complete();assert(memory_error && !dut.core_success);
        proposal(1);terminal(4);compare_case(fd,n,hidden,result_address,total);
        // PL deadline expires while final B and ARM are stalled. Late B cannot recover.
        provision();load_case(0,fd,n,hidden,result_address);hold_b=1;
        frame(1,n,3000000);axil_write(0,2);while(!dut.done_seen)@(negedge clk);
        while(!dut.terminal_valid)@(negedge clk);terminal(5);
        axil_read(8'hb8,age);assert(age==3000000);
        launches_before=observed_launches;
        hold_b=0;wait_complete();proposal(1);terminal(5);
        frame(2,n);axil_write(0,2);assert(observed_launches==launches_before && dut.owned);
        compare_case(fd,n,hidden,result_address,total);
        // Stale session proposal is ignored until the exact deadline.
        provision();load_case(0,fd,n,hidden,result_address);
        frame(1,n,3000000);axil_write(0,2);wait_complete();proposal(1,3,1,1);
        while(!dut.terminal_valid)@(negedge clk);terminal(5);
        compare_case(fd,n,hidden,result_address,total);
        // Malformed shape is terminal INVALID, never a core launch.
        provision();launches_before=observed_launches;
        frame(1,0);axil_write(0,2);terminal(6);assert(observed_launches==launches_before);axil_write(0,8);
        frame(2,129);axil_write(0,2);terminal(6);assert(observed_launches==launches_before);axil_write(0,8);
        frame(3,2,1000,1,2);axil_write(0,2);terminal(6);assert(observed_launches==launches_before);axil_write(0,8);
        assert(early_done_with_pending_b>=4);
        $display("PASS typed200: %0d golden words, %0d paired completions, %0d launches; delayed B, early proposal, B/R errors, timeout/late response, stale session, shapes",total,paired_done,observed_launches);
        $finish;
    end
