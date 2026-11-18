// I/O primitives for the RGMII bridge.  UltraScale+ IDDRE1/ODDRE1 in hardware; simple
// behavioral equivalents under Verilator (same cycle alignment as SAME_EDGE_PIPELINED).
package gate_eth_pkg;
    function automatic logic [31:0] crc_byte(input logic [31:0] c, input logic [7:0] d);
        logic [31:0] w;
        w = c;
        for (int i = 0; i < 8; i++)
            w = (w[0] ^ d[i]) ? ((w >> 1) ^ 32'hEDB88320) : (w >> 1);
        return w;
    endfunction
    localparam logic [31:0] CRC_RESIDUE = 32'hDEBB20E3;   // register value after a good frame + FCS
endpackage

// Rising-edge bit on q_rise, falling-edge bit on q_fall, both registered on the next
// rising edge (IDDRE1 DDR_CLK_EDGE = "SAME_EDGE_PIPELINED").
module gate_iddr #(
    parameter int IDELAY_PS = 0          // >0: calibrated IDELAYE3 (TIME mode) in front of the IDDR
) (
    input  logic clk,
    input  logic d,
    output logic q_rise,
    output logic q_fall
);
`ifdef VERILATOR
    logic r, f;
    always_ff @(posedge clk) begin
        r <= d;
        q_rise <= r;
        q_fall <= f;
    end
    always_ff @(negedge clk) f <= d;
`else
    logic dd;
    if (IDELAY_PS > 0) begin : g_dly
        IDELAYE3 #(.DELAY_SRC("IDATAIN"), .DELAY_TYPE("FIXED"), .DELAY_FORMAT("TIME"),
                   .DELAY_VALUE(IDELAY_PS), .REFCLK_FREQUENCY(333.333), .SIM_DEVICE("ULTRASCALE_PLUS"),
                   .CASCADE("NONE"), .UPDATE_MODE("ASYNC")) u_dly (
            .IDATAIN(d), .DATAOUT(dd), .DATAIN(1'b0), .CLK(1'b0), .CE(1'b0), .INC(1'b0), .LOAD(1'b0),
            .CNTVALUEIN(9'd0), .CNTVALUEOUT(), .EN_VTC(1'b1), .RST(1'b0),
            .CASC_IN(1'b0), .CASC_RETURN(1'b0), .CASC_OUT());
    end else begin : g_nodly
        assign dd = d;
    end
    IDDRE1 #(.DDR_CLK_EDGE("SAME_EDGE_PIPELINED"), .IS_CB_INVERTED(1'b1)) u (
        .Q1(q_rise), .Q2(q_fall), .C(clk), .CB(clk), .D(dd), .R(1'b0));
`endif
endmodule

// d_rise is driven while clk is high, d_fall while clk is low (ODDRE1).
module gate_oddr (
    input  logic clk,
    input  logic d_rise,
    input  logic d_fall,
    output logic q
);
`ifdef VERILATOR
    logic r, f;
    always_ff @(posedge clk) begin
        r <= d_rise;
        f <= d_fall;
    end
    assign q = clk ? r : f;
`else
    ODDRE1 #(.SRVAL(1'b0)) u (.Q(q), .C(clk), .D1(d_rise), .D2(d_fall), .SR(1'b0));
`endif
endmodule
