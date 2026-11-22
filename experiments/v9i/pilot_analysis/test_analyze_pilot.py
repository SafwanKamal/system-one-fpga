"""Tests for analyze_pilot.py exercising GO, NO-GO-identity, NO-GO-slower, and all supported input formats."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPT = HERE / "analyze_pilot.py"

sys.path.insert(0, str(HERE))
import analyze_pilot  # noqa: E402


class AnalyzePilotTest(unittest.TestCase):
    def test_go_fixture(self) -> None:
        rc13 = analyze_pilot.load_records([FIXTURES / "rc13_bench.json"])
        pilot = analyze_pilot.load_records([FIXTURES / "pilot_go_bench.json"])
        rep = analyze_pilot.analyze(rc13, pilot)
        self.assertEqual(rep["verdict"], "GO")
        self.assertTrue(rep["go"])
        self.assertTrue(rep["go_line"].startswith("GO:"))
        self.assertTrue(rep["identity"]["passed"])
        self.assertEqual(rep["identity"]["identical_queries"], 21)
        self.assertEqual(rep["identity"]["total_queries"], 21)
        self.assertEqual(len(rep["by_category"]), 3)
        self.assertGreaterEqual(rep["overall"]["decode_speedup"], 1.30)
        self.assertIsNotNone(rep["measured_vs_modelled"]["tool"])
        self.assertAlmostEqual(rep["measured_vs_modelled"]["tool"]["modelled_speedup"], 1.31)
        self.assertAlmostEqual(rep["measured_vs_modelled"]["overall"]["modelled_speedup"], 1.065)

    def test_nogo_identity_fixture(self) -> None:
        rc13 = analyze_pilot.load_records([FIXTURES / "rc13_bench.json"])
        pilot = analyze_pilot.load_records([FIXTURES / "pilot_nogo_identity_bench.json"])
        rep = analyze_pilot.analyze(rc13, pilot)
        self.assertEqual(rep["verdict"], "NO-GO")
        self.assertFalse(rep["go"])
        self.assertFalse(rep["identity"]["passed"])
        self.assertEqual(rep["identity"]["identical_queries"], 20)
        self.assertEqual(len(rep["identity"]["failing_queries"]), 1)
        self.assertEqual(rep["identity"]["failing_queries"][0]["first_diff_index"], 3)
        self.assertIn("identity failed", rep["go_line"])

    def test_nogo_slower_fixture(self) -> None:
        rc13 = analyze_pilot.load_records([FIXTURES / "rc13_bench.json"])
        pilot = analyze_pilot.load_records([FIXTURES / "pilot_nogo_slower_bench.json"])
        rep = analyze_pilot.analyze(rc13, pilot)
        self.assertEqual(rep["verdict"], "NO-GO")
        self.assertFalse(rep["go"])
        self.assertTrue(rep["identity"]["passed"])
        self.assertLess(rep["overall"]["decode_speedup"], 1.0)
        self.assertIn("slower than threshold", rep["go_line"])

    def test_bench_json_stdout_and_pilot_cases_formats(self) -> None:
        rc13_rows = json.loads((FIXTURES / "rc13_bench.json").read_text(encoding="utf-8"))
        go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))
        workload_rc13 = {
            "passed": True,
            "cases": [
                {
                    "key": "case-gen-0",
                    "index": 0,
                    "domain": "general",
                    "prefill_seconds": 1.2,
                    "identical": True,
                    "ar": {"tokens": [10, 20, 30], "logit_bits": [1, 2, 3], "kv_sha256": "abc", "decode_seconds": 4.0},
                    "candidate": {"tokens": [10, 20, 30], "logit_bits": [1, 2, 3], "kv_sha256": "abc", "decode_seconds": 3.0},
                }
            ],
        }
        workload_pilot = {
            "passed": True,
            "cases": [
                {
                    "key": "case-gen-0",
                    "index": 0,
                    "domain": "general",
                    "prefill_seconds": 1.1,
                    "identical": True,
                    "ar": {"tokens": [10, 20, 30], "logit_bits": [1, 2, 3], "kv_sha256": "abc", "decode_seconds": 3.8},
                    "candidate": {"tokens": [10, 20, 30], "logit_bits": [1, 2, 3], "kv_sha256": "abc", "decode_seconds": 2.7},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_log = tmp / "rc13.stdout"
            go_log = tmp / "go.stdout"
            w_rc13 = tmp / "w_rc13.json"
            w_pilot = tmp / "w_pilot.json"
            out_json = tmp / "out.json"
            rc13_log.write_text("some header\nBENCH-JSON " + json.dumps(rc13_rows) + "\n", encoding="utf-8")
            go_log.write_text("some header\nBENCH-JSON " + json.dumps(go_rows) + "\n", encoding="utf-8")
            w_rc13.write_text(json.dumps(workload_rc13), encoding="utf-8")
            w_pilot.write_text(json.dumps(workload_pilot), encoding="utf-8")

            r_go = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_log), str(w_rc13), "--pilot", str(go_log), str(w_pilot), "--out", str(out_json), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_go.returncode, 0, r_go.stdout + r_go.stderr)
            self.assertIn("GO:", r_go.stdout)
            saved = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(saved["identity"]["total_queries"], 22)
            self.assertIn("general", saved["by_category"])

            r_fail = subprocess.run(
                [sys.executable, str(SCRIPT), str(FIXTURES / "rc13_bench.json"), str(FIXTURES / "pilot_nogo_identity_bench.json"), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_fail.returncode, 1)
            self.assertIn("NO-GO:", r_fail.stdout)

            r_slow = subprocess.run(
                [sys.executable, str(SCRIPT), str(FIXTURES / "rc13_bench.json"), str(FIXTURES / "pilot_nogo_slower_bench.json"), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_slow.returncode, 1)
            self.assertIn("NO-GO:", r_slow.stdout)


if __name__ == "__main__":
    unittest.main()
