// Streaming IPv4 header + TCP checksum verifier for the agent gate.
//
// Watches the byte stream of one Ethernet frame (no preamble/FCS, optional 802.1Q tag) and, one cycle after the
// last byte, reports whether the IPv4 header checksum and the TCP checksum (pseudo-header + IP-delimited segment,
// odd length padded with zero) are valid.  Bit-exact with frames_v3.py / gate_v2.csum16 for frames the parser
// accepts; for frames the parser rejects the outputs are don't-care (the core ignores them).
module gate_csum (
    input  logic       clk,
    input  logic       rst,
    input  logic       s_valid,
    input  logic [7:0] s_data,
    input  logic       s_last,
    output logic       c_valid,    // pulses one cycle after the last byte
    output logic       ip_ok,
    output logic       tcp_ok
);
    logic [15:0] pos;
    logic [7:0]  b12;
    logic [15:0] l3, hlen, total;
    logic        l3_known;
    logic [31:0] ipsum, tcpsum;
    logic [7:0]  ip_hi, tcp_hi;
    logic        tcp_odd;

    wire [15:0] idx    = pos - l3;                       // byte index within the IP header / datagram
    wire        in_ip  = l3_known && pos >= l3 && (pos == l3 || idx < hlen);
    wire        in_tcp = l3_known && pos >= l3 + hlen && pos < l3 + total && pos > l3 + 3;
    wire [15:0] tidx   = pos - (l3 + hlen);

    function automatic logic [15:0] fold(input logic [31:0] x);
        logic [31:0] a;
        a = {16'd0, x[15:0]} + {16'd0, x[31:16]};
        a = {16'd0, a[15:0]} + {16'd0, a[31:16]};
        return a[15:0];
    endfunction

    logic [31:0] ip_f, tcp_f;
    logic [15:0] tcp_len_f;

    always_ff @(posedge clk) begin
        c_valid <= 1'b0;
        if (rst) begin
            pos <= 0; l3_known <= 1'b0; ipsum <= 0; tcpsum <= 0; tcp_odd <= 1'b0;
            hlen <= 16'd20; total <= 16'hFFFF;
        end else if (s_valid) begin
            if (pos == 16'd12) b12 <= s_data;
            if (pos == 16'd13) begin
                l3 <= (b12 == 8'h81 && s_data == 8'h00) ? 16'd18 : 16'd14;
                l3_known <= 1'b1;
            end
            // IPv4 header: bytes [l3, l3+hlen)
            if (l3_known && pos == l3) hlen <= {10'd0, s_data[3:0], 2'b00};
            if (l3_known && pos == l3 + 16'd2) total[15:8] <= s_data;
            if (l3_known && pos == l3 + 16'd3) total[7:0]  <= s_data;
            if (in_ip) begin
                if (!idx[0]) ip_hi <= s_data;
                else begin
                    ipsum <= ipsum + {16'd0, ip_hi, s_data};
                    // source and destination address words (header bytes 12..19) belong to the pseudo-header
                    if (idx >= 16'd13 && idx <= 16'd19) tcpsum <= tcpsum + {16'd0, ip_hi, s_data};
                end
            end
            // TCP segment: bytes [l3+hlen, l3+total)
            if (in_tcp) begin
                if (!tidx[0]) begin tcp_hi <= s_data; tcp_odd <= 1'b1; end
                else begin tcpsum <= tcpsum + {16'd0, tcp_hi, s_data}; tcp_odd <= 1'b0; end
            end
            if (s_last) begin
                pos <= 0; l3_known <= 1'b0;
                // finalise next cycle from the registered sums (see below)
                c_valid <= 1'b1;
            end else begin
                pos <= pos + 16'd1;
            end
        end
        if (c_valid) begin
            ipsum <= 0; tcpsum <= 0; tcp_odd <= 1'b0; hlen <= 16'd20; total <= 16'hFFFF;
        end
    end

    // result computed from the sums as they stand when c_valid is high (before they are cleared)
    always_comb begin
        tcp_len_f = total - hlen;
        ip_f  = ipsum;
        tcp_f = tcpsum + 32'h0000_0006 + {16'd0, tcp_len_f} + (tcp_odd ? {16'd0, tcp_hi, 8'h00} : 32'd0);
        ip_ok  = (fold(ip_f)  == 16'hFFFF);
        tcp_ok = (fold(tcp_f) == 16'hFFFF);
    end
endmodule
