// Behavioral IEEE 802.3 clause-22 PHY (DP83867-like) for testbenches: answers reads at
// one address, records writes, supports REGCR/ADDAR extended-register access.
module mdio_phy_model #(
    parameter logic [4:0] ADDR = 5'd4
) (
    input  logic mdc,
    input  logic mdio_t,
    input  logic mdio_o,
    output logic mdio_i
);
    logic [15:0] regs [32];
    logic [15:0] ext [256];
    logic drv = 0, bitv = 1;
    assign mdio_i = mdio_t ? (drv ? bitv : 1'b1) : mdio_o;

    initial begin
        for (int i = 0; i < 32; i++) regs[i] = 0;
        for (int i = 0; i < 256; i++) ext[i] = 0;
        regs[1] = 16'h796D; regs[2] = 16'h2000; regs[3] = 16'hA231; regs[5'h11] = 16'hAC02;
    end

    initial begin
        int ones; logic [12:0] hdr; logic [15:0] wd, rdv; logic [4:0] pa, ra; logic [1:0] op;
        forever begin
            ones = 0;
            while (1) begin
                @(posedge mdc);
                if (mdio_i) ones++;
                else if (ones >= 32) break;
                else ones = 0;
            end
            for (int hb = 0; hb < 13; hb++) begin @(posedge mdc); hdr[12 - hb] = mdio_i; end
            op = hdr[11:10]; pa = hdr[9:5]; ra = hdr[4:0];
            if (op == 2'b10) begin
                if (pa == ADDR) begin
                    rdv = (ra == 5'h0E && regs[5'h0D] == 16'h401F) ? ext[regs[5'h0E][7:0]] : regs[ra];
                    @(posedge mdc); #10; drv = 1; bitv = 0;            // after TA1 rising: TA2 = 0
                    for (int k = 15; k >= 0; k--) begin @(posedge mdc); #10; bitv = rdv[k]; end
                    @(posedge mdc); #10; drv = 0;
                end
            end else begin
                for (int k = 0; k < 18; k++) begin @(posedge mdc); if (k >= 2) wd[17 - k] = mdio_i; end
                if (pa == ADDR) begin
                    if (ra == 5'h0E && regs[5'h0D] == 16'h401F) ext[regs[5'h0E][7:0]] = wd;
                    else regs[ra] = wd;
                end
            end
        end
    end
endmodule
