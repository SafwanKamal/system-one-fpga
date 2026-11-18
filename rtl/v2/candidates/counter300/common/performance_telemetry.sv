// One-cycle diagnostic input cut. Never feeds back into AXI/core control.
// Events are evaluated in their original cycle, including outstanding-beat tests.
// The last sample drains on the first idle edge; snapshot_ready then goes high.
module performance_telemetry (
    input logic clk, reset, clear, busy,
    input logic arvalid, arready, rvalid, rready,
    input logic [7:0] arlen,
    input logic wvalid, wready,
    input logic write_request_valid, write_request_ready,
    input logic [15:0] write_request_beats,
    input logic write_valid, write_ready,
    input logic [3:0] core_events,
    output logic [31:0] counts [0:9],
    output logic pending, snapshot_ready
);
    logic [31:0] read_due, write_due;
    (* DONT_TOUCH = "TRUE" *) logic signed [9:0] read_delta_reg;
    (* DONT_TOUCH = "TRUE" *) logic signed [16:0] write_delta_reg;
    logic [9:0] sampled_events;
    logic sampled_read_wait, sampled_write_wait;
    logic [9:0] events;
    assign snapshot_ready = !busy && !pending;
    always_comb begin
        events = sampled_events;
        events[1] = read_due != 0 && sampled_read_wait;
        events[9] = write_due != 0 && sampled_write_wait;
    end
    always_ff @(posedge clk) begin
        if (reset || clear) begin
            pending <= 0;
            read_due <= 0; write_due <= 0;
            read_delta_reg <= 0; write_delta_reg <= 0;
            sampled_events <= 0;
            sampled_read_wait <= 0; sampled_write_wait <= 0;
            for (int c=0; c<10; c++) counts[c] <= 0;
        end else begin
            pending <= busy;
            if (busy) begin
                read_delta_reg <= ((arvalid && arready) ? 10'({1'b0,arlen}) + 10'd1 : 10'd0)
                                  - ((rvalid && rready) ? 10'd1 : 10'd0);
                write_delta_reg <= ((write_request_valid && write_request_ready) ? 17'({1'b0,write_request_beats}) : 17'd0)
                                   - ((write_valid && write_ready) ? 17'd1 : 17'd0);
                sampled_events <= {1'b0, arvalid && arready, wvalid && wready,
                    core_events[0], core_events[1], core_events[3], core_events[2],
                    rvalid && !rready, 1'b0, rvalid && rready};
                sampled_read_wait <= rready && !rvalid;
                sampled_write_wait <= write_ready && !write_valid;
            end
            if (pending) begin
                read_due <= read_due + 32'(read_delta_reg);
                write_due <= write_due + 32'(write_delta_reg);
                for (int c=0; c<10; c++)
                    if (events[c]) counts[c] <= counts[c] + 1'b1;
            end
        end
    end
endmodule
