// Fixed PHY bring-up over MDIO (no runtime write path from the PS).
//  1. hold PHY reset for RESET_CYC, then wait SETTLE_CYC
//  2. scan addresses 0..31 for a PHYIDR1 that is not 0x0000/0xFFFF
//  3. if PHYIDR1 == 0x2000 (TI DP83867): RGMIICTL (ext 0x0032) = 0x00D3 (RGMII, TX+RX
//     internal clock delays), RGMIIDCTL (ext 0x0086) = 0x0077 (2.0 ns each)
//  4. ANAR = 0x0141 (10/100 full duplex), 1000BASE-T control = 0x0200 (1000FD), BMCR = 0x1340
//  5. forever: poll BMSR, PHYSTS (0x11) and ext RGMIICTL into status registers
// MDC = clk / (2*DIV).  MDIO out changes while MDC is low; MDIO in is sampled just
// before the rising edge.
module gate_mdio #(
    parameter int DIV = 25,                 // 125 MHz / 50 = 2.5 MHz MDC
    parameter int RESET_CYC  = 1_250_000,   // 10 ms
    parameter int SETTLE_CYC = 12_500_000,  // 100 ms
    parameter int POLL_CYC   = 1_250_000,   // 10 ms
    parameter bit LOOPBACK   = 1'b0,         // test builds only: PHY MII loopback at 1000FD
    parameter logic [15:0] RGMIICTL = 16'h00D3,  // D3: TX+RX internal delays, D2: TX delay only
    parameter bit ADV_1000 = 1'b0               // 0: advertise/loop back at 10/100 only
) (
    input  logic        clk,
    input  logic        rst,
    output logic        phy_rst_n,
    output logic        mdc,
    output logic        mdio_o,
    output logic        mdio_t,             // 1 = release (input)
    input  logic        mdio_i,
    output logic [31:0] st_ctrl,            // {..., found, cfg_done, link, speed[1:0], addr[4:0]}
    output logic [31:0] st_id,              // {PHYIDR1, PHYIDR2}
    output logic [31:0] st_stat,            // {BMSR, PHYSTS}
    output logic [31:0] st_cfg              // {RGMIICTL readback, attempts}
);
    // ---------------- bit engine: one 64-bit MDIO frame (32 preamble + 32 command)
    logic [63:0] sh;
    logic [6:0]  bitn;
    logic        busy, go, is_read;
    logic [15:0] rd_data;
    logic [$clog2(DIV)-1:0] div;
    logic        phase;   // 0: MDC low half, 1: MDC high half
    logic [63:0] go_frame;
    logic        go_read;

    always_ff @(posedge clk) begin
        if (rst) begin
            busy <= 0; mdc <= 0; mdio_o <= 1; mdio_t <= 0; div <= 0; phase <= 0;
        end else if (!busy) begin
            mdc <= 0;
            if (go) begin
                busy <= 1; sh <= go_frame; is_read <= go_read; bitn <= 0; div <= 0; phase <= 0;
                mdio_o <= go_frame[63]; mdio_t <= 0;
            end
        end else begin
            if (div == DIV - 1) begin
                div <= 0;
                if (!phase) begin
                    // rising edge of MDC; sample read data bits 48..63
                    mdc <= 1; phase <= 1;
                    if (is_read && bitn >= 7'd48) rd_data <= {rd_data[14:0], mdio_i};
                end else begin
                    mdc <= 0; phase <= 0;
                    if (bitn == 7'd63) begin
                        busy <= 0; mdio_t <= 0; mdio_o <= 1;
                    end else begin
                        bitn <= bitn + 1;
                        sh <= {sh[62:0], 1'b1};
                        mdio_o <= sh[62];
                        // release the line from the turnaround (bit 46) on for reads
                        mdio_t <= is_read && (bitn + 1 >= 7'd46);
                    end
                end
            end else div <= div + 1;
        end
    end

    function automatic logic [63:0] frame(input logic rd, input logic [4:0] pa, input logic [4:0] ra,
                                          input logic [15:0] d);
        return {32'hFFFF_FFFF, 2'b01, rd ? 2'b10 : 2'b01, pa, ra, rd ? 2'b11 : 2'b10, rd ? 16'hFFFF : d};
    endfunction

    // ---------------- sequencer
    typedef enum logic [4:0] {S_RST, S_SETTLE, S_SCAN, S_SCAN_W, S_ID2, S_ID2_W, S_CMD, S_CMD_W,
                              S_POLL_WAIT, S_POLL, S_POLL_W} st_t;
    st_t st;
    logic [31:0] cnt;
    logic [4:0]  addr;
    logic [4:0]  ci;          // command index
    logic        found, cfg_done, dp83867;
    logic [15:0] id1, id2, bmsr, physts, rgctl;
    logic [7:0]  attempts;
    logic        busy_q;
    wire         done_pulse = busy_q && !busy;

    // command list: {is_read, reg, data}; ext writes via REGCR(0x0D)/ADDAR(0x0E)
    localparam int NCMD = 11;
    function automatic logic [21:0] cmd(input logic [4:0] i);
        case (i)
            0:  return {1'b0, 5'h0D, 16'h001F};
            1:  return {1'b0, 5'h0E, 16'h0032};
            2:  return {1'b0, 5'h0D, 16'h401F};
            3:  return {1'b0, 5'h0E, RGMIICTL};
            4:  return {1'b0, 5'h0D, 16'h001F};
            5:  return {1'b0, 5'h0E, 16'h0086};
            6:  return {1'b0, 5'h0D, 16'h401F};
            7:  return {1'b0, 5'h0E, 16'h0077};
            8:  return {1'b0, 5'h04, 16'h0141};   // ANAR: 100FD + 10FD
            9:  return {1'b0, 5'h09, ADV_1000 ? 16'h0200 : 16'h0000};
            default: return {1'b0, 5'h00, LOOPBACK ? (ADV_1000 ? 16'h4140 : 16'h6100) : 16'h1340};
        endcase
    endfunction
    // poll list: BMSR, PHYSTS, ext RGMIICTL readback
    localparam int NPOLL = 6;
    function automatic logic [21:0] pcmd(input logic [4:0] i);
        case (i)
            0: return {1'b1, 5'h01, 16'h0};
            1: return {1'b1, 5'h11, 16'h0};
            2: return {1'b0, 5'h0D, 16'h001F};
            3: return {1'b0, 5'h0E, 16'h0032};
            4: return {1'b0, 5'h0D, 16'h401F};
            default: return {1'b1, 5'h0E, 16'h0};
        endcase
    endfunction

    wire [21:0] cc = cmd(ci);
    wire [21:0] pc = pcmd(ci);

    always_ff @(posedge clk) begin
        go <= 1'b0;
        busy_q <= busy;
        if (rst) begin
            st <= S_RST; cnt <= 0; phy_rst_n <= 0; found <= 0; cfg_done <= 0; addr <= 0;
            id1 <= 0; id2 <= 0; bmsr <= 0; physts <= 0; rgctl <= 0; attempts <= 0; dp83867 <= 0;
        end else begin
            case (st)
            S_RST: begin
                phy_rst_n <= 0;
                if (cnt == RESET_CYC) begin cnt <= 0; phy_rst_n <= 1; st <= S_SETTLE; end
                else cnt <= cnt + 1;
            end
            S_SETTLE: if (cnt == SETTLE_CYC) begin cnt <= 0; addr <= 0; st <= S_SCAN; end
                      else cnt <= cnt + 1;
            S_SCAN: if (!busy && !go) begin
                go_frame <= frame(1'b1, addr, 5'h02, 16'h0); go_read <= 1'b1; go <= 1'b1;
                st <= S_SCAN_W;
            end
            S_SCAN_W: if (done_pulse) begin
                if (rd_data != 16'h0000 && rd_data != 16'hFFFF) begin
                    id1 <= rd_data; found <= 1; dp83867 <= (rd_data == 16'h2000); st <= S_ID2;
                end else if (addr == 5'd31) begin
                    attempts <= attempts + 1; cnt <= 0; st <= S_SETTLE;   // rescan later
                end else begin
                    addr <= addr + 1; st <= S_SCAN;
                end
            end
            S_ID2: if (!busy && !go) begin
                go_frame <= frame(1'b1, addr, 5'h03, 16'h0); go_read <= 1'b1; go <= 1'b1; st <= S_ID2_W;
            end
            S_ID2_W: if (done_pulse) begin id2 <= rd_data; ci <= dp83867 ? 5'd0 : 5'd8; st <= S_CMD; end
            S_CMD: if (!busy && !go) begin
                go_frame <= frame(cc[21], addr, cc[20:16], cc[15:0]);
                go_read <= cc[21]; go <= 1'b1; st <= S_CMD_W;
            end
            S_CMD_W: if (done_pulse) begin
                if (ci == 5'(NCMD - 1)) begin cfg_done <= 1; cnt <= 0; st <= S_POLL_WAIT; end
                else begin ci <= ci + 1; st <= S_CMD; end
            end
            S_POLL_WAIT: if (cnt == POLL_CYC) begin cnt <= 0; ci <= 0; st <= S_POLL; end
                         else cnt <= cnt + 1;
            S_POLL: if (!busy && !go) begin
                go_frame <= frame(pc[21], addr, pc[20:16], pc[15:0]);
                go_read <= pc[21]; go <= 1'b1; st <= S_POLL_W;
            end
            S_POLL_W: if (done_pulse) begin
                if (ci == 0) bmsr <= rd_data;
                if (ci == 1) physts <= rd_data;
                if (ci == 5) rgctl <= rd_data;
                if (ci == 5'(NPOLL - 1)) st <= S_POLL_WAIT;
                else begin ci <= ci + 1; st <= S_POLL; end
            end
            default: st <= S_RST;
            endcase
        end
    end

    // PHYSTS (DP83867): [15:14] speed (10 = 1000), [13] duplex, [10] link
    assign st_ctrl = {20'd0, dp83867, found, cfg_done, physts[10], physts[15:14], addr};
    assign st_id   = {id1, id2};
    assign st_stat = {bmsr, physts};
    assign st_cfg  = {rgctl, 8'd0, attempts};
endmodule
