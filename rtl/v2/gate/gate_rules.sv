// Agent command gate: rule engine.
// Bit-exact implementation of src/sysone/v2/agent_gate/intspec.py::decide().
// One registered decision per cycle (fully pipelined, latency 1).
//
// Rule codes: 0 pass, 1 fc_denied, 2 fc_not_holding_write, 3 unmapped, 4 range,
//             5 R1, 6 R7, 7 R2, 8 R3, 9 R4_low, 10 R4_drain, 11 R5, 12 R6.
module gate_rules (
    input  logic        clk,
    input  logic        in_valid,
    input  logic [7:0]  fc,
    input  logic [15:0] addr,
    input  logic [2:0]  nvals,        // 0..4 register values present
    input  logic        nvals_over,   // request carried more than 4 values
    input  logic [15:0] vals [4],
    input  logic signed [15:0] lvl10,
    input  logic [15:0] act [4],      // inlet, pump, outlet, heater (as forwarded)
    input  logic [31:0] t_ms,
    input  logic [31:0] starts [4],   // last pump-start times, 32'hFFFF_FFFF = empty
    output logic        out_valid,
    output logic [3:0]  rule_id,
    output logic        allow
);
    localparam int INLET = 0, PUMP = 1, OUTLET = 2, HEATER = 3;

    function automatic logic [3:0] decide();
        logic [15:0] a [4];
        logic [3:0]  names;
        logic [16:0] end_addr;
        logic [15:0] need;
        logic signed [17:0] diff;
        logic [2:0]  recent;
        logic        any_range;
        logic        pump_or_out;
        logic [31:0] age;

        if (!(fc == 8'd1 || fc == 8'd2 || fc == 8'd3 || fc == 8'd4 ||
              fc == 8'd5 || fc == 8'd6 || fc == 8'd15 || fc == 8'd16)) return 4'd1;
        if (fc <= 8'd4) return 4'd0;
        if (!(fc == 8'd6 || fc == 8'd16)) return 4'd2;
        end_addr = {1'b0, addr} + {14'd0, nvals};
        if (nvals_over || nvals == 3'd0 || end_addr > 17'd4) return 4'd3;
        any_range = 1'b0;
        for (int i = 0; i < 4; i++)
            if (i < nvals && vals[i] > 16'd100) any_range = 1'b1;
        if (any_range) return 4'd4;

        for (int k = 0; k < 4; k++) begin
            a[k] = act[k];
            names[k] = 1'b0;
        end
        for (int i = 0; i < 4; i++) begin
            for (int k = 0; k < 4; k++) begin
                if (i < nvals && (addr[2:0] + i[2:0]) == k[2:0]) begin
                    a[k] = vals[i];
                    names[k] = 1'b1;
                end
            end
        end
        pump_or_out = names[PUMP] | names[OUTLET];

        if (a[PUMP] > 0 && pump_or_out) begin
            if (lvl10 < 16'sd150) return 4'd5;
            if (a[PUMP] > 16'd50 && lvl10 < 16'sd400) return 4'd6;
        end
        if (a[PUMP] > 0) begin
            need = (a[PUMP] > 16'd50) ? a[PUMP] : 16'd15;
            if (a[OUTLET] < need) return 4'd7;
        end
        if (names[OUTLET] && act[PUMP] > 0) begin
            diff = $signed({2'b00, a[OUTLET]}) - $signed({2'b00, act[OUTLET]});
            if (diff > 18'sd30 || diff < -18'sd30) return 4'd8;
        end
        if (a[HEATER] > 0) begin
            if (lvl10 < 16'sd350) return 4'd9;
            if (lvl10 < 16'sd400 && pump_or_out &&
                (a[PUMP] > act[PUMP] || a[OUTLET] > act[OUTLET])) return 4'd10;
        end
        if (names[INLET]) begin
            if (a[INLET] > 0 && lvl10 >= 16'sd850) return 4'd11;
            if (a[INLET] >= 16'd50 && lvl10 >= 16'sd750) return 4'd11;
        end
        if (names[PUMP] && act[PUMP] == 0 && a[PUMP] > 0) begin
            recent = 3'd0;
            for (int s = 0; s < 4; s++) begin
                age = t_ms - starts[s];
                if (starts[s] != 32'hFFFF_FFFF && age <= 32'd60000) recent = recent + 3'd1;
            end
            if (recent >= 3'd3) return 4'd12;
        end
        return 4'd0;
    endfunction

    always_ff @(posedge clk) begin
        out_valid <= in_valid;
        if (in_valid) begin
            rule_id <= decide();
            allow   <= (decide() == 4'd0);
        end
    end
endmodule
