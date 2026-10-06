// The v2 memory port as an AXI4 master: for the KR260 (Zynq UltraScale+ K26), whose
// external memory is the PS DDR4 reached through an S_AXI_HP port, and for any
// other AXI-based platform.
//
// Same port as mig_memory_port.sv on the Nexys 4 DDR, so nothing above it changes:
//   request   *_request_valid / _ready, _address (bytes, beat-aligned), _beats
//   read data read_valid / read_ready, read_data, read_last (end of a request)
//   write     write_valid / write_ready, write_data
//
// A request is split into AXI bursts of at most 256 beats that never cross a 4 KiB
// boundary (AXI4 rules). Read bursts are issued back to back, up to
// MAX_OUTSTANDING_READS in flight, and R data is passed straight through: AXI read
// data has its own RREADY, so no reservation FIFO is needed here. read_last is
// generated per request, not per burst. Writes: AW for each burst, then its W
// beats, then the B response is counted; a write request completes when all its
// responses are back. Fixed ID 0, INCR bursts, full-width beats, no strobes masked.
module axi_memory_port #(
    parameter integer ADDRESS_WIDTH = 40,
    parameter integer DATA_WIDTH = 128,
    parameter integer BEATS_WIDTH = 16,
    parameter integer MAX_OUTSTANDING_READS = 8
) (
    input logic clk,
    input logic reset,

    // ---- v2 memory port
    input logic read_request_valid,
    output logic read_request_ready,
    input logic [ADDRESS_WIDTH-1:0] read_request_address,
    input logic [BEATS_WIDTH-1:0] read_request_beats,

    output logic read_valid,
    input logic read_ready,
    output logic [DATA_WIDTH-1:0] read_data,
    output logic read_last,

    input logic write_request_valid,
    output logic write_request_ready,
    input logic [ADDRESS_WIDTH-1:0] write_request_address,
    input logic [BEATS_WIDTH-1:0] write_request_beats,

    input logic write_valid,
    output logic write_ready,
    input logic [DATA_WIDTH-1:0] write_data,

    // ---- AXI4 master
    output logic [ADDRESS_WIDTH-1:0] m_axi_araddr,
    output logic [7:0] m_axi_arlen,
    output logic [2:0] m_axi_arsize,
    output logic [1:0] m_axi_arburst,
    output logic m_axi_arvalid,
    input logic m_axi_arready,
    input logic [DATA_WIDTH-1:0] m_axi_rdata,
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
    output logic [DATA_WIDTH-1:0] m_axi_wdata,
    output logic [DATA_WIDTH/8-1:0] m_axi_wstrb,
    output logic m_axi_wlast,
    output logic m_axi_wvalid,
    input logic m_axi_wready,
    input logic [1:0] m_axi_bresp,
    input logic m_axi_bvalid,
    output logic m_axi_bready,

    output logic response_error            // sticky: any RRESP/BRESP other than OKAY
);

    localparam integer BEAT_BYTES = DATA_WIDTH / 8;
    localparam integer BEAT_SHIFT = $clog2(BEAT_BYTES);
    localparam integer PAGE_BEATS = 4096 / BEAT_BYTES;              // beats per 4 KiB
    localparam integer OUTSTANDING_WIDTH = $clog2(MAX_OUTSTANDING_READS + 1);

    // ------------------------------------------------------------- burst sizing
    // beats in the next burst: min(left, 256, beats to the 4 KiB boundary)
    function automatic logic [8:0] burst_beats(input logic [ADDRESS_WIDTH-1:0] address,
                                               input logic [BEATS_WIDTH-1:0] left);
        logic [BEATS_WIDTH:0] to_page;
        logic [BEATS_WIDTH:0] n;
        to_page = PAGE_BEATS - ((address >> BEAT_SHIFT) & (PAGE_BEATS - 1));
        n = left;
        if (to_page < n) n = to_page;
        if (n > 256) n = 256;
        return n[8:0];
    endfunction

    // ------------------------------------------------------------------- reads
    typedef enum logic [0:0] {
        READ_IDLE,
        READ_ISSUE
    } read_state_t;

    read_state_t read_state_reg, read_state_next;
    logic [ADDRESS_WIDTH-1:0] read_address_reg, read_address_next;
    logic [BEATS_WIDTH-1:0] read_issue_left_reg, read_issue_left_next;
    logic [OUTSTANDING_WIDTH-1:0] read_outstanding_reg, read_outstanding_next;

    // per-request delivery count for read_last; lengths of accepted requests queue up
    logic [BEATS_WIDTH-1:0] deliver_left_reg, deliver_left_next;
    logic [BEATS_WIDTH-1:0] length_head, deliver_now;
    logic length_full, length_empty, length_push, length_pop;
    logic [2:0] length_count;

    wire [8:0] read_burst = burst_beats(read_address_reg, read_issue_left_reg);
    wire read_burst_done = m_axi_rvalid && m_axi_rready && m_axi_rlast;

    sync_fifo #(
        .WIDTH (BEATS_WIDTH),
        .DEPTH (4)
    ) length_queue_inst (
        .clk          (clk),
        .reset        (reset),
        .write_enable (length_push),
        .write_data   (read_request_beats),
        .full         (length_full),
        .read_enable  (length_pop),
        .read_data    (length_head),
        .empty        (length_empty),
        .count        (length_count)
    );

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            read_state_reg <= READ_IDLE;
            read_address_reg <= '0;
            read_issue_left_reg <= '0;
            read_outstanding_reg <= '0;
            deliver_left_reg <= '0;
        end else begin
            read_state_reg <= read_state_next;
            read_address_reg <= read_address_next;
            read_issue_left_reg <= read_issue_left_next;
            read_outstanding_reg <= read_outstanding_next;
            deliver_left_reg <= deliver_left_next;
        end
    end

    wire read_beat = m_axi_rvalid && m_axi_rready;
    assign deliver_now = (deliver_left_reg != '0) ? deliver_left_reg : length_head;
    assign length_pop = read_beat && (deliver_left_reg == '0);

    always_comb begin
        read_state_next = read_state_reg;
        read_address_next = read_address_reg;
        read_issue_left_next = read_issue_left_reg;
        read_outstanding_next = read_outstanding_reg
                                + ((m_axi_arvalid && m_axi_arready) ? 1'b1 : 1'b0)
                                - (read_burst_done ? 1'b1 : 1'b0);
        deliver_left_next = read_beat ? deliver_now - 1'b1 : deliver_left_reg;
        read_request_ready = 1'b0;
        length_push = 1'b0;
        m_axi_arvalid = 1'b0;

        case (read_state_reg)
            READ_IDLE: begin
                if (read_request_valid && !length_full) begin
                    read_request_ready = 1'b1;
                    length_push = 1'b1;
                    read_address_next = read_request_address;
                    read_issue_left_next = read_request_beats;
                    read_state_next = READ_ISSUE;
                end
            end

            READ_ISSUE: begin
                m_axi_arvalid = (read_outstanding_reg < MAX_OUTSTANDING_READS[OUTSTANDING_WIDTH-1:0]);
                if (m_axi_arvalid && m_axi_arready) begin
                    read_address_next = read_address_reg + (ADDRESS_WIDTH'(read_burst) << BEAT_SHIFT);
                    read_issue_left_next = read_issue_left_reg - BEATS_WIDTH'(read_burst);
                    if (read_issue_left_reg == BEATS_WIDTH'(read_burst)) begin
                        read_state_next = READ_IDLE;
                    end
                end
            end

            default: begin
                read_state_next = READ_IDLE;
            end
        endcase
    end

    assign m_axi_araddr = read_address_reg;
    assign m_axi_arlen = 8'(read_burst - 1'b1);
    assign m_axi_arsize = 3'(BEAT_SHIFT);
    assign m_axi_arburst = 2'b01;                      // INCR
    assign read_valid = m_axi_rvalid;
    assign m_axi_rready = read_ready;
    assign read_data = m_axi_rdata;
    assign read_last = (deliver_now == 1);

    // ------------------------------------------------------------------ writes
    typedef enum logic [1:0] {
        WRITE_IDLE,
        WRITE_ADDRESS,
        WRITE_DATA,
        WRITE_RESPONSES
    } write_state_t;

    write_state_t write_state_reg, write_state_next;
    logic [ADDRESS_WIDTH-1:0] write_address_reg, write_address_next;
    logic [BEATS_WIDTH-1:0] write_left_reg, write_left_next;       // beats not yet in a burst
    logic [8:0] burst_left_reg, burst_left_next;                    // beats left in this burst
    logic [BEATS_WIDTH-1:0] responses_due_reg, responses_due_next;
    logic response_error_reg, response_error_next;

    wire [8:0] write_burst = burst_beats(write_address_reg, write_left_reg);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            write_state_reg <= WRITE_IDLE;
            write_address_reg <= '0;
            write_left_reg <= '0;
            burst_left_reg <= '0;
            responses_due_reg <= '0;
            response_error_reg <= 1'b0;
        end else begin
            write_state_reg <= write_state_next;
            write_address_reg <= write_address_next;
            write_left_reg <= write_left_next;
            burst_left_reg <= burst_left_next;
            responses_due_reg <= responses_due_next;
            response_error_reg <= response_error_next;
        end
    end

    always_comb begin
        write_state_next = write_state_reg;
        write_address_next = write_address_reg;
        write_left_next = write_left_reg;
        burst_left_next = burst_left_reg;
        responses_due_next = responses_due_reg - ((m_axi_bvalid && m_axi_bready) ? 1'b1 : 1'b0);
        response_error_next = response_error_reg
                              || (m_axi_bvalid && m_axi_bready && m_axi_bresp != 2'b00)
                              || (m_axi_rvalid && m_axi_rready && m_axi_rresp != 2'b00);
        write_request_ready = 1'b0;
        m_axi_awvalid = 1'b0;
        m_axi_wvalid = 1'b0;
        write_ready = 1'b0;

        case (write_state_reg)
            WRITE_IDLE: begin
                // a write starts only when no read is in progress
                if (write_request_valid && !read_request_valid && read_state_reg == READ_IDLE
                    && length_empty && deliver_left_reg == '0) begin
                    write_request_ready = 1'b1;
                    write_address_next = write_request_address;
                    write_left_next = write_request_beats;
                    write_state_next = WRITE_ADDRESS;
                end
            end

            WRITE_ADDRESS: begin
                m_axi_awvalid = 1'b1;
                if (m_axi_awready) begin
                    burst_left_next = write_burst;
                    responses_due_next = responses_due_next + 1'b1;
                    write_state_next = WRITE_DATA;
                end
            end

            WRITE_DATA: begin
                m_axi_wvalid = write_valid;
                write_ready = m_axi_wready;
                if (write_valid && m_axi_wready) begin
                    write_address_next = write_address_reg + BEAT_BYTES;
                    write_left_next = write_left_reg - 1'b1;
                    burst_left_next = burst_left_reg - 1'b1;
                    if (burst_left_reg == 1) begin
                        write_state_next = (write_left_reg == 1) ? WRITE_RESPONSES : WRITE_ADDRESS;
                    end
                end
            end

            WRITE_RESPONSES: begin
                if (responses_due_next == '0) begin
                    write_state_next = WRITE_IDLE;
                end
            end

            default: begin
                write_state_next = WRITE_IDLE;
            end
        endcase
    end

    assign m_axi_awaddr = write_address_reg;
    assign m_axi_awlen = 8'(write_burst - 1'b1);
    assign m_axi_awsize = 3'(BEAT_SHIFT);
    assign m_axi_awburst = 2'b01;
    assign m_axi_wdata = write_data;
    assign m_axi_wstrb = '1;
    assign m_axi_wlast = (burst_left_reg == 1);
    assign m_axi_bready = 1'b1;
    assign response_error = response_error_reg;

endmodule
