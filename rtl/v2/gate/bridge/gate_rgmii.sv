// RGMII <-> byte streams at 1000, 100 and 10 Mb/s.  The PHY (DP83867) adds both RX and TX
// clock delays (rgmii-id), so data are sampled/launched edge-aligned to the clocks.
//   speed: 2'b10 = 1000, 2'b01 = 100, 2'b00 = 10 (DP83867 PHYSTS[15:14] encoding)
// At 1000 Mb/s a byte crosses per clock (low nibble on the rising edge).  At 10/100 the
// clock is 25/2.5 MHz and one nibble crosses per clock (same value on both edges).

module gate_rgmii_rx #(
    parameter int IDELAY_PS = 0
) (
    input  logic       rxc,
    input  logic [3:0] rd,
    input  logic       rx_ctl,
    input  logic [1:0] speed,        // core-domain value; synchronized here
    output logic [7:0] rxd,          // rxc domain byte stream, qualified by rx_ce
    output logic       rx_dv,
    output logic       rx_er,
    output logic       rx_ce
);
    logic [3:0] lo, hi;
    logic       c_rise, c_fall;
    for (genvar i = 0; i < 4; i++) begin : g_d
        gate_iddr #(.IDELAY_PS(IDELAY_PS)) u (.clk(rxc), .d(rd[i]), .q_rise(lo[i]), .q_fall(hi[i]));
    end
    gate_iddr #(.IDELAY_PS(IDELAY_PS)) u_ctl (.clk(rxc), .d(rx_ctl), .q_rise(c_rise), .q_fall(c_fall));

    (* ASYNC_REG = "TRUE" *) logic [1:0] sp1, sp2;
    always_ff @(posedge rxc) begin sp1 <= speed; sp2 <= sp1; end
    wire gig = (sp2 == 2'b10);

    // 10/100: nibble -> byte, re-creating one 0x55 and the 0xD5 SFD for gate_eth_rx
    typedef enum logic [1:0] {N_IDLE, N_PRE, N_DATA} nst_t;
    nst_t ns;
    logic       ph;
    logic [3:0] lown;
    logic       sent55;

    always_ff @(posedge rxc) begin
        if (gig) begin
            rxd <= {hi, lo}; rx_dv <= c_rise; rx_er <= c_rise ^ c_fall; rx_ce <= 1'b1;
            ns <= N_IDLE;
        end else begin
            rx_ce <= 1'b0; rx_er <= 1'b0;
            case (ns)
            N_IDLE: begin
                rx_dv <= 1'b0;
                if (c_rise && lo == 4'h5) begin
                    ns <= N_PRE; rxd <= 8'h55; rx_dv <= 1'b1; rx_ce <= 1'b1;
                end
            end
            N_PRE: begin
                if (!c_rise) begin ns <= N_IDLE; rx_dv <= 1'b0; rx_ce <= 1'b1; end
                else if (lo == 4'hD) begin
                    rxd <= 8'hD5; rx_dv <= 1'b1; rx_ce <= 1'b1; ns <= N_DATA; ph <= 1'b0;
                end else if (lo != 4'h5) begin ns <= N_IDLE; rx_dv <= 1'b0; rx_ce <= 1'b1; end
            end
            N_DATA: begin
                if (!c_rise) begin
                    rx_dv <= 1'b0; rx_ce <= 1'b1; ns <= N_IDLE;        // frame end
                end else if (!ph) begin
                    lown <= lo; ph <= 1'b1;
                end else begin
                    rxd <= {lo, lown}; rx_dv <= 1'b1; rx_ce <= 1'b1; ph <= 1'b0;
                end
            end
            default: ns <= N_IDLE;
            endcase
        end
    end
endmodule

module gate_rgmii_tx (
    input  logic       clk,          // 125 MHz core clock
    input  logic [1:0] speed,
    input  logic [7:0] txd,          // byte from the transmit engine
    input  logic       tx_en,
    output logic       tx_ce,        // engine advances to the next byte when high
    output logic       txc,
    output logic [3:0] td,
    output logic       tx_ctl
);
    wire gig = (speed == 2'b10);
    wire [6:0] nib = (speed == 2'b01) ? 7'd5 : 7'd50;   // core cycles per nibble
    logic [7:0] c;                                       // 0 .. 2*nib-1 within a byte
    logic [7:0] byte_l;
    logic       en_l;
    logic [3:0] d_r, d_f;
    logic       ctl_r, ctl_f, ck_r, ck_f;
    logic [6:0] cn;

    always_ff @(posedge clk) begin
        if (gig) begin
            c <= 0;
        end else begin
            if (c == {nib, 1'b0} - 8'd1) c <= 0; else c <= c + 1;
            if (c == 0) begin byte_l <= txd; en_l <= tx_en; end
        end
    end
    assign tx_ce = gig ? 1'b1 : (c == 0);
    assign cn = (c < {1'b0, nib}) ? c[6:0] : c[6:0] - nib;

    always_comb begin
        if (gig) begin
            d_r = txd[3:0]; d_f = txd[7:4]; ctl_r = tx_en; ctl_f = tx_en; ck_r = 1'b1; ck_f = 1'b0;
        end else begin
            d_r = (c < {1'b0, nib}) ? byte_l[3:0] : byte_l[7:4];
            d_f = d_r;
            ctl_r = en_l; ctl_f = en_l;
            // TXC high for cycles [2/5, 4/5) of each nibble -> rising edge mid-nibble, 40% duty
            ck_r = (cn >= (nib * 2) / 5) && (cn < (nib * 4) / 5);
            ck_f = ck_r;
        end
    end
    for (genvar i = 0; i < 4; i++) begin : g_d
        gate_oddr u (.clk(clk), .d_rise(d_r[i]), .d_fall(d_f[i]), .q(td[i]));
    end
    gate_oddr u_ctl (.clk(clk), .d_rise(ctl_r), .d_fall(ctl_f), .q(tx_ctl));
    gate_oddr u_clk (.clk(clk), .d_rise(ck_r), .d_fall(ck_f), .q(txc));
endmodule
