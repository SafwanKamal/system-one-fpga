// The v2 memory port on top of the Xilinx 7-series MIG native (UI) interface.
//
// Every v2 block that touches external memory uses the same small burst
// interface, so that only this adapter changes between boards:
//
//   request   *_request_valid / _ready, _address (byte address, aligned to one
//             beat), _beats (number of DATA_WIDTH-bit beats, >= 1)
//   read data read_valid / read_ready, read_data, read_last (last beat of a request)
//   write     write_valid / write_ready, write_data (beats of the current write request)
//
// On the KR260 the same port maps one-to-one onto an AXI4 master into the Zynq
// PS DDR (request -> AR/AW with ARLEN = beats - 1, read data -> R, write -> W);
// that adapter is a separate file, the compute side does not change.
//
// Nexys 4 DDR: MIG configured from ip/v2/nexys4ddr/mig_ddr2.prj (Digilent's
// out-of-box settings): MT47H64M16HR-25E, 16-bit DDR2 at 300 MHz (600 MT/s), 4:1
// PHY, so ui_clk is 75 MHz and one UI command moves one 128-bit beat (burst of 8 x
// 16 bits). app_addr counts 16-bit words, so it is the byte address shifted right by
// one and advances by 8 per beat. Peak 1.2 GB/s.
//
// Reads: the MIG returns read data with no backpressure, in request order
// (Ordering = Strict). A read command is only issued when the read FIFO has room
// for its beat counting every beat still in flight, so read_ready may be held low
// indefinitely without losing data.
//
// Writes: command and data are presented together, only in cycles where both
// app_rdy and app_wdf_rdy are high, which the MIG user guide allows.
//
// Commands of one request are issued before the next request starts, but read
// requests overlap: up to REQUEST_QUEUE_DEPTH reads may be issued while earlier
// ones are still being delivered, so the DDR stays busy across request boundaries.
// A write starts only when no read data is outstanding.
module mig_memory_port #(
    parameter integer ADDRESS_WIDTH = 27,     // bytes: 128 MiB
    parameter integer DATA_WIDTH = 128,
    parameter integer BEATS_WIDTH = 16,
    parameter integer READ_FIFO_DEPTH = 64,
    parameter integer REQUEST_QUEUE_DEPTH = 4
) (
    input logic clk,                          // MIG ui_clk
    input logic reset,                        // MIG ui_clk_sync_rst

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

    // ---- MIG native user interface
    output logic [ADDRESS_WIDTH-1:0] app_addr,
    output logic [2:0] app_cmd,
    output logic app_en,
    output logic [DATA_WIDTH-1:0] app_wdf_data,
    output logic app_wdf_end,
    output logic [DATA_WIDTH/8-1:0] app_wdf_mask,
    output logic app_wdf_wren,
    input logic [DATA_WIDTH-1:0] app_rd_data,
    input logic app_rd_data_end,
    input logic app_rd_data_valid,
    input logic app_rdy,
    input logic app_wdf_rdy
);

    localparam logic [2:0] COMMAND_WRITE = 3'b000;
    localparam logic [2:0] COMMAND_READ = 3'b001;
    localparam integer WORDS_PER_BEAT = DATA_WIDTH / 16;    // app_addr step per beat
    localparam integer FIFO_COUNT_WIDTH = $clog2(READ_FIFO_DEPTH) + 1;

    typedef enum logic [1:0] {
        IDLE,
        READ,
        WRITE
    } state_t;

    state_t state_reg, state_next;

    logic [ADDRESS_WIDTH-1:0] word_address_reg, word_address_next;
    logic [BEATS_WIDTH-1:0] commands_left_reg, commands_left_next;
    logic [FIFO_COUNT_WIDTH-1:0] in_flight_reg, in_flight_next;

    // beats of the read request being delivered, for read_last; the lengths of
    // requests issued but not yet delivered wait in length_queue
    logic [BEATS_WIDTH-1:0] deliver_left_reg, deliver_left_next;
    logic [BEATS_WIDTH-1:0] length_head, deliver_now;
    logic length_full, length_empty, length_push, length_pop;
    logic [$clog2(REQUEST_QUEUE_DEPTH):0] length_count;

    logic fifo_full, fifo_empty;
    logic [FIFO_COUNT_WIDTH-1:0] fifo_count;
    logic fifo_pop;

    wire issue_read = (state_reg == READ) && (commands_left_reg != '0) && app_rdy
                      && ((fifo_count + in_flight_reg) < READ_FIFO_DEPTH[FIFO_COUNT_WIDTH-1:0]);
    wire issue_write = (state_reg == WRITE) && (commands_left_reg != '0) && app_rdy
                       && app_wdf_rdy && write_valid;


    sync_fifo #(
        .WIDTH (DATA_WIDTH),
        .DEPTH (READ_FIFO_DEPTH)
    ) read_fifo_inst (
        .clk          (clk),
        .reset        (reset),
        .write_enable (app_rd_data_valid),
        .write_data   (app_rd_data),
        .full         (fifo_full),
        .read_enable  (fifo_pop),
        .read_data    (read_data),
        .empty        (fifo_empty),
        .count        (fifo_count)
    );

    sync_fifo #(
        .WIDTH (BEATS_WIDTH),
        .DEPTH (REQUEST_QUEUE_DEPTH)
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

    assign read_valid = !fifo_empty;
    assign fifo_pop = read_valid && read_ready;
    // beats left in the request the head of the read FIFO belongs to
    assign deliver_now = (deliver_left_reg != '0) ? deliver_left_reg : length_head;
    assign read_last = (deliver_now == 1);
    assign length_pop = fifo_pop && (deliver_left_reg == '0);


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= IDLE;
            word_address_reg <= '0;
            commands_left_reg <= '0;
            in_flight_reg <= '0;
            deliver_left_reg <= '0;
        end else begin
            state_reg <= state_next;
            word_address_reg <= word_address_next;
            commands_left_reg <= commands_left_next;
            in_flight_reg <= in_flight_next;
            deliver_left_reg <= deliver_left_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        word_address_next = word_address_reg;
        commands_left_next = commands_left_reg;
        in_flight_next = in_flight_reg + (issue_read ? 1'b1 : 1'b0)
                         - (app_rd_data_valid ? 1'b1 : 1'b0);
        deliver_left_next = fifo_pop ? deliver_now - 1'b1 : deliver_left_reg;
        length_push = 1'b0;

        read_request_ready = 1'b0;
        write_request_ready = 1'b0;

        case (state_reg)
            IDLE: begin
                if (read_request_valid && !length_full) begin
                    read_request_ready = 1'b1;
                    length_push = 1'b1;
                    word_address_next = read_request_address >> 1;
                    commands_left_next = read_request_beats;
                    state_next = READ;
                end else if (write_request_valid && !read_request_valid && length_empty
                             && deliver_left_reg == '0 && in_flight_reg == '0) begin
                    write_request_ready = 1'b1;
                    word_address_next = write_request_address >> 1;
                    commands_left_next = write_request_beats;
                    state_next = WRITE;
                end
            end

            READ: begin
                if (issue_read) begin
                    word_address_next = word_address_reg + WORDS_PER_BEAT[ADDRESS_WIDTH-1:0];
                    commands_left_next = commands_left_reg - 1'b1;
                    if (commands_left_reg == 1) begin
                        state_next = IDLE;
                    end
                end
            end

            WRITE: begin
                if (issue_write) begin
                    word_address_next = word_address_reg + WORDS_PER_BEAT[ADDRESS_WIDTH-1:0];
                    commands_left_next = commands_left_reg - 1'b1;
                    if (commands_left_reg == 1) begin
                        state_next = IDLE;
                    end
                end
            end

            default: begin
                state_next = IDLE;
            end
        endcase
    end

    assign app_addr = word_address_reg;
    assign app_cmd = (state_reg == WRITE) ? COMMAND_WRITE : COMMAND_READ;
    assign app_en = issue_read || issue_write;
    assign app_wdf_data = write_data;
    assign app_wdf_wren = issue_write;
    assign app_wdf_end = issue_write;
    assign app_wdf_mask = '0;
    assign write_ready = issue_write;

endmodule
