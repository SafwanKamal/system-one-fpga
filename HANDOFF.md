# Handoff: System One on FPGAs — v2 runs on the Nexys 4 DDR; next, the KR260

Written 2026-10-08 for whoever continues this project (person or AI agent). It is meant
to be read without any earlier conversation. Read this first, then `rtl/v2/README.md`:
it has every result and design decision, and a log of problems hit and how they were
solved (21 entries).

**The Kria KR260 board is now on hand, so the next phase is bringing the encoder up on it
(section 5).**

## 1. The project in one paragraph

"System One" is a fast text classifier (an assistant's quick, intuitive first pass) built
in FPGA hardware. **v1** (in `rtl/`, `scripts/`, `src/sysone/`, unchanged) is a hashed
bag-of-n-grams classifier that runs entirely in block RAM on a Digilent Nexys 4 DDR
(Artix-7 xc7a100t). **v2** (everything under `*/v2/`) runs a small transformer encoder
(MiniLM-L6: 6 layers x 384, 23M parameters, INT8) on the FPGA: the weights live in the
board's DDR memory as one "DDR image"; the host sends token ids over raw Ethernet, the
FPGA runs the whole encoder and returns the final hidden states, and small task heads
(intent classification, slot filling, sentence pairs, a sentence embedding) run on the
host in NumPy. The FPGA result is bit-exact with a Python integer model
(`src/sysone/v2/ddr_image.py`, `ImageMachine`), which is how everything is verified.

## 2. Rules from the owner (standing)

* **Sole author.** Commits are by `Safwan Kamal <safwankamal123@gmail.com>` only: no AI
  co-author lines or "generated with" trailers in commits or pull requests.
* **Commit or push only when asked.** Never touch the `main` branch of the separate
  Genome-Classifier repository.
* **Never ask the owner for access tokens** (Hugging Face or others) in chat.
* **No speed conclusions from the Ethernet link.** The host connects through a USB
  100 Mb/s adapter, so host-measured times are dominated by it. Speed is reported from
  the board's own clock counters; host-measured times are labelled "host path".
* **Document significant problems and their fixes** in `rtl/v2/README.md`, section
  "Problems hit and how they were solved" (continue the numbering). When the owner pastes
  command output marked "document:", record the results in the README and fix anything
  the output shows to be wrong.
* Heads run on the host (an FPGA-heads variant exists behind the `FPGA_HEADS` RTL
  parameter; it was not worth it).
* Before starting on a request, check for recently changed or uncommitted files: once,
  an interrupted session left half-finished work that was then done a second time.

## 3. Machines, tools, repository

* **Repository**: `github.com/SafwanKamal/system-one-fpga`, branch `main`. The working
  copy is on the owner's Windows laptop:
  `C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga`
  (long path: Windows' 260-character limit broke a Vivado IP build once, so Vivado
  projects use short names, `build/v2/enc`, `build/v2/encp`; `subst` a drive letter if
  it recurs).
* **Git state: HEAD is `45547f8`** (v2 through step 4). **Everything since is
  uncommitted**: step 5 and the board run, the KR260 RTL, the v3 models, all host
  features (tens of modified and new files). Never commit `logs/` or `_to_delete/`
  (transfer leftovers, safe to delete). `export/`, `models/` and the downloaded corpora
  under `data/v2/` are gitignored.
* **Python**: `uv`. Runtime needs only NumPy (+ scapy for the Ethernet link):
  `uv run python ...`. Training and image compilation need PyTorch + transformers, in the
  `train` dependency group: `uv sync --group train`, then `uv run --group train python ...`.
  Corpora: `uv run python scripts/v2/fetch_v2_data.py`; base models:
  `uv run --group train python scripts/v2/fetch_models.py` (public, no token).
* **Training runs on the laptop CPU** (no NVIDIA GPU; all cores by default): about 36 min
  per epoch for the current corpus (~97k training chains).
* **Vivado**: laptop 2025.2. A desktop has 2026.1, whose licence tiers reject the
  xc7a100t unless the free BASIC tier is selected.
* **Simulation**: Verilator 5.x, `simulation/v2/Makefile` (targets listed in the README).
* **Nexys host side**: Windows laptop, Realtek USB Ethernet adapter, raw Ethernet via
  scapy/Npcap: `-i "Realtek USB FE Family Controller"`.

## 4. Current state

### Nexys 4 DDR: the v2 encoder runs on the board, bit-exact

* Bitstream: `vivado -mode batch -source scripts/v2/create_project_v2.tcl -tclargs build encoder`,
  then `vivado -mode batch -source scripts/v2/program_board_v2.tcl -tclargs encoder`.
  75 MHz, worst setup slack +0.187 ns; LUT 79%, block RAM 128/135, DSP 236/240 (full).
* `bert-mini-slots4` on the board: `check` bit-exact for 1/12/64/128 tokens; 128 tokens =
  2,951,462 clocks = 39.35 ms (simulation: 2,952,317). `eval --verify`: 120/120
  bit-exact.
* Host client `scripts/v2/sysone_v2_client.py` (all commands take `--image <name>`):
  `load` (writes the image to DDR, 15 s for 11 MB), `check` (random token chains vs
  `ImageMachine`), `run --dataset <name>|auto [--intents file.json] "text"`,
  `doc --file text.txt [--query ...] [--intents ...]` (long texts), `eval`; `--local`
  runs without a board; `--kr260` runs on the KR260's ARM cores (section 5).

### Models (heads on the host)

| test sets | minilm-l6 | **minilm-l6-v3b** (current best) |
|---|---|---|
| CLINC150 in-scope / combined incl. out-of-scope rule | 0.953 / 0.902 (τ 0.475) | 0.961 / **0.9025** (τ 0.48) |
| ATIS intent / slot F1 | 0.959 / 0.782 | 0.976 / 0.876 |
| HWU64 intent / slot F1 | – | 0.916 / 0.696 |
| SGD dialogue intent / slot F1 | 0.879 / 0.496 | 0.868 / 0.506 |
| SICK / MSRP | 0.862 / 0.751 | 0.858 / 0.713 |
| unseen intents from 5 examples, integer image: Banking77 / SNIPS | – | 0.752 / 0.905 |

* v3b training command (laptop): `uv run --group train python scripts/v2/train_chain.py
  --model models/all-MiniLM-L6-v2 --name minilm-l6-v3b --init export/v2/chain/minilm-l6/chain_model.pt
  --hwu --embed-dim 384 --teacher models/all-MiniLM-L6-v2 --epochs 2 --lr 4e-5 --head-lr 1e-3
  --distill-weight 10 --resume`.
* v3b image `export/v2/image/minilm-l6-v3b/` (23,035,904 bytes; `compile_image.py check`:
  0 mismatches over 1,400 chains; runs on the same bitstream). **Not yet run on the
  board.**
* `auto` routing: one encoder pass; custom intents (embedding head, nearest centroid of a
  few example sentences, `examples/v2/custom_intents.json`) → CLINC with its
  out-of-scope threshold → ATIS (flights) / SGD (services) / HWU64 (assistant) intents
  and slots → else the CLINC intent.
* Long inputs: the encoder window is 128 tokens. `doc` splits text into sentences and
  sends one request per sentence (packing several into one request costs accuracy:
  1000-word documents 0.919 alone vs 0.790 packed). The window cannot grow on the Nexys
  (block RAM).

### KR260 (K26 SOM, part xck26-sfvc784-2LV-c): simulation only so far

* RTL `rtl/v2/platform/kr260/`: `kr260_encoder.sv` (AXI4-Lite registers 0x00 CONTROL …
  0x2C RESULT, ID register "SYS2", BUILD register, interrupt; the same `encoder_system`
  as the Nexys; `axi_memory_port.sv` = AXI4 master to the PS DDR) and
  `kr260_encoder_wrapper.v` (plain-Verilog wrapper for a block-design module reference).
  Parameters: TILE_OUT 32, DRAIN_LANES 4, NORM_LANES 4, 40-bit addresses.
* Simulation (`make encoder-kr260`; `make kr260-vectors` + `make kr260` with an AXI DDR
  model with random stalls, runs started through the registers): bit-exact for 1, 12
  and 128 tokens. bert-mini at 128 tokens: 1.39M clocks (2.95M on the Nexys), ~14 ms at
  100 MHz. LayerNorm is now ~31% of the time.
* Vivado block design `scripts/v2/kr260/create_project_kr260.tcl`: **written before the
  board arrived and never run.** Zynq UltraScale+ PS with the board preset,
  M_AXI_HPM0_FPD → encoder registers at 0xA000_0000, encoder → S_AXI_HP0_FPD (128-bit),
  pl_clk0 100 MHz, interrupt → pl_ps_irq0; output in `build/v2/kr260/`.
* ARM-side driver `src/sysone/v2/kr260_link.py`: `Kr260Link(registers=0xA000_0000,
  memory=(0x6000_0000, 64 MiB))` via `/dev/mem` (uncached); the whole host client runs on
  the board with `--kr260`. **Never run.**
* KR260 images: `uv run --group train python scripts/v2/compile_image.py build --name <model>
  --board kr260 --base 0x60000000 --suffix=-kr260 --reuse-calibration` (tile 16x32,
  absolute addresses). Built so far: `bert-mini-slots4-kr260` only.

## 5. Next: KR260 bring-up (suggested order)

1. **Board OS**: find out what the KR260 runs (the Kria Ubuntu image is the usual
   choice; it provides `xmutil` / `fpgautil`). Network/SSH; `python3 -m pip install numpy`
   (the client needs only NumPy with `--kr260`); copy the repo's `src/` and `scripts/v2/`.
2. **Vivado**: install the KR260 board files (Vivado Store → Boards → Kria KR260), run
   `create_project_kr260.tcl`, fix what breaks (board-part names, PS preset,
   interconnect, address assignment), build. TILE_OUT 32 has never been through Vivado
   (the K26 has 1,248 DSP, 144 block RAM + 64 UltraRAM, ~117k LUT). Log every fix in the
   README problems section.
3. **Deploy**: bitstream as `.bit.bin` (bootgen) + device-tree overlay (`.dtbo`)
   describing the encoder at 0xA000_0000 + `shell.json`, in `/lib/firmware/xilinx/<app>/`;
   `sudo xmutil unloadapp && sudo xmutil loadapp <app>` (or `fpgautil`).
4. **Memory for the image — a decision to make.** `kr260_link.py` assumes 64 MiB at
   0x6000_0000 that Linux does not use; a stock Kria Ubuntu probably does use it.
   Options: (a) a reserved-memory node in the boot device tree (a runtime overlay
   cannot add one); (b) the `u-dma-buf` kernel module: a physically contiguous buffer
   whose physical address is read from sysfs; rebuild the images with
   `--base <that address>` and pass it to `Kr260Link`; (c) CMA / dma-heap. The HP0 port
   is not cache-coherent: keep the CPU mapping uncached or flush/invalidate explicitly.
   (b) is probably simplest; verify on the board.
5. **First run on the ARM**: `python3 scripts/v2/sysone_v2_client.py --kr260 --image
   bert-mini-slots4-kr260 --clock-mhz 100 load`, then `check` (must be bit-exact; compare
   the clocks with the 1.39M simulation figure), `run --dataset auto "..."`, `doc`, and
   `eval --verify` (needs the corpora on the board).
6. **MiniLM-L6-v3b on the KR260**: build `minilm-l6-v3b-kr260` on the laptop (command
   above); copy the image directory (image, `manifest.json`, `decision.json`) and
   `export/v2/chain/minilm-l6-v3b/tokenizer.json`.
7. **Experiments the larger chip allows** (all measured with the board's clock
   counters): a faster pl_clk, a wider array or the packed-DSP option (two INT8 products
   per DSP; 1.6–1.7x in simulation on the Nexys), more LayerNorm lanes, a longer window
   (UltraRAM could hold MiniLM buffers for ~512 tokens; the models would need training
   on longer inputs), a per-segment attention mask (packed long-text speed without the
   accuracy loss), and evaluating through the hardware instead of `ImageMachine`
   (Banking77 few-shot took 5.7 h in NumPy).

## 6. Loose ends on the Nexys side

* Rerun the out-of-scope thresholds after the router-statistics fix (problem 21; the
  probabilities are cached in `logs/oos_cache/`, so it takes seconds):
  `uv run --group train python scripts/v2/oos_threshold.py --name minilm-l6-v3b --extra hwu`.
  The current `export/v2/image/minilm-l6-v3b/decision.json` has the HWU threshold 0.515
  from the faulty run.
* Run v3b on the Nexys board: `--image minilm-l6-v3b` with `load`, `check`,
  `run --dataset auto --intents examples/v2/custom_intents.json "how should I build a h-bridge circuit?"`,
  `doc --file examples/v2/long_text.txt`.
* The packed-DSP build (`encoder_packed`) was never synthesised; the Nexys is nearly
  full.
* Commit the outstanding work when the owner asks (sole author, no AI trailers).
