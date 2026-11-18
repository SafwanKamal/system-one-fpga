# Deploy the combined UltraRAM candidate

App `sysone-v2-memory` combines the registered MAC pipeline, BRAM exponent
tables, H768/T128 capacity and four-clock pipelined UltraRAM activation reads.
It does not include the later streaming/query-localization/performance-counter
batch. The compiled bitstream uses the immutable 16-file memory snapshot.

Routed resources: 95,139 LUTs, 52,465 registers, 59 BRAM, 32 UltraRAM, 606 DSPs.
Both-clock 125 MHz qualification: setup +0.001 ns, hold +0.010 ns. The runtime
requests 125 MHz and discovers the existing boot reservation; it does not
resize DDR or change boot files.

From repository PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\v2\kr260\deploy_memory.ps1
```

This requests SSH/sudo passwords, transfers `build/v2/kr260-app-memory.tar.gz`,
loads the app, reads its SYS2/BUILD identifiers and live clock, then loads the
existing L12 model, verifies eight token lengths and runs its frozen 350-chain
evaluation. Reports go to a printed `~/kr260-memory-YYYYMMDD-HHMMSS` directory.
Deployment has not been performed by the laptop agent: key authentication is
unavailable. Return the check/evaluation results for board qualification.

The installed apps are preserved. To return to the prior verified pipeline:

```bash
sudo xmutil unloadapp && sudo xmutil loadapp sysone-v2-pipe
cd ~/system-one-fpga
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load
```

Changing the app requires reloading the model before RUN. Reboot likewise
requires loading an encoder app again. The new client helpers support old apps;
their prior copies are also saved in the board report directory.
