// Die temperature for the MIG's read-path temperature compensation.
//
// The MIG is generated without its own XADC instance (XADC_En = Disabled in
// mig_ddr2.prj), so it expects device_temp_i: the 12-bit XADC temperature code.
// This polls the XADC temperature register over the DRP about every 10 us, the
// same arrangement as Digilent's out-of-box design for this board.
module xadc_temperature #(
    parameter integer CLOCK_HZ = 75_000_000
) (
    input logic clk,
    input logic reset,
    output logic [11:0] temperature
);

    localparam integer WAIT_CYCLES = CLOCK_HZ / 100_000;    // 10 us

    typedef enum logic [1:0] {
        WAIT,
        READ,
        HOLD
    } state_t;

    state_t state_reg, state_next;
    logic [$clog2(WAIT_CYCLES+1)-1:0] wait_reg, wait_next;
    logic [11:0] temperature_reg, temperature_next;

    logic drp_enable;
    logic [15:0] drp_data;
    logic drp_ready;


    XADC #(
        .INIT_40(16'h1000),        // average off, temperature channel
        .INIT_41(16'h3F3F),        // continuous single channel, alarms off
        .INIT_42(16'h0400),        // ADCCLK = DCLK / 4
        .INIT_48(16'h0100),        // sequencer: temperature
        .INIT_49(16'h0000), .INIT_4A(16'h0000), .INIT_4B(16'h0000),
        .INIT_4C(16'h0000), .INIT_4D(16'h0000), .INIT_4E(16'h0000), .INIT_4F(16'h0000),
        .INIT_50(16'hB5ED), .INIT_51(16'h57E4), .INIT_52(16'hA147), .INIT_53(16'hCA33),
        .INIT_54(16'hA93A), .INIT_55(16'h52C6), .INIT_56(16'h9555), .INIT_57(16'hAE4E),
        .INIT_58(16'h5999), .INIT_5C(16'h5111),
        .SIM_DEVICE("7SERIES")
    ) xadc_inst (
        .CONVST(1'b0), .CONVSTCLK(1'b0),
        .DADDR(7'h00), .DCLK(clk), .DEN(drp_enable), .DI(16'h0000), .DWE(1'b0),
        .RESET(reset), .VAUXN(16'h0000), .VAUXP(16'h0000), .VN(1'b0), .VP(1'b0),
        .ALM(), .BUSY(), .CHANNEL(), .DO(drp_data), .DRDY(drp_ready),
        .EOC(), .EOS(), .JTAGBUSY(), .JTAGLOCKED(), .JTAGMODIFIED(), .OT(), .MUXADDR()
    );


    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= WAIT;
            wait_reg <= '0;
            temperature_reg <= '0;
        end else begin
            state_reg <= state_next;
            wait_reg <= wait_next;
            temperature_reg <= temperature_next;
        end
    end


    always_comb begin
        state_next = state_reg;
        wait_next = wait_reg;
        temperature_next = temperature_reg;
        drp_enable = 1'b0;

        case (state_reg)
            WAIT: begin
                wait_next = wait_reg + 1'b1;
                if (wait_reg == WAIT_CYCLES) begin
                    wait_next = '0;
                    state_next = READ;
                end
            end

            READ: begin
                drp_enable = 1'b1;
                state_next = HOLD;
            end

            HOLD: begin
                if (drp_ready) begin
                    temperature_next = drp_data[15:4];
                    state_next = WAIT;
                end
            end

            default: begin
                state_next = WAIT;
            end
        endcase
    end

    assign temperature = temperature_reg;

endmodule
