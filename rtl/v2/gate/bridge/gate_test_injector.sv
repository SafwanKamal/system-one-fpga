// TEST BUILDS ONLY.  Replays a ROM of Ethernet frames into a port's transmitter once,
// after `start`.  With the PHYs in MII loopback, each frame returns on the same port's
// receiver, crosses the gate, leaves through the other port, loops back again and is
// judged in the other direction.  The production bridge never instantiates this module.
//
// ROM layout (bytes): per frame a 4-byte header {flags, len_hi, len_lo, 0} followed by
// len frame bytes (DA .. payload, no FCS).  flags[0] = port (0 = A, 1 = B),
// flags[1] = 1 for a correct FCS (0 = deliberately corrupted), flags = 8'hFF ends the list.
module gate_test_injector #(
    parameter int    ROM_BYTES = 32768,
    parameter string ROM_FILE  = "gate_inject_rom.hex",
    parameter int    GAP_CYC   = 12500          // 100 us between frames
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        start,
    input  logic        ce,           // byte strobe of the selected port's transmitter (>= 2 cycles apart)
    output logic        active,
    output logic        port,
    output logic [7:0]  txd,
    output logic        txen,
    output logic [31:0] n_sent,
    output logic        done
);
    import gate_eth_pkg::*;
    (* rom_style = "block" *) logic [7:0] rom [ROM_BYTES];
    initial $readmemh(ROM_FILE, rom);

    logic [14:0] addr;
    logic [7:0]  rd;
    always_ff @(posedge clk) rd <= rom[addr];

    typedef enum logic [3:0] {I_WAIT, I_H0, I_H1, I_H2, I_H3, I_PRE, I_DATA, I_FCS, I_GAP, I_DONE} st_t;
    st_t st;
    logic [7:0]  flags;
    logic [10:0] len, i;
    logic [3:0]  pc;
    logic [31:0] crc, fcs;
    logic [15:0] gap;
    // addressing: `addr` points at the byte to send next; rd = rom[addr] one cycle later.
    // Requires ce at most every other cycle (true at 10/100 Mb/s; 1000 Mb/s needs a prefetch).

    always_ff @(posedge clk) begin
        if (rst) begin
            st <= I_WAIT; addr <= 0; active <= 0; txen <= 0; n_sent <= 0; done <= 0;
        end else begin
            case (st)
            I_WAIT: if (start) begin addr <= 0; st <= I_H0; end
            I_H0: begin addr <= addr + 1; st <= I_H1; end                // rd = rom[0] next
            I_H1: begin
                flags <= rd; addr <= addr + 1;
                if (rd == 8'hFF) st <= I_DONE; else st <= I_H2;
            end
            I_H2: begin len[10:8] <= rd[2:0]; addr <= addr + 1; st <= I_H3; end
            I_H3: begin len[7:0] <= rd; addr <= addr + 1; st <= I_PRE; pc <= 0; active <= 1; port <= flags[0]; end
            I_PRE: if (ce) begin
                // addr already points at the first frame byte (H + 4)
                txen <= 1; txd <= (pc == 4'd7) ? 8'hD5 : 8'h55;
                if (pc == 4'd7) begin st <= I_DATA; i <= 0; crc <= 32'hFFFF_FFFF; end
                pc <= pc + 1;
            end
            I_DATA: if (ce) begin
                txd <= rd; crc <= crc_byte(crc, rd);
                addr <= addr + 1;
                if (i == len - 11'd1) begin st <= I_FCS; pc <= 0; end
                i <= i + 1;
            end
            I_FCS: if (ce) begin
                fcs = ~crc;
                if (!flags[1]) fcs = fcs ^ 32'h0000_0100;
                txd <= fcs[8*pc[1:0] +: 8];
                if (pc == 4'd3) begin st <= I_GAP; gap <= 0; end
                pc <= pc + 1;
            end
            I_GAP: begin
                if (ce) txen <= 0;
                active <= (gap < 16'd400);           // keep the mux until the last byte has left
                if (gap == 16'(GAP_CYC)) begin n_sent <= n_sent + 1; st <= I_H0; end
                gap <= gap + 1;
            end
            I_DONE: begin done <= 1; active <= 0; txen <= 0; end
            default: st <= I_DONE;
            endcase
        end
    end
endmodule
