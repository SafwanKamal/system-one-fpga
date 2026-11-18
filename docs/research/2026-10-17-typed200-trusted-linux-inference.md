# Full inference deployed on KR260 through trusted Linux

2026-10-17. The qualified 200 MHz PL encoder and MiniLM L12 model are loaded
and ready for requests. Tokenization and classifier/slot heads execute on the
board's Linux A53 cores; the encoder executes in PL. R5 is not involved in
this inference deployment. JTAG stayed stopped.

On the KR260:

```sh
sysone-infer "show me flights from denver to boston tomorrow"
```

The installed `/usr/local/bin/sysone-infer` runs the existing hardware client
under sudo and serializes requests with flock. It defaults to ATIS intent and
slots. To use other existing heads, pass e.g. `--dataset clinc` before the text.
Full existing client functionality remains in
`/home/ubuntu/system-one-fpga/scripts/v2/sysone_v2_client.py`.

## Actual deployment result

- Root-private systemd deployment `sysone-trusted-inference-deploy-v3` exited
  successfully. Service runtime was 32.390 seconds, including loading/readback,
  examples and evaluation; no timing guarantee is claimed.
- FPGA app: `sysone-v2-attention-context-capture`, live PL0/PL1 clocks199999998Hz.
- Image: `minilm-l12-v1-kr260`,33916928bytes, SHA256
  `4129baded344729ccc7ef6a3f0a2b34799280a91d88173ae1c0b197cdef8c3bb`.
  DDR was loaded at60000000 and fully read back identically inside the existing
  256MiB Linux no-map reservation.
- Frozen evaluation:350/350 PL hidden-state results bit-exact. Cases cover
  ATIS, CLINC, HWU, MSRP, multi-CLINC, SGD and SICK, with predictions recorded.
  This is numerical agreement, not350/350 classification accuracy.
- First text example returned `atis_flight` (p0.999), with Denver/Boston/date
  slots; encoder time7.66ms. The installed entry point independently returned
  `atis_flight` (p0.994) for the Dallas/Boston cheapest-flight example.
- The app and model were left loaded. The incompatible stock dashboard stays
  stopped while the inference app owns PL. No R5 module or remoteproc owner is
  present. UART capture was closed after the run.

This is a working current-boot CLI deployment. It does not install a network
server or modify boot configuration to reload the app/model after reboot.
Existing client preflight rejects an absent app or unloaded/mismatched DDR.
Exclusive R5 ownership and hard deadlines are not claimed on this trusted
Linux path.

## Evidence and recovery

`build/v2/typed200-trusted-linux-inference-v1/deploy-v3` contains service logs,
collected target logs/evaluation and post-health. Root target stage is
`/var/lib/sysone/trusted-inference/deploy-v3`. Local `evaluation.json`,
`example-output.txt` and `result.json` summarize the successful run.

Deployment reused the already installed, hash-verified qualified package and
unchanged existing model/client sources. There was no RTL, model, module or
kernel rebuild, raw PS/RPU register access, boot mutation, commit or push.

Two failed preflights are retained: v1 expected an underscore rather than the
reported hyphen in the stock firmware name; v2 had Windows separators in
generated Linux hash paths. Both stopped before hardware changes. Corrected
v3 passed. Recovery restores stock before any attempted encoder RUN; after an
uncertain RUN failure it retains PL rather than unloading a possible DMA master.

Post-health retained boot6c80ec1a-e7ae-473f-b169-d54f129615d1, CPUs0-3 online,
taint12288 (existing O/E only), FPGA manager operating, encoder app active,
PL0/PL1 enabled/prepared1/1 at199999998Hz. Passive UART recorded the known Linux
overlay-removal warnings, without a new observed hang. No power-cycle is needed.

The companion validation JSON preserves both prior maps and their anchor and
seals new deployment evidence. HANDOFF.md remains mutable.
