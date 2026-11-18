// Isolated actual score-BRAM/subtract/DSP composition; no engine integration.
// Only the preservation attribute differs; pipeline equations/cycles are equal.
module score_distance_ooc #(parameter integer FABRIC_DISTANCE=0)(
    input logic clk, write,
    input logic [6:0] write_address, read_address,
    input logic [703:0] write_data, maximum,
    input logic [16:0] multiplier,
    output logic [1247:0] product
);
    (* ram_style="block" *) logic [703:0] score_memory [0:127];
    logic [703:0] score_word, maximum_reg;
    logic [16:0] multiplier_reg;
    always_ff @(posedge clk) begin
        if(write) score_memory[write_address]<=write_data;
        score_word<=score_memory[read_address];
        maximum_reg<=maximum;
        multiplier_reg<=multiplier;
    end
    for(genvar lane=0;lane<32;lane++) begin: gen_lane
        logic [38:0] product_reg;
        if(FABRIC_DISTANCE!=0) begin: gen_fabric
            (* keep="true", dont_touch="true" *) logic [21:0] distance_reg;
            always_ff @(posedge clk) begin
                distance_reg<=22'($signed(maximum_reg[22*lane+:22])-$signed(score_word[22*lane+:22]));
                product_reg<=distance_reg*multiplier_reg;
            end
        end else begin: gen_default
            logic [21:0] distance_reg;
            always_ff @(posedge clk) begin
                distance_reg<=22'($signed(maximum_reg[22*lane+:22])-$signed(score_word[22*lane+:22]));
                product_reg<=distance_reg*multiplier_reg;
            end
        end
        assign product[39*lane+:39]=product_reg;
    end
endmodule
