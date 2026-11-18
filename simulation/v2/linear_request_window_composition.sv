// Focused loader lookahead -> engine request mux -> registered DDR acceptance.
// Includes registered callers; estimates do not include full-design placement.
module linear_request_window_probe #(parameter integer CACHED_LIMIT=0)(
    input logic clk, reset, clear, load_advance, request_advance,
    input logic running, launch, use_lut, lut_requested, port_ready,
    input logic [2:0] opcode,
    input logic [15:0] out_tiles, tile_beats,
    input logic [31:0] linear_address, lut_address,
    input logic [4:0] other_valid,
    input logic [159:0] other_addresses,
    input logic [79:0] other_beats,
    output logic [31:0] accepted_address,
    output logic [15:0] accepted_beats,
    output logic accepted);
    logic [16:0] load_tile, request_tile;
    (* keep=(CACHED_LIMIT!=0 ? "true":"false"), dont_touch=(CACHED_LIMIT!=0 ? "true":"false") *) logic [16:0] window_limit;
    logic running_reg, launch_reg, use_lut_reg, lut_requested_reg, ready_reg;
    logic [2:0] opcode_reg;
    logic [15:0] out_tiles_reg, tile_beats_reg;
    logic [31:0] linear_address_reg, lut_address_reg;
    logic [4:0] other_valid_reg;
    logic [159:0] other_addresses_reg;
    logic [79:0] other_beats_reg;
    always_ff @(posedge clk) begin
        running_reg<=running; launch_reg<=launch; use_lut_reg<=use_lut;
        lut_requested_reg<=lut_requested; ready_reg<=port_ready;
        opcode_reg<=opcode; out_tiles_reg<=out_tiles; tile_beats_reg<=tile_beats;
        linear_address_reg<=linear_address; lut_address_reg<=lut_address;
        other_valid_reg<=other_valid; other_addresses_reg<=other_addresses;
        other_beats_reg<=other_beats;
        if(reset || clear) begin load_tile<=0;request_tile<=0;window_limit<=2;end
        else begin
            if(load_advance) begin load_tile<=load_tile+1'b1;window_limit<=window_limit+1'b1;end
            if(request_advance) request_tile<=request_tile+1'b1;
        end
    end
    logic linear_valid, selected_valid;
    logic [31:0] address, selected_address;
    logic [15:0] beats, selected_beats;
    always_comb begin
        linear_valid=0;address=0;beats=0;
        if(running_reg && !launch_reg) begin
            if(use_lut_reg && !lut_requested_reg) begin
                linear_valid=1;address=lut_address_reg;beats=16;
            end else if(request_tile<17'(out_tiles_reg)
                     && request_tile<(CACHED_LIMIT!=0 ? window_limit : load_tile+17'd2)) begin
                linear_valid=1;address=linear_address_reg;beats=tile_beats_reg;
            end
        end
        selected_valid=0;selected_address=0;selected_beats=0;
        case(opcode_reg)
            0:begin selected_valid=linear_valid;selected_address=address;selected_beats=beats;end
            1,2,3,4,5:begin
                selected_valid=other_valid_reg[opcode_reg-1];
                selected_address=other_addresses_reg[32*(opcode_reg-1)+:32];
                selected_beats=other_beats_reg[16*(opcode_reg-1)+:16];
            end
            default:begin end
        endcase
    end
    always_ff @(posedge clk) begin
        accepted<=!reset && selected_valid && ready_reg;
        if(selected_valid && ready_reg) begin
            accepted_address<=selected_address;accepted_beats<=selected_beats;
        end
    end
endmodule
