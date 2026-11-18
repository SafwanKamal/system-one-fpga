`timescale 1ns/1ps
module linear_drain_select_tb #(parameter integer ROW_CHANNELS=32,LANES=4);
    localparam integer COLUMN_WIDTH=$clog2(ROW_CHANNELS+1);
    logic clk=0,reset=1,advance;
    always #5 clk=~clk;
    logic in_valid=0,out_valid,bank;
    logic [32*ROW_CHANNELS-1:0] row0,row1;
    logic [COLUMN_WIDTH-1:0] column;
    logic [LANES-1:0] lane_mask,out_lane_mask;
    logic [17*LANES-1:0] multipliers,out_multipliers;
    logic [31:0] tag,out_tag;
    logic [32*LANES-1:0] selected;
    logic force_stall=0,held=0;
    logic [32*LANES-1:0] expected_data[0:8191],held_data;
    logic [LANES-1:0] expected_mask[0:8191],held_mask;
    logic [17*LANES-1:0] expected_m[0:8191],held_m;
    logic [31:0] expected_tag[0:8191],held_tag;
    int cycle=0,head=0,tail=0,stalls=0;
    int valid_bank0=0,valid_bank1=0,invalid_columns=0;
    int unsigned seed=5318;
    assign advance=!force_stall && cycle%5!=0 && cycle%13!=0;
    linear_drain_select #(.ROW_CHANNELS(ROW_CHANNELS),.LANES(LANES)) dut(.*);
    always @(posedge clk)begin
        cycle<=cycle+1;
        if(reset)begin head<=0;tail<=0;held<=0;stalls<=0;valid_bank0<=0;valid_bank1<=0;invalid_columns<=0;end
        else begin
            if(held && (!out_valid || selected!==held_data || out_lane_mask!==held_mask ||
                        out_multipliers!==held_m || out_tag!==held_tag))$fatal(1,"Drain tuple changed while stalled");
            held<=out_valid && !advance;
            held_data<=selected;held_mask<=out_lane_mask;held_m<=out_multipliers;held_tag<=out_tag;
            if(out_valid && !advance)stalls<=stalls+1;
            if(in_valid && advance)begin
                logic any_lane;
                any_lane=0;
                // Original one-stage semantic selection, independent of new pipeline registers.
                for(int l=0;l<LANES;l++)begin
                    expected_mask[tail][l]<=lane_mask[l] && int'(column)+l<ROW_CHANNELS;
                    expected_data[tail][32*l+:32]<=lane_mask[l] && int'(column)+l<ROW_CHANNELS ?
                        (bank ? row1[32*(int'(column)+l)+:32] : row0[32*(int'(column)+l)+:32]) : 32'd0;
                    any_lane |= lane_mask[l] && int'(column)+l<ROW_CHANNELS;
                end
                if(any_lane)begin
                    if(bank)valid_bank1<=valid_bank1+1;else valid_bank0<=valid_bank0+1;
                end
                if(int'(column)>=ROW_CHANNELS)invalid_columns<=invalid_columns+1;
                expected_m[tail]<=multipliers;expected_tag[tail]<=tag;tail<=tail+1;
            end
            if(out_valid && advance)begin
                if(head>=tail || selected!==expected_data[head] || out_lane_mask!==expected_mask[head] ||
                   out_multipliers!==expected_m[head] || out_tag!==expected_tag[head])
                    $fatal(1,"Drain selection/tag/multiplier mismatch at %0d",head);
                head<=head+1;
            end
        end
        if(cycle>30000)$fatal(1,"Drain test timed out");
    end
    task automatic send(input int n);
        bank=1'(n/(ROW_CHANNELS+2));column=COLUMN_WIDTH'(n%(ROW_CHANNELS+2));
        lane_mask=LANES'(n/(2*(ROW_CHANNELS+2))+1);
        tag=32'(n);in_valid=1;
        for(int c=0;c<ROW_CHANNELS;c++)begin
            row0[32*c+:32]=(n%7==0) ? 32'h80000000 : $urandom();
            row1[32*c+:32]=(n%11==0) ? 32'h7fffffff : $urandom();
        end
        for(int l=0;l<LANES;l++)multipliers[17*l+:17]=(n%3==0) ? 17'h1ffff : (n%3==1) ? 17'd0 : 17'($urandom());
        do @(posedge clk);while(!advance);
        @(negedge clk);in_valid=0;
    endtask
    initial begin
        int unsigned ignored;
        ignored=$urandom(seed);
        repeat(3)@(negedge clk);reset=0;
        send(0);send(1);force_stall=1;
        repeat(5)@(negedge clk);
        reset=1;repeat(3)@(negedge clk);reset=0;force_stall=0;
        if(out_valid)$fatal(1,"Reset left a drain tuple valid");
        for(int n=0;n<4096;n++)begin send(n);if(n%19==0)repeat(2)@(negedge clk);end
        while(head<4096)@(negedge clk);
        repeat(5)@(negedge clk);
        if(out_valid || tail!=4096 || !stalls || !valid_bank0 || !valid_bank1 || !invalid_columns)
            $fatal(1,"Incomplete drain coverage");
        $display("PASS two-stage drain selector: 4096 packets, ROW_CHANNELS=%0d LANES=%0d; signed row data, masks, banks, multipliers, tags, stalls and reset",ROW_CHANNELS,LANES);
        $finish;
    end
endmodule
