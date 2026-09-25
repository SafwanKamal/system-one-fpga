"""Host side of the board's raw-Ethernet classify protocol.

    uv run python scripts/sysone_ethernet_client.py --list-interfaces
    uv run python scripts/sysone_ethernet_client.py -i "Ethernet 2" "what is my credit score"
    uv run python scripts/sysone_ethernet_client.py -i "Ethernet 2" --test-set 500    # accuracy + latency

Uses scapy, like Genome-Classifier's decode_ethernet_result.py; on Windows that
needs Npcap. Raw frames need no IP configuration, but the host must be on the same
link as the board (a direct cable is simplest).

The encoder and decoder are src/sysone/ethernet_protocol.py, the same code the RTL
testbench vectors were built and checked with.

Round-trip latency here is measured in Python on the host, so it includes the
operating system's packet path and is an upper bound on the wire time. It is the
right number for the cascade comparison, since a real host pays it too, but quote
it as host-measured.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sysone import ethernet_protocol as ep      # noqa: E402


def load_calibration(export_dir: Path) -> tuple[float, list[str] | None]:
    manifest = json.loads((export_dir / "manifest.json").read_text())
    labels = None
    try:
        from sysone.data import load_clinc150
        labels = load_clinc150().labels
    except Exception:
        pass
    return manifest["arithmetic"]["s_out"], labels


OOS_CLASS = 150

# Answer "oos" when the top probability is below this. Chosen on the validation
# split to give up at most 1 point of in-scope accuracy (scripts/oos_tradeoff.py):
# on the test split OOS recall goes from 0.447 to 0.712 while in-scope accuracy
# goes from 0.9071 to 0.9024. Over three training seeds: 0.708 +- 0.015 recall.
# The probabilities themselves are unchanged, so calibration is unaffected.
DEFAULT_OOS_THRESHOLD = 0.32


def decide(p: np.ndarray, threshold: float) -> int:
    """The board's argmax, or oos when the model is not confident enough."""
    return OOS_CLASS if p.max() < threshold else int(p.argmax())


def probabilities(logits: list[int], s_out: float) -> np.ndarray:
    z = np.asarray(logits, dtype=np.float64) * s_out
    z -= z.max()
    p = np.exp(z)
    return p / p.sum()


class Board:
    def __init__(self, interface: str, fpga_mac: str, timeout: float):
        from scapy.all import get_if_hwaddr
        self.interface = interface
        self.host_mac = get_if_hwaddr(interface)
        self.fpga_mac = ep.mac_bytes(fpga_mac)
        self.timeout = timeout
        self.sequence = int(time.time()) & 0xFFFF_0000

    def classify(self, text: str, retries: int = 2) -> tuple[ep.ClassifyResult, float]:
        from scapy.all import AsyncSniffer, Ether, Raw, sendp

        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        frame = ep.encode_request_frame(text, self.sequence, self.host_mac, self.fpga_mac,
                                        with_fcs=False)   # the NIC appends the FCS
        bpf = f"ether proto 0x{ep.ETHERTYPE:04x} and ether src {ep.mac_string(self.fpga_mac)}"

        for _ in range(retries + 1):
            sniffer = AsyncSniffer(iface=self.interface, filter=bpf, store=True, count=1,
                                   timeout=self.timeout,
                                   lfilter=lambda p: self._is_ours(p))
            sniffer.start()
            time.sleep(0.01)                      # let the capture open before sending
            start = time.perf_counter()
            sendp(Ether(frame), iface=self.interface, verbose=False)
            sniffer.join()
            elapsed = time.perf_counter() - start
            if sniffer.results:
                raw = bytes(sniffer.results[0])
                return ep.decode_result_frame(raw, has_fcs=False), elapsed
        raise TimeoutError(f"no result for sequence {self.sequence} after {retries + 1} tries")

    def _is_ours(self, packet) -> bool:
        try:
            result = ep.decode_result_frame(bytes(packet), has_fcs=False)
        except ep.ProtocolError:
            return False
        return result.sequence_number == self.sequence


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="*", help="utterances to classify")
    ap.add_argument("-i", "--interface", help="network interface wired to the board")
    ap.add_argument("--fpga-mac", default=ep.mac_string(ep.FPGA_MAC))
    ap.add_argument("--timeout", type=float, default=0.5, help="seconds to wait per try")
    ap.add_argument("--export", default=str(ROOT / "export/student_bram_max"))
    ap.add_argument("--test-set", type=int, default=0,
                    help="send the first N CLINC150 test utterances and report accuracy and latency")
    ap.add_argument("--oos-threshold", type=float, default=DEFAULT_OOS_THRESHOLD,
                    help="answer oos below this top probability (0 = plain argmax)")
    ap.add_argument("--list-interfaces", action="store_true")
    args = ap.parse_args()

    if args.list_interfaces:
        from scapy.all import show_interfaces
        show_interfaces()
        return
    if not args.interface:
        ap.error("--interface is required (see --list-interfaces)")

    s_out, labels = load_calibration(Path(args.export))
    board = Board(args.interface, args.fpga_mac, args.timeout)
    print(f"host {board.host_mac} -> board {args.fpga_mac} on {args.interface}")

    for text in args.text:
        result, elapsed = board.classify(text)
        p = probabilities(result.logits, s_out)
        decision = decide(p, args.oos_threshold)
        name = labels[decision] if labels else str(decision)
        if decision != result.class_index:
            name += f" (board argmax {labels[result.class_index] if labels else result.class_index}, p below threshold)"
        print(f"{text!r}\n  -> {name}  p={p.max():.3f}  margin={result.margin}"
              f"  features={result.feature_count}  round trip {elapsed * 1e3:.2f} ms")

    if args.test_set:
        from sysone.data import load_clinc150
        ds = load_clinc150()
        n = min(args.test_set, len(ds.test.texts))
        correct, times = 0, []
        for i in range(n):
            result, elapsed = board.classify(ds.test.texts[i])
            decision = decide(probabilities(result.logits, s_out), args.oos_threshold)
            correct += int(decision == ds.test.y[i])
            times.append(elapsed)
        t = np.asarray(times) * 1e3
        print(f"{n} test utterances: accuracy {correct / n:.4f} (combined, in-scope + OOS)")
        print(f"round trip ms: median {np.median(t):.3f}  p95 {np.percentile(t, 95):.3f}"
              f"  min {t.min():.3f}  (host-measured)")


if __name__ == "__main__":
    main()
