// KR260 (Zynq UltraScale+ K26): the v2 encoder as a PL block for the processing
// system. The ARM cores are the host: they keep the DDR image in a reserved region
// of the PS DDR4, write a request's token ids next to it, start the encoder through
// AXI4-Lite registers and read X back from DDR; the heads run on the ARM (heads on
// the host, as on the Nexys 4 DDR, src/sysone/v2/host_heads.py).
//
//   s_axil  (from M_AXI_HPM0_LPD or _FPD)  control registers below
//   m_axi   (to S_AXI_HP0..3_FPD)           the encoder's memory port (axi_memory_port)
//   irq     (to pl_ps_irq0)                 high while a finished run is unacknowledged
//
// Registers (32-bit, byte offsets):
//   0x00  CONTROL   write 1: start a run with the descriptor below (ignored while busy);
//                   write 2: clear DONE / irq.  read: bit 0 busy, bit 1 done
//   0x04  STATUS    run status (0 ok, bit 0 sequencer error, bit 1 bad descriptor)
//   0x08  ENCODER_CLOCKS    clocks from EMBED to END
//   0x0C  REQUEST_CLOCKS    clocks for the whole run (ids in, encoder, X out)
//   0x10  STOPPED_AT        the instruction the sequencer stopped at (END when ok)
//   0x14  ID        "SYS2" (0x53595332)
//   0x18  BUILD     {TILE_OUT[7:0], MAX_TOKENS[7:0], MAX_HIDDEN / 16 [7:0], DRAIN_LANES[7:0]}
//   0x20  PROGRAM   program address (the image's program section)
//   0x24  SHAPE     {hidden H [31:16], tokens n [15:0]}
//   0x28  IDS       token-ids address (n UINT16)
//   0x2C  RESULT    result address (X, n x H INT8)
// The descriptor is the memory link's RUN descriptor (memory_protocol.py), so the
// same encoder_system runs it; addresses are PS physical addresses below 4 GiB.
module kr260_encoder #(
    parameter integer TILE_OUT = 32,
    parameter integer ATTENTION_LANES = TILE_OUT,
    parameter integer MAC_INPUT_REGISTERS = 0,
    parameter integer PIPELINED_DOT = 0,
    parameter integer EXP_TABLE_IN_BRAM = 0,
    parameter integer PIPELINED_URAM = 0,
    parameter integer LOCAL_READ_CAPTURE = 0,
    parameter integer INCREMENTAL_SOURCE_ROW = 0,
    parameter integer LINEAR_ACCUMULATORS_IN_BRAM = 0,
    parameter integer FABRIC_CONTEXT_CAPTURE = 0,
    parameter integer FABRIC_SCORE_DISTANCE = 0,
    parameter integer CACHED_REQUEST_WINDOW = 0,
    parameter integer DSP_EMBED_ROW_ADDRESS = 0,
    parameter integer PROBABILITY_INPUT_CAPTURE = 0,
    parameter integer LOCAL_EMBED_CONTROLS = 0,
    parameter integer PROBABILITY_PIPELINE = 0,
    parameter integer PIPELINED_DRAIN_SELECT = 0,
    parameter integer REGISTERED_FIFO_FLAGS = 0,
    parameter integer STREAM_RESULTS = 0,
    parameter integer PERF_COUNTERS = 0,
    parameter integer LOCAL_QUERY_REGISTERS = 0,
    parameter integer LOCAL_ACCUMULATOR_CONTROLS = 0,
    parameter integer MAX_TOKENS = 128,
    parameter integer MAX_HEAD_DIM = 64,
    parameter integer MAX_HIDDEN = 384,
    parameter integer DRAIN_LANES = 4,                 // requantisers in LINEAR's drain
    parameter integer NORM_LANES = 4,                  // LAYERNORM output elements per clock
    parameter integer ADDRESS_WIDTH = 40,              // AXI address of the PS DDR
    parameter integer BEATS_WIDTH = 16
) (
    input logic clk,                                   // pl_clk0
    input logic reset_n,                               // pl_resetn0 (via proc_sys_reset)

    // AXI4-Lite slave (control)
    input logic [7:0] s_axil_awaddr,
    input logic s_axil_awvalid,
    output logic s_axil_awready,
    input logic [31:0] s_axil_wdata,
    input logic [3:0] s_axil_wstrb,
    input logic s_axil_wvalid,
    output logic s_axil_wready,
    output logic [1:0] s_axil_bresp,
    output logic s_axil_bvalid,
    input logic s_axil_bready,
    input logic [7:0] s_axil_araddr,
    input logic s_axil_arvalid,
    output logic s_axil_arready,
    output logic [31:0] s_axil_rdata,
    output logic [1:0] s_axil_rresp,
    output logic s_axil_rvalid,
    input logic s_axil_rready,

    // AXI4 master (memory)
    output logic [ADDRESS_WIDTH-1:0] m_axi_araddr,
    output logic [7:0] m_axi_arlen,
    output logic [2:0] m_axi_arsize,
    output logic [1:0] m_axi_arburst,
    output logic m_axi_arvalid,
    input logic m_axi_arready,
    input logic [127:0] m_axi_rdata,
    input logic [1:0] m_axi_rresp,
    input logic m_axi_rlast,
    input logic m_axi_rvalid,
    output logic m_axi_rready,
    output logic [ADDRESS_WIDTH-1:0] m_axi_awaddr,
    output logic [7:0] m_axi_awlen,
    output logic [2:0] m_axi_awsize,
    output logic [1:0] m_axi_awburst,
    output logic m_axi_awvalid,
    input logic m_axi_awready,
    output logic [127:0] m_axi_wdata,
    output logic [15:0] m_axi_wstrb,
    output logic m_axi_wlast,
    output logic m_axi_wvalid,
    input logic m_axi_wready,
    input logic [1:0] m_axi_bresp,
    input logic m_axi_bvalid,
    output logic m_axi_bready,

    output logic irq,
    output logic memory_error                          // sticky: an AXI error response
);

    logic reset;
    assign reset = !reset_n;

    // ------------------------------------------------------------- registers
    logic [31:0] program_reg, shape_reg, ids_reg, result_reg;
    logic done_reg, run_start;
    logic run_done, busy;
    logic contract_start, contract_valid, contract_active, contract_ready, contract_quarantined;
    logic [2:0] contract_outcome;
    logic [31:0] contract_age, contract_budget;
    wire contract_ack = write_fire && s_axil_awaddr[7:2] == 0 && s_axil_wdata[1];
    deadline_supervisor contract_inst(.clk, .reset, .start(contract_start),
        .budget_cycles(contract_budget), .ack(contract_ack), .core_done(run_done),
        .core_fault(run_result[71:64] != 0), .ready(contract_ready),
        .active(contract_active), .result_valid(contract_valid),
        .quarantined(contract_quarantined), .outcome(contract_outcome), .elapsed(contract_age));
    logic [127:0] run_result, result_latch;
    logic [3:0] perf_events;
    logic [31:0] perf_counts [0:9];
    // Counters reset on each accepted RUN and freeze at completion. Events may
    // overlap; these are diagnostics, not a partition of request clocks.
    if (PERF_COUNTERS != 0) begin : gen_performance
        logic [31:0] read_due;
        logic [31:0] write_due;
        logic [9:0] events;
        always_comb begin
            events[0] = m_axi_rvalid && m_axi_rready;
            events[1] = read_due != 0 && m_axi_rready && !m_axi_rvalid;
            events[2] = m_axi_rvalid && !m_axi_rready;
            events[3] = perf_events[2]; // LINEAR MAC input issue
            events[4] = perf_events[3]; // ATTENTION MAC input issue
            events[5] = perf_events[1]; // LINEAR waiting for weight bank
            events[6] = perf_events[0]; // LINEAR waiting for accumulator drain
            events[7] = m_axi_wvalid && m_axi_wready;
            events[8] = m_axi_arvalid && m_axi_arready;
            events[9] = write_due != 0 && write_ready && !write_valid;
        end
        always_ff @(posedge clk) begin
            if (reset || run_start) begin
                read_due <= 0;
                write_due <= 0;
                for (int c = 0; c < 10; c++) perf_counts[c] <= 0;
            end else if (busy) begin
                read_due <= read_due + ((m_axi_arvalid && m_axi_arready) ? 32'(m_axi_arlen)+1 : 0)
                                     - ((m_axi_rvalid && m_axi_rready) ? 1 : 0);
                write_due <= write_due + ((write_request_valid && write_request_ready) ? 32'(write_request_beats) : 0)
                                       - ((write_valid && write_ready) ? 1 : 0);
                for (int c = 0; c < 10; c++)
                    if (events[c]) perf_counts[c] <= perf_counts[c] + 1'b1;
            end
        end
    end else begin : gen_no_performance
        for (genvar c = 0; c < 10; c++) assign perf_counts[c] = 0;
    end

    // write channel: take address and data together
    logic write_fire;
    assign s_axil_awready = s_axil_awvalid && s_axil_wvalid && !s_axil_bvalid;
    assign s_axil_wready = s_axil_awready;
    assign write_fire = s_axil_awready;
    assign s_axil_bresp = 2'b00;
    assign s_axil_rresp = 2'b00;

    always_ff @(posedge clk) begin
        if (reset) begin
            s_axil_bvalid <= 1'b0;
            program_reg <= '0;
            shape_reg <= '0;
            ids_reg <= '0;
            result_reg <= '0;
            done_reg <= 1'b0;
            run_start <= 1'b0;
            contract_start <= 1'b0;
            contract_budget <= 32'hffffffff;
            result_latch <= '0;
        end else begin
            run_start <= 1'b0;
            contract_start <= 1'b0;
            if (s_axil_bvalid && s_axil_bready) s_axil_bvalid <= 1'b0;
            if (run_done && !contract_quarantined) begin
                done_reg <= 1'b1;
                result_latch <= run_result;
            end
            if (write_fire) begin
                s_axil_bvalid <= 1'b1;
                case (s_axil_awaddr[7:2])
                    6'h00: begin
                        if (s_axil_wdata[0] && !busy && !run_start && contract_ready) begin
                            contract_start <= 1'b1;
                            run_start <= contract_budget != 0;
                            done_reg <= 1'b0;
                        end
                        if (s_axil_wdata[1]) done_reg <= 1'b0;
                    end
                    6'h08: program_reg <= s_axil_wdata;
                    6'h09: shape_reg <= s_axil_wdata;
                    6'h0A: ids_reg <= s_axil_wdata;
                    6'h0B: result_reg <= s_axil_wdata;
                    6'h1A: if (!busy && contract_ready && !run_start) contract_budget <= s_axil_wdata;
                    default: ;
                endcase
            end
        end
    end

    // read channel
    always_ff @(posedge clk) begin
        if (reset) begin
            s_axil_rvalid <= 1'b0;
            s_axil_rdata <= '0;
        end else begin
            if (s_axil_rvalid && s_axil_rready) s_axil_rvalid <= 1'b0;
            if (s_axil_arvalid && s_axil_arready) begin
                s_axil_rvalid <= 1'b1;
                case (s_axil_araddr[7:2])
                    6'h00: s_axil_rdata <= {30'd0, done_reg, busy || run_start};
                    6'h01: s_axil_rdata <= {24'd0, result_latch[71:64]};
                    6'h02: s_axil_rdata <= result_latch[31:0];
                    6'h03: s_axil_rdata <= result_latch[63:32];
                    6'h04: s_axil_rdata <= {16'd0, result_latch[95:80]};
                    6'h05: s_axil_rdata <= 32'h5359_5332;
                    6'h06: s_axil_rdata <= {8'(TILE_OUT), 8'(MAX_TOKENS), 8'(MAX_HIDDEN / 16), 8'(DRAIN_LANES)};
                    // Versioned capability word: bit0 counters, bit1 streaming,
                    // bit2 local queries, bit3 pipelined UltraRAM.
                    6'h07: s_axil_rdata <= ((FABRIC_CONTEXT_CAPTURE!=0) ? 32'h53800000 :
                         ((CACHED_REQUEST_WINDOW!=0 || DSP_EMBED_ROW_ADDRESS!=0) ? 32'h53600000 :
                         ((FABRIC_SCORE_DISTANCE!=0 || ATTENTION_LANES!=TILE_OUT) ? 32'h535a0000 :
                         ((INCREMENTAL_SOURCE_ROW!=0 || LINEAR_ACCUMULATORS_IN_BRAM!=0) ? 32'h53594000 :
                         ((PROBABILITY_INPUT_CAPTURE!=0 || LOCAL_EMBED_CONTROLS!=0) ? 32'h53591000 :
                         ((PROBABILITY_PIPELINE!=0 || PIPELINED_DRAIN_SELECT!=0) ? 32'h53590400 : 32'h53590100)))))) | 32'(PERF_COUNTERS != 0)
                        | (32'(STREAM_RESULTS != 0) << 1) | (32'(LOCAL_QUERY_REGISTERS != 0) << 2)
                        | (32'(LOCAL_ACCUMULATOR_CONTROLS != 0) << 4)
                        | (32'(PIPELINED_DOT != 0) << 5)
                        | (32'(PIPELINED_URAM != 0) << 3)
                        | (32'(LOCAL_READ_CAPTURE != 0) << 6)
                        | (32'(REGISTERED_FIFO_FLAGS != 0) << 7)
                        | (32'(PROBABILITY_PIPELINE != 0) << 8)
                        | (32'(PIPELINED_DRAIN_SELECT != 0) << 9)
                        | (32'(PROBABILITY_INPUT_CAPTURE != 0) << 10)
                        | (32'(LOCAL_EMBED_CONTROLS != 0) << 11)
                        | (32'(INCREMENTAL_SOURCE_ROW != 0) << 12)
                        | (32'(LINEAR_ACCUMULATORS_IN_BRAM != 0) << 13)
                        | (32'(ATTENTION_LANES != TILE_OUT) << 14)
                        | (32'(FABRIC_SCORE_DISTANCE != 0) << 15)
                        | (32'(CACHED_REQUEST_WINDOW != 0) << 16)
                        | (32'(DSP_EMBED_ROW_ADDRESS != 0) << 17)
                        | (32'(FABRIC_CONTEXT_CAPTURE != 0) << 18);
                    6'h18: s_axil_rdata <= {21'd0, contract_outcome, 4'd0, contract_ready, contract_quarantined, contract_active, contract_valid};
                    6'h19: s_axil_rdata <= contract_age;
                    6'h1A: s_axil_rdata <= contract_budget;
                    6'h1B: s_axil_rdata <= 32'h53595431; // independent deadline-outcome ABI
                    6'h08: s_axil_rdata <= program_reg;
                    6'h09: s_axil_rdata <= shape_reg;
                    6'h0A: s_axil_rdata <= ids_reg;
                    6'h0B: s_axil_rdata <= result_reg;
                    6'h0C: s_axil_rdata <= perf_counts[0];
                    6'h0D: s_axil_rdata <= perf_counts[1];
                    6'h0E: s_axil_rdata <= perf_counts[2];
                    6'h0F: s_axil_rdata <= perf_counts[3];
                    6'h10: s_axil_rdata <= perf_counts[4];
                    6'h11: s_axil_rdata <= perf_counts[5];
                    6'h12: s_axil_rdata <= perf_counts[6];
                    6'h13: s_axil_rdata <= perf_counts[7];
                    6'h14: s_axil_rdata <= perf_counts[8];
                    6'h15: s_axil_rdata <= perf_counts[9];
                    default: s_axil_rdata <= '0;
                endcase
            end
        end
    end
    assign s_axil_arready = !s_axil_rvalid;
    assign irq = done_reg || contract_valid;

    // ------------------------------------------------------------- encoder
    logic read_request_valid, read_request_ready, read_valid, read_ready, read_last;
    logic write_request_valid, write_request_ready, write_valid, write_ready;
    logic [ADDRESS_WIDTH-1:0] read_request_address, write_request_address;
    logic [BEATS_WIDTH-1:0] read_request_beats, write_request_beats;
    logic [127:0] read_data, write_data;

    encoder_system #(
        .TILE_OUT(TILE_OUT),
        .ATTENTION_LANES(ATTENTION_LANES),
        .MAC_INPUT_REGISTERS(MAC_INPUT_REGISTERS),
        .PIPELINED_DOT(PIPELINED_DOT),
        .EXP_TABLE_IN_BRAM(EXP_TABLE_IN_BRAM),
        .PIPELINED_URAM(PIPELINED_URAM),
        .LOCAL_READ_CAPTURE(LOCAL_READ_CAPTURE),
        .INCREMENTAL_SOURCE_ROW(INCREMENTAL_SOURCE_ROW),
        .LINEAR_ACCUMULATORS_IN_BRAM(LINEAR_ACCUMULATORS_IN_BRAM),
        .FABRIC_CONTEXT_CAPTURE(FABRIC_CONTEXT_CAPTURE),
        .FABRIC_SCORE_DISTANCE(FABRIC_SCORE_DISTANCE),
        .CACHED_REQUEST_WINDOW(CACHED_REQUEST_WINDOW),
        .DSP_EMBED_ROW_ADDRESS(DSP_EMBED_ROW_ADDRESS),
        .PROBABILITY_INPUT_CAPTURE(PROBABILITY_INPUT_CAPTURE),
        .PROBABILITY_PIPELINE(PROBABILITY_PIPELINE),
        .LOCAL_EMBED_CONTROLS(LOCAL_EMBED_CONTROLS),
        .PIPELINED_DRAIN_SELECT(PIPELINED_DRAIN_SELECT),
        .STREAM_RESULTS(STREAM_RESULTS),
        .LOCAL_QUERY_REGISTERS(LOCAL_QUERY_REGISTERS),
        .LOCAL_ACCUMULATOR_CONTROLS(LOCAL_ACCUMULATOR_CONTROLS),
        .MAX_TOKENS(MAX_TOKENS),
        .MAX_HEAD_DIM(MAX_HEAD_DIM),
        .MAX_HIDDEN(MAX_HIDDEN),
        .DRAIN_LANES(DRAIN_LANES),
        .NORM_LANES(NORM_LANES),
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .BEATS_WIDTH(BEATS_WIDTH)
    ) encoder_system_inst (
        .perf_events(perf_events),
        .clk(clk),
        .reset(reset),
        .run_start(run_start),
        .run_descriptor({result_reg, ids_reg, shape_reg, program_reg}),
        .run_done(run_done),
        .run_result(run_result),
        .busy(busy),
        .read_request_valid(read_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(read_request_address),
        .read_request_beats(read_request_beats),
        .read_valid(read_valid),
        .read_ready(read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid),
        .write_request_ready(write_request_ready),
        .write_request_address(write_request_address),
        .write_request_beats(write_request_beats),
        .write_valid(write_valid),
        .write_ready(write_ready),
        .write_data(write_data)
    );

    axi_memory_port #(
        .ADDRESS_WIDTH(ADDRESS_WIDTH),
        .DATA_WIDTH(128),
        .BEATS_WIDTH(BEATS_WIDTH),
        .REGISTERED_REQUESTS(PIPELINED_DOT),
        .REGISTERED_FIFO_FLAGS(REGISTERED_FIFO_FLAGS)
    ) memory_port_inst (
        .clk(clk),
        .reset(reset),
        .read_request_valid(read_request_valid),
        .read_request_ready(read_request_ready),
        .read_request_address(read_request_address),
        .read_request_beats(read_request_beats),
        .read_valid(read_valid),
        .read_ready(read_ready),
        .read_data(read_data),
        .read_last(read_last),
        .write_request_valid(write_request_valid),
        .write_request_ready(write_request_ready),
        .write_request_address(write_request_address),
        .write_request_beats(write_request_beats),
        .write_valid(write_valid),
        .write_ready(write_ready),
        .write_data(write_data),
        .m_axi_araddr(m_axi_araddr), .m_axi_arlen(m_axi_arlen), .m_axi_arsize(m_axi_arsize),
        .m_axi_arburst(m_axi_arburst), .m_axi_arvalid(m_axi_arvalid), .m_axi_arready(m_axi_arready),
        .m_axi_rdata(m_axi_rdata), .m_axi_rresp(m_axi_rresp), .m_axi_rlast(m_axi_rlast),
        .m_axi_rvalid(m_axi_rvalid), .m_axi_rready(m_axi_rready),
        .m_axi_awaddr(m_axi_awaddr), .m_axi_awlen(m_axi_awlen), .m_axi_awsize(m_axi_awsize),
        .m_axi_awburst(m_axi_awburst), .m_axi_awvalid(m_axi_awvalid), .m_axi_awready(m_axi_awready),
        .m_axi_wdata(m_axi_wdata), .m_axi_wstrb(m_axi_wstrb), .m_axi_wlast(m_axi_wlast),
        .m_axi_wvalid(m_axi_wvalid), .m_axi_wready(m_axi_wready),
        .m_axi_bresp(m_axi_bresp), .m_axi_bvalid(m_axi_bvalid), .m_axi_bready(m_axi_bready),
        .response_error(memory_error)
    );

endmodule
