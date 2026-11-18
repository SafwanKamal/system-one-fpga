`timescale 1ns/1ps
module deadline_supervisor_tb;
    logic clk=0, reset=1, start=0, ack=0, core_done=0, core_fault=0;
    logic [31:0] budget_cycles=0, elapsed;
    logic ready, active, result_valid, quarantined;
    logic [2:0] outcome;
    always #5 clk=~clk;
    deadline_supervisor dut(.*);
    task automatic tick;
        @(posedge clk); #1; @(negedge clk);
    endtask
    task automatic init;
        reset=1; start=0; ack=0; core_done=0; core_fault=0;
        tick(); reset=0; tick();
    endtask
    initial begin
        // Exhaust all completion/deadline boundary relations for small budgets.
        for (int limit=1;limit<=16;limit++) begin
            for (int done_at=1;done_at<=18;done_at++) begin
                init(); budget_cycles=32'(limit); start=1; tick(); start=0;
                for (int age=1;age<=18;age++) begin
                    core_done=age==done_at; tick();
                    if (age < limit && age < done_at && result_valid)
                        $fatal(1,"Premature result");
                    if (age >= limit || age >= done_at) begin
                        if (!result_valid || outcome != (done_at<=limit ? 1 : 2))
                            $fatal(1,"Wrong boundary outcome limit=%0d done=%0d age=%0d",limit,done_at,age);
                        if(elapsed != 32'(done_at<=limit ? done_at : limit))
                            $fatal(1,"Result age changed after terminal outcome");
                    end
                end
                if (done_at > limit) begin
                    ack=1; start=1; tick();
                    if(ready || active || !quarantined || outcome!=2 || !result_valid)
                        $fatal(1,"Late completion/ack/restart escaped quarantine");
                end
            end
        end
        init(); budget_cycles=0; start=1; tick(); start=0;
        if(outcome!=3 || !result_valid || active) $fatal(1,"Zero budget not rejected");
        ack=1;tick();ack=0;if(!ready) $fatal(1,"Invalid input cannot be acknowledged");
        init();budget_cycles=3;start=1;tick();start=0;budget_cycles=100;
        repeat(3) tick();if(outcome!=2 || elapsed!=3) $fatal(1,"Mutable budget extended deadline");
        init();budget_cycles=32'hffffffff;start=1;tick();start=0;core_done=1;core_fault=1;tick();
        if(outcome!=4 || elapsed!=1) $fatal(1,"Hardware fault classification failed");
        $display("PASS supervisor 288 boundary scenarios, invalid budget, immutable deadline, fault and quarantine");
        $finish;
    end
endmodule
