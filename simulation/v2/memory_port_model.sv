// Behavioural model of the v2 memory port, read side, for encoder simulations.
//
// Memory is initialised from a hex file of 128-bit words (one per line, word 0 =
// byte address 0), e.g. a DDR image written by scripts/v2/encoder_vectors.py.
// Up to QUEUE_DEPTH read requests are accepted; each starts after LATENCY clocks
// and then delivers its beats in order, with read_valid and read_request_ready
// randomly withheld STALL_PERCENT of the time (seeded, deterministic). The model
// checks the port rules: aligned addresses, beats >= 1, inside the memory, and
// that read data is not dropped (the consumer may hold read_ready low).
module memory_port_model #(
    parameter integer WORDS = 1 << 21,               // 32 MiB
    parameter integer ADDRESS_WIDTH = 27,
    parameter integer BEATS_WIDTH = 16,
    parameter integer QUEUE_DEPTH = 4,
    parameter integer LATENCY = 12,
    parameter integer STALL_PERCENT = 20,
    parameter string IMAGE = "image.hex"
) (
    input logic clk,
    input logic reset,

    input logic read_request_valid,
    output logic read_request_ready,
    input logic [ADDRESS_WIDTH-1:0] read_request_address,
    input logic [BEATS_WIDTH-1:0] read_request_beats,

    output logic read_valid,
    input logic read_ready,
    output logic [127:0] read_data,
    output logic read_last,

    output longint beats_delivered,
    output longint requests_accepted
);

    logic [127:0] memory [0:WORDS-1];

    initial begin
        $readmemh(IMAGE, memory);
    end

    logic [ADDRESS_WIDTH-1:0] queue_address [0:QUEUE_DEPTH-1];
    logic [BEATS_WIDTH-1:0] queue_beats [0:QUEUE_DEPTH-1];
    int queue_count;
    int head;
    int beat;
    int wait_count;
    logic stall_request, stall_data;

    always_ff @(posedge clk) begin
        stall_request <= ($urandom % 100) < STALL_PERCENT;
        stall_data <= ($urandom % 100) < STALL_PERCENT;
    end

    assign read_request_ready = !reset && (queue_count < QUEUE_DEPTH) && !stall_request;
    assign read_valid = !reset && (queue_count > 0) && (wait_count == 0) && !stall_data;
    assign read_data = memory[(queue_address[head] >> 4) + beat];
    assign read_last = (beat == int'(queue_beats[head]) - 1);

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            queue_count <= 0;
            head <= 0;
            beat <= 0;
            wait_count <= LATENCY;
            beats_delivered <= 0;
            requests_accepted <= 0;
        end else begin
            int count;
            count = queue_count;
            if (read_valid && read_ready) begin
                beats_delivered <= beats_delivered + 1;
                if (read_last) begin
                    head <= (head + 1) % QUEUE_DEPTH;
                    beat <= 0;
                    wait_count <= LATENCY;
                    count = count - 1;
                end else begin
                    beat <= beat + 1;
                end
            end else if (queue_count > 0 && wait_count > 0) begin
                wait_count <= wait_count - 1;
            end
            if (read_request_valid && read_request_ready) begin
                if (read_request_address[3:0] != 0 || read_request_beats == 0
                        || (read_request_address >> 4) + read_request_beats > WORDS) begin
                    $fatal(1, "memory_port_model: bad request address %h beats %0d",
                           read_request_address, read_request_beats);
                end
                queue_address[(head + queue_count) % QUEUE_DEPTH] <= read_request_address;
                queue_beats[(head + queue_count) % QUEUE_DEPTH] <= read_request_beats;
                requests_accepted <= requests_accepted + 1;
                count = count + 1;
            end
            queue_count <= count;
        end
    end

endmodule
