// Isolated typed200 integration, ABI 0x54590201; no legacy start/descriptor CSR.
module typed200_encoder #(
    parameter logic [31:0] PROGRAM_ADDRESS=32'd1610613760,
    parameter logic [31:0] IDS_ADDRESS=32'd1645215744,
    parameter logic [31:0] RESULT_ADDRESS=32'd1645219840,
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
    input logic deployment_ready,
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
    assign reset=!reset_n;
    wire run_start,run_done,busy,memory_drained;
    wire [127:0] run_result;
    wire [3:0] perf_events;
    wire [31:0] program_reg=PROGRAM_ADDRESS,ids_reg=IDS_ADDRESS,result_reg=RESULT_ADDRESS;
    wire [15:0] admission_tokens,admission_first,admission_count;
    wire [15:0] owned_tokens,owned_first,owned_count;
    wire [31:0] shape_reg={16'd384,admission_tokens};
    wire [63:0] admitted_session,admitted_request_id,core_session,core_request_id;
    wire core_complete,core_success,owned,fault_seen,done_seen,terminal_valid,quarantined,retired;
    wire live_quiet=!busy && memory_drained;
    // Captured immediately at the original completion boundary, unaffected by
    // memory-response drain or ARM head/publication latency.
    logic [31:0] encoder_clocks,request_clocks;
    always_ff @(posedge clk) begin
        if(reset || run_start) begin encoder_clocks<=0;request_clocks<=0;end
        else if(run_done) begin encoder_clocks<=run_result[31:0];request_clocks<=run_result[63:32];end
    end
    typed_epoch_tracker epoch_inst (
        .clk(clk),.reset(reset),.admitted(run_start),.retired(retired),
        .admission_session(admitted_session),.admission_request_id(admitted_request_id),
        .run_done(run_done),.busy(busy),.memory_drained(memory_drained),.memory_error(memory_error),
        .run_status(run_result[71:64]),.owned(owned),.complete(core_complete),.success(core_success),
        .fault_seen(fault_seen),.done_seen(done_seen),.session(core_session),.request_id(core_request_id)
    );
    typed_intent_axil publication_inst (
        .clk(clk),.reset(reset),.environment_ready(deployment_ready && !memory_error),
        .s_awaddr(s_axil_awaddr),.s_awvalid(s_axil_awvalid),.s_awready(s_axil_awready),
        .s_wdata(s_axil_wdata),.s_wstrb(s_axil_wstrb),.s_wvalid(s_axil_wvalid),.s_wready(s_axil_wready),
        .s_bresp(s_axil_bresp),.s_bvalid(s_axil_bvalid),.s_bready(s_axil_bready),
        .s_araddr(s_axil_araddr),.s_arvalid(s_axil_arvalid),.s_arready(s_axil_arready),
        .s_rdata(s_axil_rdata),.s_rresp(s_axil_rresp),.s_rvalid(s_axil_rvalid),.s_rready(s_axil_rready),
        .core_complete(core_complete),.core_success(core_success && deployment_ready),.live_quiet(live_quiet),
        .core_session(core_session),.core_request_id(core_request_id),
        .admitted(run_start),.admitted_session(admitted_session),.admitted_request_id(admitted_request_id),
        .encoder_clocks(encoder_clocks),.request_clocks(request_clocks),
        .terminal_valid(terminal_valid),.terminal_quarantined(quarantined),.retired(retired),
        .admission_tokens(admission_tokens),.admission_first(admission_first),.admission_count(admission_count),
        .owned_tokens(owned_tokens),.owned_first(owned_first),.owned_count(owned_count)
    );
    assign irq=terminal_valid;

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
        .response_error(memory_error), .drained(memory_drained)
    );

endmodule
