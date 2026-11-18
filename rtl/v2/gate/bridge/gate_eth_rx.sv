// GMII receive: strip preamble/SFD, write the frame (DA .. FCS) into a dual-clock byte
// FIFO, check the FCS, and push a descriptor {good, length} when the frame ends.
// A frame that would not fit is dropped whole at its SFD (counted, never partially written).
module gate_eth_rx #(
    parameter int AW = 12,
    parameter int MAXLEN = 1522
) (
    input  logic        rxc,
    input  logic        rrst_rx,      // reset synchronous to rxc
    input  logic [7:0]  rxd,
    input  logic        rx_dv,
    input  logic        rx_er,
    input  logic        rx_ce,        // byte strobe (every cycle at 1000 Mb/s)
    // core-domain read side
    input  logic        clk,
    input  logic        rst,
    input  logic        d_ren,
    output logic [7:0]  d_rdata,
    output logic        d_rempty,
    input  logic        q_ren,
    output logic [11:0] q_len,
    output logic        q_good,
    output logic        q_rempty,
    // rxc-domain counters (sampled by the status block through synchronizers)
    output logic [31:0] cnt_frames,
    output logic [31:0] cnt_bad,
    output logic [31:0] cnt_overflow
);
    import gate_eth_pkg::*;
    typedef enum logic [1:0] {IDLE, PRE, DATA, SKIP} st_t;
    st_t st;
    logic [31:0] crc;
    logic [11:0] len;
    logic        err;
    logic        wen, qwen;
    logic [7:0]  wdata;
    logic [12:0] qwdata;
    logic [AW:0] wfree;
    logic [4:0]  qwfree;

    gate_async_fifo #(.W(8), .AW(AW)) u_data (
        .wclk(rxc), .wrst(rrst_rx), .wen(wen), .wdata(wdata), .wfree(wfree),
        .rclk(clk), .rrst(rst), .ren(d_ren), .rdata(d_rdata), .rempty(d_rempty));
    gate_async_fifo #(.W(13), .AW(4)) u_desc (
        .wclk(rxc), .wrst(rrst_rx), .wen(qwen), .wdata(qwdata), .wfree(qwfree),
        .rclk(clk), .rrst(rst), .ren(q_ren), .rdata({q_good, q_len}), .rempty(q_rempty));

    always_ff @(posedge rxc) begin
        wen <= 1'b0;
        qwen <= 1'b0;
        if (rrst_rx) begin
            st <= IDLE; cnt_frames <= 0; cnt_bad <= 0; cnt_overflow <= 0;
        end else if (rx_ce) begin
            case (st)
            IDLE: if (rx_dv && rxd == 8'h55) st <= PRE;
            PRE: begin
                if (!rx_dv) st <= IDLE;
                else if (rxd == 8'hD5) begin
                    if (wfree > (AW + 1)'(MAXLEN + 2) && qwfree > 5'd1) begin
                        st <= DATA; crc <= 32'hFFFF_FFFF; len <= 0; err <= 1'b0;
                    end else begin
                        st <= SKIP; cnt_overflow <= cnt_overflow + 1;
                    end
                end else if (rxd != 8'h55) st <= IDLE;
            end
            DATA: begin
                if (rx_dv) begin
                    if (len < 12'(MAXLEN)) begin
                        wen <= 1'b1; wdata <= rxd;
                        crc <= crc_byte(crc, rxd);
                        len <= len + 1;
                    end else err <= 1'b1;
                    if (rx_er) err <= 1'b1;
                end else begin
                    qwen <= 1'b1;
                    qwdata <= {(crc == CRC_RESIDUE) && !err && len >= 12'd64, len};
                    cnt_frames <= cnt_frames + 1;
                    if (!((crc == CRC_RESIDUE) && !err && len >= 12'd64)) cnt_bad <= cnt_bad + 1;
                    st <= IDLE;
                end
            end
            SKIP: if (!rx_dv) st <= IDLE;
            default: st <= IDLE;
            endcase
        end
    end
endmodule
