# v2 simulation. Run from this directory. Needs Verilator >= 5.040 (as v1).
#
#   make ddr        ddr_selftest + mig_memory_port against the behavioural MIG model
#   make axi        ddr_selftest + axi_memory_port (KR260) against an AXI4 slave model
#   make memory-vectors / make link
#                   v2 memory link (Ethernet <-> DDR) through its RMII pins, two clocks,
#                   behavioural MIG; then the host decoder checks every reply
#   make encoder-vectors / make encoder
#                   one encoder layer of a DDR image (bring-up step 4): sequencer + engines
#                   single-stepped through the layer program against ImageMachine, behavioural
#                   memory port with random stalls (vectors need the ML venv, see the script)
#   make lint       Verilator lint of the v2 RTL that does not instantiate Xilinx primitives

V2 := ../../rtl/v2

DDR_RTL := $(V2)/common/sync_fifo.sv \
           $(V2)/platform/nexys4ddr/mig_memory_port.sv \
           $(V2)/test/ddr_selftest.sv

.PHONY: ddr axi memory-vectors link encoder-vectors encoder lint clean

PYTHON ?= uv run python
V1 := ../../rtl
LINK_RTL := $(V2)/common/sync_fifo.sv $(V2)/common/async_fifo.sv \
            $(V2)/platform/nexys4ddr/mig_memory_port.sv \
            $(V2)/link/memory_link_parser.sv $(V2)/link/memory_link_executor.sv \
            $(V2)/link/memory_link_responder.sv $(V2)/link/memory_link_core.sv \
            $(V1)/ethernet_CRC32.sv $(V1)/rmii_RX.sv $(V1)/ethernet_RX.sv \
            $(V1)/ethernet_RX_buffer.sv $(V1)/rmii_TX.sv $(V1)/ethernet_TX.sv \
            $(V1)/ethernet_TX_buffer.sv

memory-vectors:
	$(PYTHON) ../../scripts/v2/memory_link_vectors.py

obj_dir/memory_link_tb: $(LINK_RTL) mig_native_model.sv memory_link_tb.sv
	verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style \
	    --top-module memory_link_tb memory_link_tb.sv mig_native_model.sv $(LINK_RTL) \
	    -o memory_link_tb

link: obj_dir/memory_link_tb
	./obj_dir/memory_link_tb
	$(PYTHON) ../../scripts/v2/memory_link_vectors.py --check

AXI_RTL := $(V2)/common/sync_fifo.sv \
           $(V2)/platform/kr260/axi_memory_port.sv \
           $(V2)/test/ddr_selftest.sv

obj_dir/axi_selftest_tb: $(AXI_RTL) axi_slave_model.sv axi_selftest_tb.sv
	verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style \
	    --top-module axi_selftest_tb axi_selftest_tb.sv axi_slave_model.sv $(AXI_RTL) \
	    -o axi_selftest_tb

axi: obj_dir/axi_selftest_tb
	./obj_dir/axi_selftest_tb

obj_dir/ddr_selftest_tb: $(DDR_RTL) mig_native_model.sv ddr_selftest_tb.sv
	verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style \
	    --top-module ddr_selftest_tb ddr_selftest_tb.sv mig_native_model.sv $(DDR_RTL) \
	    -o ddr_selftest_tb

ddr: obj_dir/ddr_selftest_tb
	./obj_dir/ddr_selftest_tb

lint:
	verilator --lint-only -Wall -Wno-WIDTHEXPAND -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM \
	    $(DDR_RTL) $(V2)/platform/kr260/axi_memory_port.sv $(V2)/common/sequential_divider.sv $(V2)/common/seven_segment_display.sv \
	    --top-module ddr_selftest

clean:
	rm -rf obj_dir

ML_PYTHON ?= ../../../mlenv/bin/python
ENCODER_MODEL ?= bert-mini-slots4
ENCODER_RTL := $(V2)/common/sequential_divider.sv \
               $(V2)/encoder/encoder_pkg.sv $(V2)/encoder/activation_buffer.sv $(V2)/encoder/mac_array.sv \
               $(V2)/encoder/linear_engine.sv $(V2)/encoder/attention_engine.sv \
               $(V2)/encoder/add_skip_engine.sv $(V2)/encoder/layernorm_engine.sv \
               $(V2)/encoder/encoder_layer.sv

encoder-vectors:
	$(ML_PYTHON) ../../scripts/v2/encoder_vectors.py --name $(ENCODER_MODEL)

obj_dir/encoder_layer_tb: $(ENCODER_RTL) memory_port_model.sv encoder_layer_tb.sv
	verilator --binary --timing -j 0 -O3 -Wno-fatal -Wno-lint -Wno-style \
	    --top-module encoder_layer_tb encoder_layer_tb.sv memory_port_model.sv $(ENCODER_RTL) \
	    -o encoder_layer_tb

encoder: obj_dir/encoder_layer_tb
	./obj_dir/encoder_layer_tb
