"""Resource and latency estimates for the Nexys 4 DDR (Artix-7 XC7A100T).

These are analytical estimates, not measurements. They are here because the
project's headline claim is a latency and energy comparison, and it is worth
knowing before writing any RTL whether the interesting number is compute at all.
It is not: at 115,200 baud the link costs roughly three orders of magnitude more
than the arithmetic, so a compute-only latency figure would be close to
meaningless on its own.

Every assumption is a named field on ``HwAssumptions`` so it can be replaced with
a measured value later. Nothing here should be quoted as a result; quote it as a
budget, and quote Vivado numbers as estimates too until the USB power meter says
otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Datasheet quantities for the board, not assumptions.
XC7A100T = {
    "slices": 15850,
    "dsp48e1": 240,
    "bram_36k": 135,
    "bram_KiB": 4860 * 1024 / 8 / 1024,
    "ddr2_MiB": 128,
    "ddr2_width_bits": 16,
}


@dataclass
class HwAssumptions:
    fabric_mhz: float = 100.0          # Nexys 4 DDR onboard oscillator
    mac_lanes: int = 64                # parallel MACs; <= dsp48e1, leaves headroom
    bram_read_bytes_per_cycle: int = 8 # one 64-bit BRAM port
    ddr2_random_row_cycles: int = 30   # MIG user-clock latency for a scattered read
    ddr2_burst_bytes: int = 32         # bytes returned per random access
    uart_baud: int = 115_200
    uart_bits_per_byte: int = 10       # 8N1
    eth_mbps: float = 100.0
    eth_efficiency: float = 0.6        # RMII + framing + stack overhead
    eth_fixed_us: float = 120.0        # per-packet fixed cost, generous


@dataclass
class LatencyBudget:
    compute_us: float
    transport_us: float
    detail: dict = field(default_factory=dict)

    @property
    def total_us(self) -> float:
        return self.compute_us + self.transport_us

    @property
    def transport_share(self) -> float:
        return self.transport_us / max(self.total_us, 1e-9)


def compute_latency_us(n_tokens: int, dim: int, hidden: int, n_classes: int,
                       emb_bits: int, in_bram: bool, hw: HwAssumptions) -> LatencyBudget:
    """Cycles for one inference, split into the three stages that dominate."""
    row_bytes = max(1, dim * emb_bits // 8)

    if in_bram:
        fetch_cycles = n_tokens * max(1, -(-row_bytes // hw.bram_read_bytes_per_cycle))
    else:
        # Scattered DDR2 reads: latency per row, partially hidden by pipelining the
        # next request behind the current one. Assumed half-hidden, which is
        # optimistic for a naive controller and pessimistic for a good one.
        per_row = hw.ddr2_random_row_cycles * 0.5 + max(1, -(-row_bytes // hw.ddr2_burst_bytes))
        fetch_cycles = n_tokens * per_row

    mac1 = -(-(dim * hidden) // hw.mac_lanes)
    mac2 = -(-(hidden * n_classes) // hw.mac_lanes)
    total_cycles = fetch_cycles + mac1 + mac2 + 64  # +64 for requantise/argmax/control
    us = total_cycles / hw.fabric_mhz

    return LatencyBudget(compute_us=us, transport_us=0.0, detail={
        "fetch_cycles": round(fetch_cycles, 1),
        "mac1_cycles": mac1, "mac2_cycles": mac2,
        "total_cycles": round(total_cycles, 1),
        "embedding_location": "BRAM" if in_bram else "DDR2",
    })


def transport_latency_us(payload_bytes: int, link: str, hw: HwAssumptions) -> float:
    if link == "uart":
        return payload_bytes * hw.uart_bits_per_byte / hw.uart_baud * 1e6
    if link == "ethernet":
        return hw.eth_fixed_us + payload_bytes * 8 / (hw.eth_mbps * 1e6 * hw.eth_efficiency) * 1e6
    raise ValueError(link)


def corpus_payload_stats(texts: list[str], token_counts: np.ndarray) -> dict:
    """Bytes on the wire, for both framings the plan considers.

    Host-side tokenisation sends 2-byte ids and is the smaller payload only when
    the average word is longer than two characters, which it is. On-chip hashing
    sends raw text and removes the host from the loop entirely -- the reason it is
    a stretch goal rather than a simplification.
    """
    char_lens = np.array([len(t.encode("utf-8")) for t in texts])
    framing = 6  # 2 sync + 1 len + 1 type + 2 CRC16, matching the existing framer
    return {
        "n": len(texts),
        "chars_mean": float(char_lens.mean()), "chars_p95": float(np.percentile(char_lens, 95)),
        "tokens_mean": float(token_counts.mean()), "tokens_p95": float(np.percentile(token_counts, 95)),
        "payload_token_ids_mean": float(2 * token_counts.mean() + framing),
        "payload_token_ids_p95": float(2 * np.percentile(token_counts, 95) + framing),
        "payload_raw_text_mean": float(char_lens.mean() + framing),
        "payload_raw_text_p95": float(np.percentile(char_lens, 95) + framing),
    }


def budget_table(stats: dict, dim: int, hidden: int, n_classes: int, emb_bits: int,
                 in_bram: bool, hw: HwAssumptions | None = None) -> list[dict]:
    hw = hw or HwAssumptions()
    rows = []
    for framing, key in (("token ids (host tokenises)", "payload_token_ids_mean"),
                         ("raw text (on-chip hashing)", "payload_raw_text_mean")):
        for link in ("uart", "ethernet"):
            comp = compute_latency_us(int(round(stats["tokens_mean"])), dim, hidden,
                                      n_classes, emb_bits, in_bram, hw)
            tx = transport_latency_us(int(round(stats[key])), link, hw)
            rows.append({
                "framing": framing, "link": link,
                "payload_bytes": round(stats[key], 1),
                "compute_us": round(comp.compute_us, 2),
                "transport_us": round(tx, 2),
                "total_us": round(comp.compute_us + tx, 2),
                "transport_share": round(tx / (comp.compute_us + tx), 4),
                "cycles": comp.detail["total_cycles"],
            })
    return rows


def resource_estimate(dim: int, hidden: int, n_classes: int, emb_bits: int,
                      head_bits: int, n_buckets: int, hw: HwAssumptions | None = None) -> dict:
    """Rough fit against the part. The BRAM number is the one that actually binds."""
    hw = hw or HwAssumptions()
    emb_kib = n_buckets * dim * max(emb_bits, 2) / 8 / 1024
    head_kib = (dim * hidden + hidden * n_classes) * max(head_bits, 2) / 8 / 1024
    return {
        "embedding_KiB": emb_kib, "head_KiB": head_kib,
        "bram_KiB_available": XC7A100T["bram_KiB"],
        "fits_all_in_bram": (emb_kib + head_kib) <= XC7A100T["bram_KiB"],
        "head_only_bram_utilisation": head_kib / XC7A100T["bram_KiB"],
        "dsp_used_estimate": hw.mac_lanes,
        "dsp_available": XC7A100T["dsp48e1"],
        "dsp_utilisation": hw.mac_lanes / XC7A100T["dsp48e1"],
        "note": ("DSP count assumes one DSP48E1 per MAC lane. 8-bit operands can be "
                 "packed two-per-DSP on Artix-7, so the real DSP count may be about "
                 "half this; 4-bit and ternary lanes map to LUTs instead and would "
                 "trade DSP pressure for slice pressure."),
    }
