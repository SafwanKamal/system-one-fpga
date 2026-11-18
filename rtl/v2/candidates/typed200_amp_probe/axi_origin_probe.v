// Volatile qualification probe only. No encoder, permit, DDR master or PL I/O.
// Records actual AWUSER/PROT/ID, never a payload-claimed source identity.
module axi_origin_probe (
 (* X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET reset_n" *) input wire clk,
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire reset_n,
 input wire [15:0] s_axi_awid, input wire [39:0] s_axi_awaddr,
 input wire [7:0] s_axi_awlen, input wire [2:0] s_axi_awsize,
 input wire [1:0] s_axi_awburst, input wire s_axi_awlock,
 input wire [3:0] s_axi_awcache, input wire [2:0] s_axi_awprot,
 input wire [3:0] s_axi_awqos, input wire [15:0] s_axi_awuser,
 input wire s_axi_awvalid, output wire s_axi_awready,
 input wire [127:0] s_axi_wdata, input wire [15:0] s_axi_wstrb,
 input wire s_axi_wlast,s_axi_wvalid, output wire s_axi_wready,
 output wire [15:0] s_axi_bid, output wire [1:0] s_axi_bresp,
 output wire s_axi_bvalid, input wire s_axi_bready,
 input wire [15:0] s_axi_arid, input wire [39:0] s_axi_araddr,
 input wire [7:0] s_axi_arlen, input wire [2:0] s_axi_arsize,
 input wire [1:0] s_axi_arburst, input wire s_axi_arlock,
 input wire [3:0] s_axi_arcache, input wire [2:0] s_axi_arprot,
 input wire [3:0] s_axi_arqos, input wire [15:0] s_axi_aruser,
 input wire s_axi_arvalid, output wire s_axi_arready,
 output wire [15:0] s_axi_rid, output wire [127:0] s_axi_rdata,
 output wire [1:0] s_axi_rresp, output wire s_axi_rlast,s_axi_rvalid,
 input wire s_axi_rready
);
 reg aw_full,w_full,drain,bvalid;
 reg [39:0] awaddr;
 reg [15:0] awid,awuser,wstrb;
 reg [7:0] awlen,left;
 reg [2:0] awprot,awsize;
 reg [1:0] awburst,bresp;
 reg awlock,wlast;
 reg [127:0] wdata;
 reg [31:0] ticks,writes,errors;
 reg [31:0] tags[0:15],addresses[0:15],values[0:15],metadata[0:15];
 reg rvalid;
 reg [15:0] rid;
 reg [127:0] rdata;
 reg [1:0] rresp;
 reg [7:0] rleft;
 assign s_axi_awready=reset_n && !aw_full && !drain && !bvalid;
 assign s_axi_wready=reset_n && (drain || (!w_full && !bvalid));
 assign s_axi_bid=awid;assign s_axi_bresp=bresp;assign s_axi_bvalid=reset_n && bvalid;
 assign s_axi_arready=reset_n && !rvalid;
 assign s_axi_rid=rid;assign s_axi_rdata=rdata;assign s_axi_rresp=rresp;
 assign s_axi_rlast=rleft==0;assign s_axi_rvalid=reset_n && rvalid;
 function [31:0] read_word;
  input [11:0] a;
  reg [3:0] slot;
  begin
   slot=a[7:4];read_word=0;
   case(a)
    12'h000:read_word=32'h4f524731;
    12'h004:read_word=1;
    12'h008:read_word=writes;
    12'h00c:read_word=errors;
    12'h010:read_word=ticks;
    12'h018:read_word={13'b0,s_axi_arprot,s_axi_aruser};
    12'h01c:read_word={16'b0,s_axi_arid};
    default:if(a>=12'h100 && a<12'h200)case(a[3:2])
     0:read_word=tags[slot];1:read_word=addresses[slot];
     2:read_word=values[slot];3:read_word=metadata[slot];
    endcase
   endcase
  end
 endfunction
 integer i;
 always @(posedge clk)begin
  if(!reset_n)begin
   aw_full<=0;w_full<=0;drain<=0;bvalid<=0;bresp<=0;
   awaddr<=0;awid<=0;awuser<=0;awlen<=0;left<=0;awprot<=0;awsize<=0;
   awburst<=0;awlock<=0;wstrb<=0;wlast<=0;wdata<=0;
   rvalid<=0;rid<=0;rdata<=0;rresp<=0;rleft<=0;ticks<=0;writes<=0;errors<=0;
   for(i=0;i<16;i=i+1)begin tags[i]<=0;addresses[i]<=0;values[i]<=0;metadata[i]<=0;end
  end else begin
   ticks<=ticks+1;
   if(s_axi_awvalid && s_axi_awready)begin
    aw_full<=1;awaddr<=s_axi_awaddr;awid<=s_axi_awid;awuser<=s_axi_awuser;
    awlen<=s_axi_awlen;awprot<=s_axi_awprot;awsize<=s_axi_awsize;
    awburst<=s_axi_awburst;awlock<=s_axi_awlock;
   end
   if(s_axi_wvalid && s_axi_wready && !drain)begin
    w_full<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;wlast<=s_axi_wlast;
   end
   if(aw_full && w_full && !drain && !bvalid)begin
    if(awlen!=0)begin
     drain<=1;left<=awlen;bresp<=3;
     if(wlast)errors<=errors+1;
    end else begin
     bvalid<=1;bresp<=3;
     if(awaddr[39:6]==34'h02800000 && awaddr[1:0]==0 &&
        awsize==2 && awburst<=1 && !awlock && wlast &&
        wstrb==(16'hf<<awaddr[3:0]))begin
      tags[awaddr[5:2]]<={13'b0,awprot,awuser};
      addresses[awaddr[5:2]]<=awaddr[31:0];
      values[awaddr[5:2]]<=wdata[8*awaddr[3:0]+:32];
      metadata[awaddr[5:2]]<={writes[15:0],awid};
      writes<=writes+1;bresp<=0;
     end else errors<=errors+1;
    end
   end
   if(drain && s_axi_wvalid && s_axi_wready)begin
    left<=left-1;
    if(s_axi_wlast!=(left==1))errors<=errors+1;
    if(left==1)begin drain<=0;bvalid<=1;end
   end
   if(bvalid && s_axi_bready)begin bvalid<=0;aw_full<=0;w_full<=0;end
   if(s_axi_arvalid && s_axi_arready)begin
    rvalid<=1;rid<=s_axi_arid;rleft<=s_axi_arlen;
    rresp<=3;rdata<=0;
    if(s_axi_araddr[39:12]==28'h00a0000 && s_axi_araddr[1:0]==0 &&
       s_axi_arlen==0 && s_axi_arsize==2 && s_axi_arburst<=1 && !s_axi_arlock)begin
     rresp<=0;rdata<={96'b0,read_word(s_axi_araddr[11:0])}<<(8*s_axi_araddr[3:0]);
    end
   end
   if(rvalid && s_axi_rready)begin
    if(rleft==0)rvalid<=0;
    else rleft<=rleft-1;
   end
  end
 end
endmodule
