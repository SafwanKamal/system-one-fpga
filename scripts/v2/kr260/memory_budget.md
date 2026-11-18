# Flexible KR260 memory budget

The client now discovers the dedicated boot-time `sysone@...` no-map reservation;
`--region BASE BYTES` can restrict access to a subregion. Deployment accepts the
actual validated allocation instead of requiring exactly 64 MiB. Existing models
and apps still work at their established addresses when the region is enlarged.
Weights, instructions, token IDs and output scratch must all fit the allocation.

The first larger configuration is **256 MiB at 0x60000000**, ending at 0x6fffffff.
This retains existing image addresses and gives four times the former capacity.
The owner verified this allocation after reboot on 2026-10-10, with live
124,999,999 Hz, identical L12 readback and all eight token-length checks exact.
Evidence is in `build/v2/eval/kr260-memory-256/`; a full-region memory sweep and
larger-model validation have not been performed. The scripts accept
other page-aligned base/size pairs within mapped low DDR, reject PMU and other
reserved-region overlaps, and persist the choice across kernel updates in
`/etc/sysone/kr260-memory.json`. High DDR remains a separate ISA/mapping change.
Changing memory size alone does not increase the RTL hidden-width limit. The
original memory app supports hidden384; the separately qualified dot7 frontier
app supports hidden1024, proven by eight synthetic input lengths. This is a
capacity proof, not a trained larger-model quality result. Both use the same
verified256MiB reservation; high-DDR integration remains separate.

In PowerShell from the inner repository directory:

```powershell
scp ".\build\v2\kr260-memory-budget.tar.gz" ubuntu@192.168.0.239:~/
ssh ubuntu@192.168.0.239
```

On the KR260:

```bash
mkdir -p ~/sysone-memory-budget
tar -xzf ~/kr260-memory-budget.tar.gz -C ~/sysone-memory-budget
bash ~/sysone-memory-budget/set_memory_budget.sh 0x10000000
```

This verifies a reservation-only candidate FIT, backs up kernel DTBs, installs
persistent hooks, regenerates the boot FIT and verifies the resulting reservation.
It saves source/candidate FITs and hashes under a new `~/sysone-boot/memory-*`
directory. It updates the runtime/client and does not reboot. Only after the
script prints **Verified boot FIT**, reboot and reconnect:

```bash
sudo reboot
```

After reconnecting to the KR260:

```bash
sudo grep -E '60000000|6fffffff' /proc/iomem
sudo python3 ~/sysone-memory-budget/deploy_app.py /lib/firmware/xilinx/sysone-v2-pipe
cd ~/system-one-fpga
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 load
sudo ~/sysone-venv/bin/python scripts/v2/sysone_v2_client.py --kr260 --image minilm-l12-v1-kr260 check --tokens 1 2 3 4 5 12 64 128
```

Expect `60000000-6fffffff : reserved`, automatic detection of 256 MiB, live
124,999,999 Hz and eight bit-exact checks. Use this bundle's deployment helper
for existing apps; older extracted deployment helpers still require exactly
64 MiB. Save the complete output as the board activation evidence.

To return to 64 MiB, rerun the same budget script with `0x4000000`, verify its
FIT, reboot and reload the app. Existing image/request data must be reloaded
after any reboot. Kernel DTB originals remain under `/var/lib/sysone/dtb-backups`.
