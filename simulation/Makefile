# System One RTL simulation. Run from this directory.
#
#   make vectors   pack the export into ../memory and write vectors/ (~4 s)
#   make sim       full CLINC150 test set + edge cases, bit-exact (~3 min)
#   make metrics   score the RTL's own logits with the Phase 1 metrics
#   make ethernet  sysone_ethernet_core through its RMII pins, then the host decoder
#                  checks every response (~4 min)
#   make lint      Verilator -Wall on the synthesisable RTL (width-extension and
#                  unused-signal warnings waived, as dense_engine.sv also has them)
#
# Needs Verilator >= 5.040 (5.020 cannot compile dense_engine.sv: BLKLOOPINIT).
# Icarus 12 cannot elaborate dense_engine.sv either (whole-array assignment).

PYTHON ?= uv run python

RTL := ../rtl/feature_hash_pipeline.sv \
       ../rtl/feature_generator.sv \
       ../rtl/embedding_bag.sv \
       ../rtl/dense_engine.sv \
       ../rtl/channel_requantizer.sv \
       ../rtl/logit_argmax.sv \
       ../rtl/classifier_head.sv \
       ../rtl/sysone_core.sv

ETHERNET_RTL := $(RTL) \
       ../rtl/ethernet_CRC32.sv \
       ../rtl/rmii_RX.sv \
       ../rtl/ethernet_RX.sv \
       ../rtl/ethernet_RX_buffer.sv \
       ../rtl/sysone_request_parser.sv \
       ../rtl/sysone_result_packet.sv \
       ../rtl/rmii_TX.sv \
       ../rtl/ethernet_TX.sv \
       ../rtl/ethernet_TX_buffer.sv \
       ../rtl/sysone_ethernet_core.sv

.PHONY: vectors sim metrics ethernet-vectors ethernet lint clean

vectors:
	$(PYTHON) ../scripts/rtl_pack.py --vectors

obj_dir/sysone_core_tb: $(RTL) sysone_core_tb.sv ../rtl/model_parameters.svh
	verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style -I../rtl \
	    --top-module sysone_core_tb sysone_core_tb.sv $(RTL) -o sysone_core_tb

sim: obj_dir/sysone_core_tb
	./obj_dir/sysone_core_tb +verilator+error+limit+1000000

metrics:
	$(PYTHON) ../scripts/rtl_metrics.py

ethernet-vectors:
	$(PYTHON) ../scripts/ethernet_vectors.py

obj_dir/sysone_ethernet_tb: $(ETHERNET_RTL) sysone_ethernet_tb.sv ../rtl/model_parameters.svh
	verilator --binary --timing -j 0 -Wno-fatal -Wno-lint -Wno-style -I../rtl \
	    --top-module sysone_ethernet_tb sysone_ethernet_tb.sv $(ETHERNET_RTL) -o sysone_ethernet_tb

ethernet: obj_dir/sysone_ethernet_tb
	./obj_dir/sysone_ethernet_tb +verilator+error+limit+1000000
	$(PYTHON) ../scripts/ethernet_vectors.py --check

lint:
	verilator --lint-only -Wall -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM \
	    -I../rtl --top-module sysone_ethernet_core $(ETHERNET_RTL)

clean:
	rm -rf obj_dir rtl_logits.hex ethernet_responses.hex
