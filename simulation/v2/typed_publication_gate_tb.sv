`timescale 1ns/1ps
module typed_publication_gate_tb;
    logic clk=0,reset=1,start=0,ack=0,core_quiescent=1;
    always #5 clk=~clk;
    logic [63:0] request_id=1,proposal_request_id=1;
    logic [255:0] contract_sha256=256'h1234,proposal_contract_sha256=256'h1234;
    logic [31:0] budget_cycles=1;
    logic proposal_valid=0;
    logic [2:0] proposal_outcome=1;
    logic [15:0] proposal_label=3,proposal_confidence=40000;
    wire ready,admitted,active,result_valid,quarantined;
    wire [63:0] result_request_id;
    wire [255:0] result_contract_sha256;
    wire [2:0] result_outcome;
    wire [15:0] result_label,result_confidence;
    wire [31:0] elapsed;
    typed_publication_gate #(.LABEL_COUNT(8),.MIN_CONFIDENCE(30000)) dut(.*);
    task tick; @(posedge clk);#1;@(negedge clk);endtask
    task init_case(input int budget);
        reset=1;start=0;ack=0;proposal_valid=0;core_quiescent=1;tick();reset=0;
        request_id=1;proposal_request_id=1;contract_sha256=256'h1234;
        proposal_contract_sha256=contract_sha256;budget_cycles=budget;
        proposal_outcome=1;proposal_label=3;proposal_confidence=40000;
        start=1;tick();start=0;
    endtask
    initial begin
        for(int d=1;d<=16;d++) for(int arrival=1;arrival<=18;arrival++) begin
            init_case(d);
            for(int age=1;age<=d;age++) begin
                proposal_valid=(age==arrival);tick();
                if(age < ((arrival<d)?arrival:d)) assert(!result_valid);
            end
            assert(result_valid && !active);
            assert(result_outcome==((arrival<=d)?1:5));
            assert(elapsed==32'((arrival<=d)?arrival:d));
            if(arrival<=d) begin
                assert(result_label==3 && result_confidence==40000);
            end
            else begin
                assert(result_label==0 && result_confidence==0 && quarantined);
                ack=1;proposal_valid=1;tick();assert(result_outcome==5 && !ready);
            end
        end
        init_case(2);proposal_valid=1;proposal_request_id=2;tick();
        proposal_request_id=1;proposal_contract_sha256=256'h5678;tick();
        assert(result_outcome==5 && result_label==0);
        init_case(2);proposal_valid=1;proposal_label=8;tick();
        assert(result_outcome==4 && quarantined && result_label==0);
        init_case(2);proposal_valid=1;proposal_confidence=29999;tick();
        assert(result_outcome==3 && result_label==0 && result_confidence==0);
        init_case(2);proposal_valid=1;proposal_label=7;proposal_confidence=30000;tick();
        assert(result_outcome==1 && result_label==7 && result_confidence==30000);
        init_case(2);proposal_valid=1;proposal_outcome=7;tick();
        assert(result_outcome==4 && result_label==0 && quarantined);
        for(int o=2;o<=4;o++) begin
            init_case(2);proposal_valid=1;proposal_outcome=3'(o);tick();
            assert(result_outcome==3'(o) && result_label==0 && result_confidence==0);
        end
        init_case(2);proposal_valid=1;core_quiescent=0;tick();
        assert(result_outcome==4 && quarantined);
        init_case(0);assert(result_valid && result_outcome==6 && !active);
        init_case(3);budget_cycles=100;tick();tick();tick();
        assert(result_outcome==5 && elapsed==3);
        init_case(2);proposal_valid=1;tick();proposal_valid=0;ack=1;tick();ack=0;
        start=1;tick();start=0;assert(result_outcome==6); // replayed ID
        $display("PASS typed publication 288 deadline boundaries, identity, enums, empty failures, replay and quarantine");
        $finish;
    end
endmodule
