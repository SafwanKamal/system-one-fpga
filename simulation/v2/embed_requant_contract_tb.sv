// Arithmetic-only prerequisite for a future embedding timing optimization.
// Does not verify start capture, stream alignment, DDR stalls or whole-engine equivalence.
module embed_requant_contract_tb;
    import encoder_pkg::*;
    int unsigned cases = 0;
    int unsigned seed = 32'h5318e012;

    task automatic check(
        input logic signed [25:0] wp, pp,
        input logic [5:0] ws, ps,
        input logic signed [31:0] type_value
    );
        logic signed [25:0] old_w, old_p, bias_w, bias_p, new_w, new_p;
        logic signed [16:0] old_wterm, old_pterm;
        logic signed [15:0] new_wterm, new_pterm;
        logic signed [33:0] old_sum;
        logic signed [32:0] new_sum;
        logic signed [15:0] old_out, new_out;
        // Original stage-three expression, including 26-bit modular bias/addition.
        old_w = ws == 0 ? wp : (wp + (26'sd1 <<< (ws - 6'd1))) >>> ws;
        old_p = ps == 0 ? pp : (pp + (26'sd1 <<< (ps - 6'd1))) >>> ps;
        old_wterm = 17'(clamp(64'(old_w), -64'sd32767, 64'sd32767));
        old_pterm = 17'(clamp(64'(old_p), -64'sd32767, 64'sd32767));
        old_sum = 34'(old_wterm) + 34'(old_pterm) + 34'(type_value);
        old_out = 16'(clamp(64'(old_sum), -64'sd32767, 64'sd32767));

        // Proposed instruction-constant bias and reduced-width signed clamps/sum.
        bias_w = ws == 0 ? 26'sd0 : 26'sd1 <<< (ws - 6'd1);
        bias_p = ps == 0 ? 26'sd0 : 26'sd1 <<< (ps - 6'd1);
        new_w = ws == 0 ? wp : (wp + bias_w) >>> ws;
        new_p = ps == 0 ? pp : (pp + bias_p) >>> ps;
        new_wterm = new_w > 26'sd32767 ? 16'sd32767 :
                    new_w < -26'sd32767 ? -16'sd32767 : 16'(new_w);
        new_pterm = new_p > 26'sd32767 ? 16'sd32767 :
                    new_p < -26'sd32767 ? -16'sd32767 : 16'(new_p);
        new_sum = 33'(new_wterm) + 33'(new_pterm) + 33'(type_value);
        new_out = new_sum > 33'sd32767 ? 16'sd32767 :
                  new_sum < -33'sd32767 ? -16'sd32767 : 16'(new_sum);
        if (old_w != new_w || old_p != new_p || old_wterm != 17'(new_wterm) ||
            old_pterm != 17'(new_pterm) || old_sum != 34'(new_sum) || old_out != new_out)
            $fatal(1, "Arithmetic mismatch wp=%0d pp=%0d ws=%0d ps=%0d type=%0d", wp, pp, ws, ps, type_value);
        cases++;
    endtask

    initial begin
        logic signed [25:0] products [0:15];
        logic signed [31:0] types [0:7];
        int unsigned ignored;
        products = '{-26'sd33554432,26'sd33554431,-26'sd16777088,26'sd16646017,
                     -26'sd32769,-26'sd32768,-26'sd32767,-26'sd1,26'sd0,26'sd1,
                     26'sd32766,26'sd32767,26'sd32768,26'sd32769,26'sd65535,-26'sd65535};
        types = '{32'sh80000000,32'sh7fffffff,-32'sd65534,32'sd65534,
                  -32'sd32767,32'sd32767,-32'sd1,32'sd0};
        ignored = $urandom(seed);
        for (int ws=0; ws<64; ws++) begin
            for (int ps=0; ps<64; ps++)
                foreach (products[i]) foreach (types[j])
                    check(products[i],products[15-i],6'(ws),6'(ps),types[j]);
            for (int n=0; n<4096; n++)
                check(26'($urandom()),26'($urandom()),6'(ws),6'($urandom()),32'($urandom()));
        end
        $display("PASS embedding arithmetic contract: %0d cases; all 64 shifts, signed 26-bit extrema and INT32 types", cases);
        $finish;
    end
endmodule
