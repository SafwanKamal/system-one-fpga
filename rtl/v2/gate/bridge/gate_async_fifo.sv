// Dual-clock FIFO with Gray-coded pointers (first-word-fall-through read).
module gate_async_fifo #(
    parameter int W  = 8,
    parameter int AW = 12
) (
    input  logic          wclk,
    input  logic          wrst,
    input  logic          wen,
    input  logic [W-1:0]  wdata,
    output logic [AW:0]   wfree,      // free entries as seen by the writer (conservative)
    input  logic          rclk,
    input  logic          rrst,
    input  logic          ren,
    output logic [W-1:0]  rdata,
    output logic          rempty
);
    localparam int D = 1 << AW;
    (* ram_style = "block" *) logic [W-1:0] mem [D];

    function automatic logic [AW:0] g2b(input logic [AW:0] g);
        logic [AW:0] b;
        b[AW] = g[AW];
        for (int i = AW - 1; i >= 0; i--) b[i] = b[i + 1] ^ g[i];
        return b;
    endfunction

    logic [AW:0] wbin, wgray, rbin, rgray;
    (* ASYNC_REG = "TRUE" *) logic [AW:0] rg_w1, rg_w2;   // read pointer in write domain
    (* ASYNC_REG = "TRUE" *) logic [AW:0] wg_r1, wg_r2;   // write pointer in read domain

    // write side
    always_ff @(posedge wclk) begin
        if (wrst) begin
            wbin <= 0; wgray <= 0; rg_w1 <= 0; rg_w2 <= 0;
        end else begin
            rg_w1 <= rgray; rg_w2 <= rg_w1;
            if (wen) begin
                mem[wbin[AW-1:0]] <= wdata;
                wbin  <= wbin + 1'b1;
                wgray <= (wbin + 1'b1) ^ ((wbin + 1'b1) >> 1);
            end
        end
    end
    assign wfree = (AW + 1)'(D) - (wbin - g2b(rg_w2));

    // read side (FWFT: rdata shows the head entry whenever !rempty)
    logic [AW:0] wbin_r;
    assign wbin_r = g2b(wg_r2);
    logic [AW:0] rnext;
    assign rnext = (ren && !rempty) ? rbin + 1'b1 : rbin;
    always_ff @(posedge rclk) begin
        if (rrst) begin
            rbin <= 0; rgray <= 0; wg_r1 <= 0; wg_r2 <= 0; rempty <= 1'b1;
        end else begin
            wg_r1 <= wgray; wg_r2 <= wg_r1;
            rbin  <= rnext;
            rgray <= rnext ^ (rnext >> 1);
            rdata <= mem[rnext[AW-1:0]];
            rempty <= (rnext == wbin_r);
        end
    end
endmodule
