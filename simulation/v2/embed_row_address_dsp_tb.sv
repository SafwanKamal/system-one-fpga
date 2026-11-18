`timescale 1ns/1ps
module embed_row_address_dsp_tb;
    logic clk=0; always #5 clk=~clk;
    logic reset=1,input_capture=0,output_capture=0;
    logic [15:0] id=0,stride=0;
    logic [31:0] base=0,address32;
    logic [26:0] address27;
    embed_row_address_dsp #(.ADDRESS_WIDTH(32)) k32(.*,.address(address32));
    embed_row_address_dsp #(.ADDRESS_WIDTH(27)) k27(
        .clk,.reset,.input_capture,.output_capture,.id,.stride,.base(base[26:0]),.address(address27));
    longint unsigned expected32=0,expected27=0;
    logic [15:0] previous_id=0,previous_stride=0;
    logic [31:0] previous_base=0;
    int comparisons=0,captures=0,outputs=0,resets=0;
    int unsigned random_state=32'h123acdef;
    function automatic int unsigned next_random();
        random_state=random_state^(random_state<<13);
        random_state=random_state^(random_state>>17);
        random_state=random_state^(random_state<<5);
        return random_state;
    endfunction
    task automatic tick;
        @(posedge clk);
        if(reset) begin
            expected32=0;expected27=0;previous_id=0;previous_stride=0;previous_base=0;resets++;
        end else begin
            if(output_capture) begin
                expected32=(64'(previous_id)*64'(previous_stride)+64'(previous_base))&64'hffffffff;
                expected27=(64'(previous_id)*64'(previous_stride)+64'(previous_base[26:0]))&64'h7ffffff;
                outputs++;
            end
            if(input_capture) begin
                previous_id=id;previous_stride=stride;previous_base=base;captures++;
            end
        end
        #1;
        if(address32!==32'(expected32) || address27!==27'(expected27))
            $fatal(1,"Address arithmetic/capture/reset mismatch at%0d",comparisons);
        comparisons+=2;
        @(negedge clk);
    endtask
    initial begin
        tick(); reset=0;
        // Every stride, maximum unsigned ID/base and modular overflow.
        for(int s=0;s<65536;s++) begin
            input_capture=1;output_capture=0;id=16'hffff;stride=16'(s);base=32'hfffffff0;
            tick();input_capture=0;output_capture=1;tick();
        end
        // Independent capture/output enables, simultaneous edges, holds and reset.
        for(int n=0;n<500000;n++) begin
            int unsigned flags;
            flags=next_random();input_capture=flags[0];output_capture=flags[1];
            reset=(flags[12:2]==0);id=16'(next_random());stride=16'(next_random());base=next_random();
            if(n%31==0)id=16'h8000;
            if(n%37==0)stride=16'hffff;
            tick();
        end
        $display("PASS DSP row address:%0d comparisons,%0d captures,%0d outputs,%0d resets; all65536strides,27/32bit wraps,holds,simultaneous enables",comparisons,captures,outputs,resets);
        $finish;
    end
endmodule
