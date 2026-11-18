// Replays every recorded go/no-go decision through gate_rules and checks the rule code
// against the Python integer specification (bit-exact, including which rule fired).
module gate_rules_tb;
    logic clk = 0;
    always #4 clk = ~clk;

    logic        in_valid = 0;
    logic [7:0]  fc;
    logic [15:0] addr;
    logic [2:0]  nvals;
    logic        nvals_over;
    logic [15:0] vals [4];
    logic signed [15:0] lvl10;
    logic [15:0] act [4];
    logic [31:0] t_ms;
    logic [31:0] starts [4];
    logic        out_valid, allow;
    logic [3:0]  rule_id;

    gate_rules dut (.*);

    int fd, n, errors, count, r;
    int unsigned f_fc, f_addr, f_n, f_over, v0, v1, v2, v3, f_lvl, a0, a1, a2, a3, f_t, s0, s1, s2, s3, exp_rule;
    string path;

    initial begin
        if (!$value$plusargs("vectors=%s", path)) path = "gate_rules_vectors.txt";
        fd = $fopen(path, "r");
        if (fd == 0) begin $display("cannot open %s", path); $finish; end
        errors = 0; count = 0;
        while (!$feof(fd)) begin
            r = $fscanf(fd, "%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                        f_fc, f_addr, f_n, f_over, v0, v1, v2, v3, f_lvl, a0, a1, a2, a3,
                        f_t, s0, s1, s2, s3, exp_rule);
            if (r != 19) break;
            @(negedge clk);
            fc = f_fc[7:0]; addr = f_addr[15:0]; nvals = f_n[2:0]; nvals_over = f_over[0];
            vals[0] = v0[15:0]; vals[1] = v1[15:0]; vals[2] = v2[15:0]; vals[3] = v3[15:0];
            lvl10 = f_lvl[15:0];
            act[0] = a0[15:0]; act[1] = a1[15:0]; act[2] = a2[15:0]; act[3] = a3[15:0];
            t_ms = f_t; starts[0] = s0; starts[1] = s1; starts[2] = s2; starts[3] = s3;
            in_valid = 1;
            @(posedge clk); #1;
            in_valid = 0;
            if (rule_id !== exp_rule[3:0] || allow !== (exp_rule == 0)) begin
                errors++;
                if (errors < 10) $display("MISMATCH #%0d fc=%0d addr=%0d got rule %0d exp %0d", count, f_fc, f_addr, rule_id, exp_rule);
            end
            count++;
        end
        $display("gate_rules_tb: %0d vectors, %0d mismatches", count, errors);
        $finish;
    end
endmodule
