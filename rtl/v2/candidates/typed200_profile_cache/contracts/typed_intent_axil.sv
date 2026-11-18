// Standalone AXI4-Lite slave, 32-bit data, one clock, one outstanding read/write.
// Shadow banks and a single commit strobe provide atomic frames. Not deployed.
module typed_intent_axil (
    input logic clk, reset,
    input logic [7:0] s_awaddr, input logic s_awvalid, output wire s_awready,
    input logic [31:0] s_wdata, input logic [3:0] s_wstrb,
    input logic s_wvalid, output wire s_wready,
    output logic [1:0] s_bresp, output logic s_bvalid, input logic s_bready,
    input logic [7:0] s_araddr, input logic s_arvalid, output wire s_arready,
    output logic [31:0] s_rdata, output logic [1:0] s_rresp,
    output logic s_rvalid, input logic s_rready,
    input logic core_complete, core_success, live_quiet,
    input logic [63:0] core_session, core_request_id,
    input logic environment_ready,
    input logic [31:0] encoder_clocks, request_clocks,
    output wire terminal_valid, terminal_quarantined, retired,
    output wire [15:0] admission_tokens, admission_first, admission_count,
    output logic [15:0] owned_tokens, owned_first, owned_count,
    output wire admitted,
    output wire [63:0] admitted_session, admitted_request_id
);
    localparam logic [255:0] PROFILE=256'h8133633315487f8f322ecac49e95e7aca3801d00fccb4b4fba36026c5b2752d2;
    // Each bit equals its stored byte's equality, including unwritten reset bytes.
    // Update on the SAME execute edge/WSTRB as that byte. Never cache live quiet,
    // errors, epoch, ownership, request sequencing or deadline permission.
    (* keep = "true" *) logic [31:0] profile_byte_equal;
    (* keep = "true" *) wire [3:0] profile_group_equal;
    for(genvar w=0;w<8;w++) begin : gen_profile_word
        for(genvar b=0;b<4;b++) begin : gen_profile_byte
            always_ff @(posedge clk) begin
                if(reset) profile_byte_equal[4*w+b] <= PROFILE[32*w+8*b+:8]==8'd0;
                else if(execute && aw==8'(32+4*w) && ws[b])
                    profile_byte_equal[4*w+b] <= wd[8*b+:8]==PROFILE[32*w+8*b+:8];
            end
        end
    end
    for(genvar g=0;g<4;g++) begin : gen_profile_group
        assign profile_group_equal[g]=&profile_byte_equal[8*g+:8];
    end
    wire request_contract_matches=&profile_group_equal;
    logic aw_full,w_full;
    logic [7:0] aw;
    logic [31:0] wd;
    logic [3:0] ws;
    logic [31:0] bank[0:29]; // offsets 0x08..0x7c
    logic [3:0] written[0:29];
    wire execute=aw_full && w_full && !s_bvalid;
    wire [4:0] shadow_index=aw[6:2]-5'd2;
    wire control=execute && aw==0 && ws==4'hf;
    wire one_command=(wd==1 || wd==2 || wd==4 || wd==8);
    logic request_complete,proposal_complete,session_complete;
    wire ready,active,valid,quarantine,configured;
    wire [63:0] result_session,result_id;
    wire [255:0] result_contract;
    wire [2:0] outcome;
    wire [15:0] label,score;
    wire [31:0] elapsed;
    wire install=control && wd==1 && session_complete && !configured && {bank[1],bank[0]}!=0;
    wire start=control && wd==2 && request_complete && ready && environment_ready;
    wire commit=control && wd==4 && proposal_complete && active;
    wire ack=control && wd==8 && valid && !quarantine;
    wire shape_ok=bank[5][15:0]>0 && bank[5][15:0]<=128 && bank[28][31:16]==0
        && bank[28][15:0]>0 && bank[5][31:16]<bank[5][15:0]
        && ({1'b0,bank[5][31:16]}+{1'b0,bank[28][15:0]})<={1'b0,bank[5][15:0]};
    assign admission_tokens=bank[5][15:0];
    assign admission_first=bank[5][31:16];
    assign admission_count=bank[28][15:0];
    assign terminal_valid=valid;
    assign terminal_quarantined=quarantine;
    assign retired=ack;
    assign s_awready=!aw_full && !s_bvalid;
    assign s_wready=!w_full && !s_bvalid;
    assign s_arready=!s_rvalid;
    assign admitted_session=result_session;
    assign admitted_request_id={bank[3],bank[2]};
    always_comb begin
        session_complete=written[0]==15 && written[1]==15;
        request_complete=written[2]==15 && written[3]==15 && written[4]==15 && written[5]==15 && written[28]==15;
        for(int i=6;i<14;i++) request_complete=request_complete && written[i]==15;
        proposal_complete=1;
        for(int i=14;i<28;i++) proposal_complete=proposal_complete && written[i]==15;
    end
    logic [31:0] read_value;
    logic read_ok;
    always_comb begin
        read_value=0;read_ok=1;
        case(s_araddr)
            8'h04:read_value={27'd0,configured,quarantine,valid,active,(ready && environment_ready)};
            8'h80:read_value=result_session[31:0];
            8'h84:read_value=result_session[63:32];
            8'h88:read_value=result_id[31:0];
            8'h8c:read_value=result_id[63:32];
            8'hb0:read_value={label,13'd0,outcome};
            8'hb4:read_value={16'd0,score};
            8'hb8:read_value=elapsed;
            8'hc4:read_value={owned_first,owned_tokens};
            8'hc8:read_value={16'd0,owned_count};
            8'hcc:read_value={27'd0,environment_ready,core_complete,core_success,live_quiet,quarantine};
            8'hd0:read_value=encoder_clocks;
            8'hd4:read_value=request_clocks;
            8'hc0:read_value=32'h54590201; // TY, version 1, profile 1
            default:begin
                if(s_araddr>=8'h90 && s_araddr<=8'hac && s_araddr[1:0]==0)
                    read_value=result_contract[32*((s_araddr-8'h90)>>2)+:32];
                else read_ok=0;
            end
        endcase
    end
    always_ff @(posedge clk) begin
        if(reset) begin
            aw_full<=0;w_full<=0;aw<=0;wd<=0;ws<=0;owned_tokens<=0;owned_first<=0;owned_count<=0;
            s_bvalid<=0;s_bresp<=0;s_rvalid<=0;s_rdata<=0;s_rresp<=0;
            for(int i=0;i<30;i++) begin bank[i]<=0;written[i]<=0;end
        end else begin
            if(admitted) begin
                owned_tokens<=admission_tokens;owned_first<=admission_first;owned_count<=admission_count;
            end
            if(s_bvalid && s_bready) s_bvalid<=0;
            if(s_rvalid && s_rready) s_rvalid<=0;
            if(s_awvalid && s_awready) begin aw<=s_awaddr;aw_full<=1;end
            if(s_wvalid && s_wready) begin wd<=s_wdata;ws<=s_wstrb;w_full<=1;end
            if(s_arvalid && s_arready) begin
                s_rvalid<=1;s_rdata<=read_value;s_rresp<=read_ok ? 2'b00 : 2'b10;
            end
            if(execute) begin
                aw_full<=0;w_full<=0;s_bvalid<=1;s_bresp<=0;
                if(aw==0) begin
                    if(!control || !one_command || !(install || start || commit || ack)) s_bresp<=2;
                    if(install) begin written[0]<=0;written[1]<=0;end
                    if(start) begin
                        for(int i=2;i<14;i++) written[i]<=0;
                        written[28]<=0;
                        // Every request requires a fresh full proposal frame.
                        for(int i=14;i<28;i++) written[i]<=0;
                    end
                    if(commit) for(int i=14;i<28;i++) written[i]<=0;
                end else if(aw>=8'h08 && aw<=8'h78 && aw[1:0]==0) begin
                    for(int byte_lane=0;byte_lane<4;byte_lane++)
                        if(ws[byte_lane]) bank[shadow_index][8*byte_lane+:8]<=wd[8*byte_lane+:8];
                    written[shadow_index]<=written[shadow_index] | ws;
                end else s_bresp<=2;
            end
        end
    end
    typed_intent_guard guard (
        .clk(clk),.reset(reset),.install_session(install),.session_value({bank[1],bank[0]}),
        .start(start),.ack(ack),.request_id({bank[3],bank[2]}),
        .request_contract({bank[13],bank[12],bank[11],bank[10],bank[9],bank[8],bank[7],bank[6]}),
        .request_contract_matches(request_contract_matches),
        .budget_cycles(shape_ok ? bank[4] : 32'd0),.proposal_valid(commit),
        .proposal_session({bank[15],bank[14]}),.proposal_request_id({bank[17],bank[16]}),
        .proposal_contract({bank[25],bank[24],bank[23],bank[22],bank[21],bank[20],bank[19],bank[18]}),
        .proposal_outcome(bank[26][2:0]),.proposal_label(bank[26][31:16]),
        .proposal_reserved_score((bank[27]!=0 || bank[26][15:3]!=0) ? 16'd1 : 16'd0),
        .core_complete(core_complete),.core_success(core_success),.live_quiet(live_quiet),
        .core_session(core_session),.core_request_id(core_request_id),
        .session_configured(configured),.result_session(result_session),.ready(ready),.admitted(admitted),
        .active(active),.result_valid(valid),.quarantined(quarantine),.result_request_id(result_id),
        .result_contract(result_contract),.result_outcome(outcome),.result_label(label),
        .result_reserved_score(score),.elapsed(elapsed)
    );
endmodule
