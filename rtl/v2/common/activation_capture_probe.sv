// Isolated seven-buffer inference probe. Mirrors mapped address + URAM +
// physical selector latency from encoder_layer; it is not the production layer.
module activation_capture_probe #(
    parameter integer CAPTURE = 0,
    parameter integer SMALL_DEPTH = 8192,
    parameter integer AW = $clog2(2*SMALL_DEPTH)
) (
    input logic clk,
    input logic [AW-1:0] read_address [0:6],
    input logic [2:0] physical_select [0:3],
    input logic [6:0] write_enable,
    input logic [AW-1:0] write_address,
    input logic [127:0] write_data,
    input logic [15:0] write_byte_enable,
    output logic [127:0] port_data [0:3]
);
    logic [127:0] physical_data [0:6];
    logic [2:0] select_d1 [0:3], select_d2 [0:3], select_d3 [0:3];
    always_ff @(posedge clk) begin
        for (int p = 0; p < 4; p++) begin
            select_d1[p] <= physical_select[p];
            select_d2[p] <= select_d1[p];
            select_d3[p] <= select_d2[p];
        end
    end
    for (genvar b = 0; b < 7; b++) begin : gen_buffer
        localparam integer DEPTH = (b == 5 || b == 6) ? 2*SMALL_DEPTH : SMALL_DEPTH;
        localparam integer BAW = $clog2(DEPTH);
        logic [BAW-1:0] address_reg;
        always_ff @(posedge clk) address_reg <= BAW'(read_address[b]);
        activation_buffer #(.DEPTH(DEPTH), .PIPELINED_URAM(1)) memory_inst (
            .clk(clk), .read_address(address_reg), .read_data(physical_data[b]),
            .write_enable(write_enable[b]), .write_address(BAW'(write_address)),
            .write_data(write_data), .write_byte_enable(write_byte_enable));
    end
    if (CAPTURE != 0) begin : gen_local
        activation_read_capture local_capture (.clk(clk), .physical_data(physical_data),
            .physical_select(select_d3), .port_data(port_data));
    end else begin : gen_baseline
        always_ff @(posedge clk)
            for (int p = 0; p < 4; p++)
                port_data[p] <= select_d3[p] < 7 ? physical_data[select_d3[p]] : '0;
    end
endmodule
