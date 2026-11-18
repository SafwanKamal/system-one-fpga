# Zynq UltraScale+ / Kria: isolating a PL or R5 enforcer from Linux on the A53 (documentation check, 2026-11-08)

Sources: UG1085 (online rev 2.6), UG1137, XAPP1353, Xilinx wiki, Kria boot-firmware docs (URLs at end). Text was read
through a summarizer; UG1085 tables and figures were not seen directly. **[inference]** marks reasoning, not AMD text.

## Bottom line

- The hardware can isolate the enforcer: XPPU, XMPUs, TrustZone, the XMPU_PL soft IP, eFUSE authenticated boot and a
  PMU-owned isolation configuration.
- **None of it is on by default.** It must be configured, locked and backed by authenticated boot.
- In a default Kria/PetaLinux setup, Linux with root can, through documented interfaces: reload the PL (FPGA Manager →
  TF-A → PMUFW → PCAP), reset or stop the RPU (remoteproc / EEMI, CRL_APB), write R5 TCM through its global alias, gate PL
  clocks, and update the A/B boot images (`xmutil bootfw_update`).

## Mechanisms and the facts that matter

| Mechanism | What it protects | Key facts (source) |
|---|---|---|
| XPPU | LPD peripheral/control registers (0xFF00_0000-0xFFFF_FFFF in 64 KB apertures), IPI buffers, QSPI | Master-ID + aperture permission + TrustZone check; failing accesses poisoned. The whole APU cluster shares one master ID; each R5, PMU and CSU have their own, so APU vs RPU/PMU separation is possible but not per-core inside the APU (UG1085 Master IDs List, XPPU Operation). Configure once at boot by FSBL; only secure masters can change it and lock it. POR-sticky lock not confirmed. |
| XMPU (6 DDR, FPD, OCM) | Memory regions | 16 regions each, master/secure-level permissions; "lock register ... cleared only by a power-on reset" (UG1085). CCI can issue transactions with R5_0's ID: prefer R5_1 or no coherency for protected regions. |
| TrustZone | Every AXI transaction carries secure/non-secure | PL slaves can reject non-secure (AxPROT[1]=1) accesses, admitting only secure firmware/R5 [inference: valid only if Linux cannot reach a secure level or reprogram the PL]. |
| XMPU_PL (XAPP1353) | PL AXI slaves | LOCK[RegWrDis]=1 restricts config writes to secure masters in LOCK_BYPASS; isolate its config port with a blocking region; PMU can monitor it. |
| PMUFW configuration object | Which subsystem may use which slaves/resets | Isolation needs Advanced Mode; "Any slave on a subsystem without a defined master can be access by ALL masters" (wiki). "Lock Unused Memory" can stop the Linux subsystem from driving authenticated PL loads [inference]. |
| PL loading | Bitstream | Linux FPGA Manager loads are a documented feature, including unauthenticated partial bitstreams (wiki flag 0x01); no documented PMUFW switch limiting Linux to authenticated loads. |
| RPU / TCM | R5 code and data | TCM reachable from the APU at 0xFFE0_0000 (R5_0) / 0xFFE9_0000 (R5_1) while the R5 runs or is halted; must be blocked by XPPU (UG1085 TCM Access). |
| CRL/CRF write-protect bits | Clocks, PLLs, resets, pcap_ctrl | Ordinary register bits, protection against accidents only [inference]; real protection needs XPPU/XMPU denial of APU or non-secure access to CRL_APB, CRF_APB, PMU_GLOBAL, CSU, RPU control. |
| SMMU | DMA masters | Programmed by Linux in a standard image, so no protection against root [inference]. |
| Secure lockdown / authenticated boot | Boot chain | Without eFUSE RSA_EN and a PPK hash, a modified FSBL/PMUFW/isolation config written to the A/B images takes effect next boot [inference]. KR260 QSPI is writable in the A/B partitions; factory secure-boot status not documented. |

## What this means for direction 2 (isolation evidence)

A defensible claim needs, at minimum: an RPU-only subsystem in the PMUFW configuration object; XPPU apertures denying
APU/non-secure access to CRL_APB, CRF_APB, PMU_GLOBAL, CSU, RPU control and TCM; XMPU regions for any shared DDR/OCM,
locked until POR; the enforcer's PL slave rejecting non-secure accesses; PL reloads from the Linux subsystem disabled;
authenticated boot (RSA_EN + PPK) so the configuration cannot be replaced; and the enforcer failing closed when its clock,
reset or link is removed. Each of these is documented as available; whether the Kria SOM accepts the required custom
FSBL/PMUFW and eFUSE programming is not documented and must be checked before committing.

## Not obtained

RPU_GLBL_CNTL / RPU_x_CFG fields (UG1087); CRL_APB write-protect and reset register text; whether the XPPU lock is
POR-sticky; eFUSE security bit list (JTAG_DIS, RSA_EN, ENC_ONLY, PROG_GATE); Kria factory isolation and secure-boot state.

## URLs

- https://docs.amd.com/r/en-US/ug1085-zynq-ultrascale-trm (XPPU-Operation, XPPU-Self-Protection, XMPU-Protection-of-Slaves,
  Other-Write-Protected-Registers, CRF-APB-Registers, Master-IDs-List, TCM-Access-from-a-Global-Address-Space,
  RPU-Reset-Sequence, PCAP-Isolation-Wall-Control, Isolation-Request, AIB-Isolation-Functionality, Secure-Lockdown,
  PL-TrustZone-Extension, Lock-Unused-Memory-Attribute, System-Memory-Management-Unit)
- https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev (Configuration-Object, CSU/PMU-Register-Access,
  System-Level-Protections)
- https://docs.amd.com/r/en-US/xapp1353-pl-isolation (LOCK-Register, Isolating-the-XMPU_PL-Configuration)
- https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842442/Zynq+UltraScale+Isolation+Configuration
- https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842505/Zynq+Ultrascale+MPSoC+Secure+bitstream+programming+from+Linux
- https://xilinx.github.io/kria-apps-docs/bootfw/build/html/docs/bootfw_overview.html
- https://docs.foundries.io/latest/reference-manual/security/secure-boot-zynq.html (secondary)
