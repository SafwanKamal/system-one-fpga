# Deterministic-latency in-network enforcement: FPGA vs software IPS, stateful TCP in hardware, TSN/industrial constraints

Scope note: 8 primary papers were downloaded and read (access level recorded per paper below). Numbers are taken from the paper text and tables. Figure-only values I could not read off are marked as such. Derived arithmetic is labelled "Inference".

## Per-paper extraction

### Takeaway
The best measured evidence on software IPS tail latency comes from the TUM group (Gallenmüller et al.). With careful tuning, Snort and Suricata on DPDK stay in the tens of µs at p99.999. Untuned, or once offered load passes per-core capacity, they show spikes of 0.6 to 3.3 ms, and capacity runs out at only 70 to 200 kpkt/s of 64 B frames per worker core. FPGA systems (Pigasus, FlowBlaze, Iwasawa's ICS firewall) report µs-scale latency. Only Iwasawa reports a frame-size-independent bound, and none of the FPGA papers measures p99.99 or worst case under a flood with the methodology the TUM papers use.

### Cited Findings

**P1. Gallenmüller, Wiedner, Naab, Carle, "How Low Can You Go? A Limbo Dance for Low-Latency Network Functions," J. Network and Systems Management (2023). Access: FULL TEXT read.**
- Platform: Intel Xeon D-1518 (4 cores at 2.2 GHz) with an integrated X552 10G NIC. Debian 11, kernel 5.10 (vanilla, PREEMPT_RT, no-hz builds), DPDK 21.11, Suricata 7.0. The test traffic is 64 B UDP at a constant 10 to 250 kpkt/s. — [Gallenmüller et al. JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Methodology, which a reviewer would accept as a template: a separate LoadGen, a DuT, and a Timestamper. Passive optical splitters feed an Intel X550 that hardware-timestamps every packet at 12.5 ns resolution. Ingress and egress pcaps are matched in PostgreSQL. Results are reported as percentile plots out to 99.9999%, together with time series of the 5000 worst latency events over a 60 s run. The authors reject MoonGen's sampled timestamping (about 1 kpkt/s) because it misses rare events. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Motivating example: untuned Suricata at a moderate 10 kpkt/s had a median of 47 µs and random spikes up to 1.8 ms, a 38-fold gap between median and worst case. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- DPDK-l2fwd (no processing): about 3.3 µs up to p99.9 on every kernel. The tail beyond p99.99 rises to 5.3 µs (vanilla) or 5.5 µs (rt), and to 4.1 µs on no-hz. The local timer interrupt is the cause. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Suricata forwarding with no ruleset: on the rt kernel the median is 3.8 µs and the latency beyond p99.9 is about 6.5 µs, reaching 12.2 µs at 250 kpkt/s. Above roughly p99.999, the vanilla and no-hz kernels spike to 635 µs, which the authors attribute to TLB shootdowns from Suricata's memory management. They "did not find a configuration to avoid them". — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Suricata with the default ruleset: the median is about 10 µs at 10 to 150 kpkt/s. On vanilla and no-hz kernels latency jumps to about 600 µs starting at p99.99. Suricata overloads at about 200 kpkt/s on every kernel, and overload brings packet loss and latency up to 2 ms. The authors' Recommendation II: "overload must be avoided". — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- NIC effects: X710 and E810 NICs become bursty at 50 kpkt/s or more. On the X710 the median rose to about 14 µs and p99 to 37 µs. The authors blame configurable NIC pipelines and firmware: "the packet processing path and latency on the NIC less predictable". — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Virtualization raises the tail (about 10 to 11 µs for l2fwd) but has little effect below p99. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Cost and limitations: polling and disabled C-states take server power from 31 W idle to 47 W, a 48% increase. Suricata needs at least 3 cores to run with minimal core sharing. Cited background: LLC contention from a co-located cache-heavy application cost a DPDK application 64% of its performance (Herdrich et al.), recoverable only with Intel CAT. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Stateful limits: tests used UDP only "to avoid any impact of TCP congestion control". No TCP reassembly stress, no many-connection test, no attack traffic.

**P2. Gallenmüller, Naab, Adam, Carle, "5G QoS: Impact of Security Functions on Latency," IEEE/IFIP NOMS 2020. Access: FULL TEXT read.**
- Untuned motivating case: Snort-as-forwarder in a VM at 10 kpkt/s. Latency was p50 69 µs, p99 88 µs, p99.9 107 µs, p99.99 1.7 ms, p99.999 2.5 ms. — [Gallenmüller et al. NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Tuned stack (rt kernel, isolcpus, SR-IOV, CAT, Snort 3 with DPDK DAQ, Xeon D-1518):
  - Bare metal, Snort-filter with the community rules: p50 17.4 µs and max 36.6 µs at 10 kpkt/s; max 51.5 µs at 60 kpkt/s.
  - Snort-filter overloads at 70 kpkt/s: p50 79 µs, but p99 about 24.9 ms and max about 28 ms (Table II prints 24 897 to 27 992 µs from p99 to max).
  - Snort-fwd overloads at 90 kpkt/s: 3.3% loss and latency of about 30 ms (Table II: 30 609 to 30 959 µs).
  - In a VM at 90 kpkt/s, Snort-fwd shows 7.1% loss and about 2.5 to 2.7 ms.
  - [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Burst sensitivity: the DPDK batch size of 32 holds each packet until the whole batch is processed. Bursts of 32 to 64 back-to-back packets at a mean rate of only 10 kpkt/s pushed latency beyond the 1 ms URLLC criterion. Reducing the batch to 4 lowered the median but had "little influence on the maximum". — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Interrupt residue even when tuned: the local timer interrupt (250 Hz) costs about 5.5 µs and the IRQ-work interrupt about 8.2 µs. Each one produces spikes up to 13.6 µs on bare metal and about 19 µs in a VM. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Capacity model: R_max = (1 s − d)/t_cpu, where t_cpu is 14.3 µs/packet for Snort-filter, giving 69.7 kpkt/s. The model predicted overload correctly in 3 of 4 cases. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Power: 31 to 47 W per server, with the low-latency configuration costing up to 48% more at idle. Future work: "impact of hosting different 5G service classes on the same system", meaning QoS cross-talk from co-located workloads, which they left unmeasured. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)

**P3. Zhao, Sadok, Atre, Hoe, Sekar, Sherry, "Achieving 100Gbps Intrusion Prevention on a Single Server" (Pigasus), OSDI 2020. Access: FULL TEXT downloaded. I read the abstract, introduction, design (reassembler), evaluation, outlook and conclusion closely and skimmed the MSPM internals.**
- Platform: Intel Stratix 10 MX development card (16 MB BRAM, 10 MB eSRAM, 8 GB DRAM) in a 16-core i9-9960X host, at a 100 Gb/s line rate. The pipeline handles 25 Mpps, so 100 Gb/s holds only while the average packet exceeds 500 B. — [Pigasus OSDI'20](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Latency was measured only at low load, with FPGA counters plus the loopback baseline (DPDK Pktgen timestamps could not be used). Pigasus reports "almost an order of magnitude" better median and "up to 3×" better tail than Snort, with "3 µs latency in the common case". The Fig. 11 CDF spans 0 to 30 µs. No p99.99 figure, no worst-case figure, and no latency under attack load is reported. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Where software latency goes: relative to Snort, Pigasus saves about 6 µs in reassembly, 4 µs in parsing, 3 µs in MSPM, and about 5 µs of software packet I/O overhead. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Stateful TCP: targets 100K flows. The flow table is a de-amortized cuckoo hash in BRAM with constant-time fast-path updates. Out-of-order packets go to a separate OOO engine that keeps a linked list (about 5 KB per OOO flow). When OOO BRAM use exceeds 90%, flows are dropped or reset. The design point: "in-order flows are performance-wise isolated from out-of-order flows". In real traces 0.3% of packets arrive out of order and holes typically fill after 3 packets. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Adversarial OOO (Table 1): with 10 Gb/s of attack traffic, innocent goodput falls to 89.7 / 89.1 / 81.0% for 99.7 / 99 / 90% in-order innocent traffic, against an ideal of 99.99 / 99.9 / 99. At 10 Mb/s of attack traffic, goodput stays at 99.7 / 99.1 / 91.5%. The authors admit "slowdowns on the OOO path can make Pigasus fall short". Throughput degrades with loss probability and recovery distance (swept from 0.3 to 30% and 3 to 100), but about 50 OOO arrivals are absorbed without loss. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Malicious-traffic fraction: line rate holds with 1 CPU core while malicious packets stay below 15%, and with 16 cores up to 50%. Beyond that the FPGA's rule-reduction logic becomes the bottleneck. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Resources and power:
  - The MSPM uses 3.3 MB of BRAM, and 100K flows plus 10K rules fit in about half the FPGA.
  - FPGA power is 40 W in total, of which the core fabric is 13 W.
  - Snort would need 23 to 200× more cores (72× on average in IPS mode). Extrapolated, that is 125 to 667 cores for 100 Gb/s.
  - Snort draws 13 to 59× more power (34× on average).
  - [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- Future work: "further eliminating CPU bottlenecks" and moving more functionality onto the FPGA. The outlook section also proposes duplicating the pipeline to reach 200 Gb/s. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)

**P4. Pontarelli et al., "FlowBlaze: Stateful Packet Processing in Hardware," NSDI 2019. Access: PARTIAL. Full text downloaded. I read the abstract, introduction, hardware implementation (§4) and the evaluation passages on throughput, power and resources.**
- Platform: NetFPGA SUME (Virtex-7 690T) with 4×10G ports, clocked at 156.25 MHz and designed for 64 B line rate. Latency is "less than 1 µs" per packet; the abstract says "a few microseconds". — [FlowBlaze NSDI'19](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)
- Stateful design: EFSM over a flow-context table, using a 4-choice cuckoo hash (97% load factor) with an 8-entry stash so insertion always takes 1 cycle. Each move takes about 6.4 ns. A same-flow scheduler stalls the pipeline to keep per-flow state consistent, and "pipeline stalls ... may actually lower the achieved throughput for some traffic mixes". When the table is full, a configurable eviction policy applies. The design is not a TCP reassembler. — [FlowBlaze](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)
- Resources: one stateful element uses 71,712 LUTs (16%) and 393 BRAM (26%). Six elements give about 200K flow entries at about 57% of LUTs and 85% of BRAM. — [FlowBlaze](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)
- Power: the FPGA draws 22 W with FlowBlaze, independent of packet rate, and the whole system about 107 W. The software mSwitch and eBPF versions draw 118 to 124 W. — [FlowBlaze](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)
- Note: the design is scheduled for consistency but no worst-case latency distribution under adversarial same-flow hashing is reported. This is my reading of the sections I read.

**P5. Iwasawa, Endoh, Maruyama, Matsumoto, Yamada (Hitachi), "Low and Deterministic Latency Firewall for Cybersecurity in Real-time Control Systems," Trans. SICE 56(2):51–56, 2020. Access: ABSTRACT plus tables only (the body is in Japanese and was not machine-translatable from the PDF).**
- This is the closest prior art to our gate. The firewall is for ICS control networks and matches rules on the fly as bytes stream through. To discard a malicious frame it modifies the Ethernet FCS (the frame is invalidated in flight rather than buffered), and it uses Shift-And for signature matching. Prototyped on an FPGA at 100BASE-TX, it does not limit wire-speed throughput, and its latency "ranges from 2.12 µs to 2.2 µs regardless of the frame size or the number of matching patterns". — [Iwasawa et al. 2020](https://www.jstage.jst.go.jp/article/sicetr/56/2/56_51/_article/-char/en)
- Implication: a published, FPGA-based, frame-size-independent ~2.2 µs latency claim for an ICS bump-in-the-wire already exists at 100 Mb/s. It enforces by FCS corruption, which drops the frame and leaves TCP to recover, unlike our session-preserving one-byte mutation. From what I could read there is no TCP state, no checksum-preserving rewrite, and no Modbus semantics.

**P6. Doran, Schneider, Leibundgut, Neuhaus (ZHAW) and Eberli (Duagon), "Towards Securing Hard Real Time Networked Embedded Devices and Systems: a cBPF Implementation for an FPGA," IEEE ETFA 2023. Access: FULL TEXT read (4 pages).**
- A classic BPF VM in an FPGA, aimed at PROFINET IRT nodes. It supports all 27 cBPF instructions and 256 instructions of program memory. Each instruction issues in 1 cycle and executes in 1 to 5 cycles. Execution stalls until the needed byte arrives, so "the frame must not be completely received before filtering can start". The core uses 912 ALMs, 1162 ALUTs and 2 DSPs on an Intel FPGA. — [Doran et al. ETFA 2023](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)
- No latency or throughput numbers are reported beyond the cycle counts. Verification used tcpdump filters in simulation. — [Doran et al.](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)
- Open problems the authors name:
  - cBPF has no state; "A concept of state, which the cBPF does not possess, is necessary."
  - Filters need to be cycle-aware and aware of receive-buffer size.
  - Adding state breaks differential verification against the software BPF.
  - Protocol-phase management, e.g. dropping PROFINET DCP Reset after initialization.
  - A "security profile" for system-wide policy.
  - [Doran et al.](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)
- Context: the PROFINET Netload certification suite consists largely of DoS tests. — [Doran et al.](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)

**P7. Meyer, Häckel, Korf, Schmidt, "Network Anomaly Detection in Cars based on Time-Sensitive Ingress Control," IEEE VTC-Fall 2020 workshop (NADCI). Access: FULL TEXT read. This is a simulation study in OMNeT++/CoRE4INET, not hardware.**
- Uses 802.1Qci PSFP (stream filters, time-gated stream gates, flow meters) as a zero-false-positive anomaly detector, because the TSN configuration is engineered in advance. The network is a 100 Mb/s zonal backbone. With a correct configuration there were no drops before the attack, i.e. no false positives. — [Meyer et al. 2020](https://core.inet.haw-hamburg.de/assets/bibliography/eigene/mhks-nadci-20.pdf)
- Limits: attacks that conform to the policy are false negatives. That covers attacks under the allowed bandwidth, frames of the allowed size (64 B CAN tunnels), and frames correctly timed in the stream-gate window. — [Meyer et al.](https://core.inet.haw-hamburg.de/assets/bibliography/eigene/mhks-nadci-20.pdf)
- Effect of DoS: a flood on a concurrent stream without Qci drove a victim stream's maximum end-to-end latency past 7 s within 20 s of simulation (unbounded queues). With Qci enabled the impact was mitigated. — [Meyer et al.](https://core.inet.haw-hamburg.de/assets/bibliography/eigene/mhks-nadci-20.pdf)

**P8. Ergenç, Schenderlein, Fischer, "TSNZeek: An Open-source Intrusion Detection System for IEEE 802.1 Time-sensitive Networking," arXiv:2303.11492 (2023). Access: FULL TEXT read.**
- A software IDS (Zeek plus a spicy parser for SRP and FRER) on an i3-9100 at 3.6 GHz in a real 3-bridge TSN testbed. CPU use was 25% at 50 Mb/s rising to 45% at 250 Mb/s, plus 25% for the detection module. Processing lag rose to 2 ms with load. The authors' own caveat: "time-sensitive frames with submillisecond latency requirements may already be delivered before an intrusion alert", and a prevention system "might require further improvements in data processing speed". — [TSNZeek arXiv](https://arxiv.org/pdf/2303.11492v1)
- Future work: improving the detection engine to "minimize redundant and false alerts". Inserting a non-TSN hub caused reordering that triggered false FRER alerts. — [TSNZeek](https://arxiv.org/pdf/2303.11492v1)

### Inferences
- No paper I read reports bounded worst-case latency under adversarial load, measured with full hardware timestamping, for an FPGA ICS enforcement device. Iwasawa reports a min–max range (2.12 to 2.2 µs) but, from what I could read, not under flood or with p99.99 or 10^6+ samples. Pigasus reports latency only at low load. This looks like a real methodological gap that the KR260 gate could fill.
- The TUM methodology (passive optical taps, a separate timestamper that stamps every packet, worst-N scatter plots, percentiles to 99.9999%, an explicit overload sweep) is the bar a reviewer will apply. At 10/100 Mb/s copper, the equivalent is a passive copper tap or a second NIC that hardware-timestamps every frame on both sides of the DuT (for example Intel i210/X550-class), or an FPGA-based timestamper.

### Gaps
- I could not read Iwasawa's Japanese body text, so their measurement method, sample counts and resource use are unknown.
- I could not obtain the full texts of Limago (FPL 2019, IEEE Xplore only) or the ETH FPGA TCP stack papers. A Formby et al. SIGMETRICS 2017 substation traffic PDF could not be fetched (the URL redirected to an HTML page).

## Is there a measurable regime where software enforcement misses OT deadlines while fabric enforcement does not?

### Takeaway
Yes, but it is the overload and burst regime, not the steady state. Tuned DPDK Snort and Suricata hold well under 100 µs at p99.999 while load stays below capacity. Per-core capacity with rules loaded is only about 70 kpkt/s (Snort 3) and about 200 kpkt/s (Suricata 7) on a 2.2 GHz Xeon-D. Once crossed, latency jumps to roughly 2 to 30 ms with loss. Untuned or shared-core deployments show 0.6 to 2.5 ms spikes at p99.99 even at 10 kpkt/s. A line-rate fabric pipeline has no such knee by construction. The defensible claim is the knee, not "µs vs ms" at idle.

### Cited Findings
- Snort 3 with rules overloads at 70 kpkt/s: p50 79 µs, p99 about 24.9 ms, max about 28 ms. Snort-fwd at 90 kpkt/s shows about 30 ms latency and 3.3% loss. The authors: "URLLC-compliant latency is only violated if the DuT is overloaded". — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Suricata with rules overloads at about 200 kpkt/s, with latency up to 2 ms and loss. On non-rt kernels it jumps to about 600 µs from p99.99 even when not overloaded. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Bursts of 32 to 64 packets at a mean of only 10 kpkt/s break the 1 ms target because of DPDK batch semantics. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf)
- Untuned Snort in a VM: p99.99 1.7 ms and p99.999 2.5 ms at 10 kpkt/s. Untuned Suricata: 1.8 ms spikes. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf); [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Co-location: an LLC-heavy neighbour cost a DPDK network function 64% of its performance (Herdrich et al., as cited by TUM). TLB shootdowns from memory management cause about 600 µs spikes that the authors could not configure away for Suricata on vanilla or no-hz kernels. — [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)
- Software IDS for TSN: processing lag up to 2 ms at 250 Mb/s on an i3. — [TSNZeek](https://arxiv.org/pdf/2303.11492v1)
- FPGA side: Iwasawa reports 2.12 to 2.2 µs independent of frame size and pattern count at 100 Mb/s wire speed. FlowBlaze reports under 1 µs at 40G line rate for 64 B frames. Pigasus reports about 3 µs fast path, but its OOO slow path does degrade under adversarial reordering (innocent goodput 81 to 90% at 10 Gb/s of attack traffic). — [Iwasawa](https://www.jstage.jst.go.jp/article/sicetr/56/2/56_51/_article/-char/en); [FlowBlaze](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf); [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- OT budgets: GOOSE trip and block messages are IEC 61850 transfer-time class TT6, 3 ms. Per an SEL technical paper this must be met 99.9999% of the time. One secondary source says IEC 61850-10 allocates about 20% of the transfer time to the network (about 600 µs). — [SEL papers via search, e.g. selinc.com/api/download/113983](https://selinc.com/api/download/113983) (search-result summary only; not read in full, and I could not map each claim to a specific SEL document)

### Inferences
- Line-rate arithmetic: a minimum 64 B frame occupies 84 B on the wire, so 100 Mb/s means 148.8 kpkt/s and 1 Gb/s means 1.488 Mpps. On that basis:
  - A single attacker saturating a 100 Mb/s link with minimum frames already exceeds the measured Snort-filter per-core capacity (70 kpkt/s) by about 2×, and approaches Suricata's (about 200 kpkt/s).
  - At 1 GbE the same flood exceeds both by 7 to 20× per core.
  - The measurements show this overload produces ms-scale latency and loss for legitimate traffic sharing the path, i.e. the same order as, or above, the 3 ms TT6 budget and the ~600 µs network share.
  - This is the measurable regime: small-frame floods at line rate.
- Our own platform's software baseline (Linux on the KR260's Cortex-A53 at about 1.3 GHz, in-order) is almost certainly weaker per core than the Xeon-D used by TUM, so its overload knee would come at lower packet rates. This is inferred, not measured. It should be measured, because it is the most natural "same board, software vs fabric" control.
- The "co-located AI workload" regime is plausible but unquantified for IPS latency in the literature I read. The only hard numbers are the 64% LLC-contention penalty and TLB-shootdown spikes. A reviewer would value a measured experiment: Suricata or a minimal Modbus filter on the A53 while an LLM or encoder workload runs on the other cores or DMA engines, against the fabric gate.
- The fabric advantage also has to survive the stateful adversarial cases that broke Pigasus's slow path: OOO and retransmission floods, SYN or connection-table exhaustion, hash-collision attacks on the flow table (FlowBlaze's same-flow stalls, cuckoo insertion). A credible claim is "bounded worst case including under these attacks", with the bound derived from the RTL (cycles after the last byte) and confirmed by measurement.

### Gaps
- None of the FPGA papers read reports p99.99 or maximum latency under flood with ≥10^6 hardware-timestamped samples. I found no published head-to-head of Suricata/Snort and an FPGA gate at 100 Mb/s to 1 GbE on Modbus/TCP.
- I found no measurement of Suricata/Snort latency on an ARM Cortex-A53, or on any embedded SoC, under load.
- I could not confirm the IEC 61850-10 "20% network share" against the standard text.

## Which open hardware problems do authors name, and has the bounded-latency ICS gate claim already been made?

### Takeaway
The bounded-latency claim at 100 Mb/s for an FPGA ICS firewall has already been published (Iwasawa et al. 2020, about 2.2 µs, frame-size independent). Novelty therefore has to come from three things none of the read works combine:
- stateful TCP and Modbus enforcement in the fabric,
- session-preserving refusal (checksum-correct rewrite instead of FCS kill),
- a rigorous tail-latency-under-attack evaluation against a tuned software baseline.

### Cited Findings
- Pigasus names out-of-order and slow-path robustness and residual CPU bottlenecks as open problems, and proposes moving more onto the FPGA. — [Pigasus](https://www.usenix.org/system/files/osdi20-zhao_zhipeng.pdf)
- FlowBlaze names stateful consistency without stalls and TCAM size limits; its EFSM table is only 32 entries "due to the technical challenges of implementing a TCAM". — [FlowBlaze](https://www.usenix.org/system/files/nsdi19-pontarelli.pdf)
- Doran et al. name adding state to FPGA filters, cycle- and buffer-awareness for isochronous traffic, preserving differential V&V once state exists, and protocol-phase management. — [Doran et al.](https://digitalcollection.zhaw.ch/bitstream/11475/28963/3/2023_Doran-etal_Hard-real-time-networked-embedded-devices-and-systems_EFTA.pdf)
- Meyer et al. show that TSN PSFP is a zero-false-positive but semantics-blind enforcement layer, so policy-conforming attacks pass. TSNZeek shows that software IDS lag (up to 2 ms) disqualifies it for prevention on sub-ms TSN streams. — [Meyer et al.](https://core.inet.haw-hamburg.de/assets/bibliography/eigene/mhks-nadci-20.pdf); [TSNZeek](https://arxiv.org/pdf/2303.11492v1)
- The TUM group names energy cost (+48%), dedicated cores and QoS cross-talk from co-hosted services as the price of software determinism. — [NOMS 2020](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_noms2020.pdf); [JNSM](https://www.net.in.tum.de/fileadmin/bibtex/publications/papers/gallenmueller_jnsm2022.pdf)

### Inferences
- What a reviewer would accept as an evaluation:
  1. Baselines:
     - Suricata 7 with DPDK (or AF_PACKET inline) on an x86 mini-PC, tuned per TUM Table 1 (isolcpus, nohz_full, rt kernel, C-states off, CAT where available), with an equivalent Modbus ruleset.
     - The same or a minimal filter on the KR260's own A53 under Linux. The R5 might also run a bare-metal version.
     - The fabric gate.
  2. Instrumentation: a separate hardware timestamper on passive taps, with per-packet matching. Report p50, p99, p99.9, p99.99, p99.999 and max, plus worst-5000 scatter plots, for runs of at least 60 s, repeated.
  3. Load sweep: from 1 kpkt/s up to line rate with 64 B frames, plus bursts of 32 to 64 packets. Find each system's knee.
  4. Adversarial suites: SYN floods, many concurrent connections up to the table limit, OOO and retransmission floods, malformed checksums, hash-collision streams, and a co-located AI workload on the CPU side.
  5. Report legitimate Modbus request-response latency and loss under each condition against the deadlines (3 ms TT6 or ~600 µs network share where relevant, and PLC scan time).
- Positioning versus Iwasawa: they enforce by corrupting the FCS, which drops the frame and leaves the TCP session to retransmit. We enforce by checksum-consistent in-session mutation. That changes what happens to the PLC session under refusal, which is a measurable difference (session survival and recovery time). This is the clearest hardware-level novelty axis I found.

### Gaps
- I found no paper evaluating bump-in-the-wire security devices against IEC 62443 conduit latency requirements. IEC 62443 does not appear to specify numeric latency, though I could not verify this from the standard.
- I found no FPGA implementation of 802.1Qci PSFP with an attack evaluation. Searches surfaced simulation studies (Meyer et al.; a Tübingen PSFP simulation) and a patent, but no hardware measurement.
