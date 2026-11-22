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
        self.assertEqual(rep["measured_vs_modelled"]["tool"]["metric"], "e2e")
        self.assertAlmostEqual(rep["measured_vs_modelled"]["tool"]["modelled_speedup"], 1.31)
        self.assertAlmostEqual(rep["measured_vs_modelled"]["overall"]["modelled_speedup"], 1.065)
        self.assertEqual(rep["measured_vs_modelled"]["overall"]["metric"], "e2e")
        for key in ("measured_decode_speedup", "decode_measured_over_modelled", "decode_delta_vs_modelled"):
            self.assertNotIn(key, rep["measured_vs_modelled"]["tool"])
            self.assertNotIn(key, rep["measured_vs_modelled"]["overall"])
        scope = rep["measured_vs_modelled"]["scope"]
        self.assertEqual(scope["measured_cases"], 21)
        self.assertEqual(scope["modelled_workload_cases"], 181)
        self.assertFalse(scope["matches_model_scope"])
        self.assertAlmostEqual(scope["modelled_overall_decode_speedup"], 0.884)
        rendered = analyze_pilot.format_report(rep)
        self.assertIn("181-case", rendered)
        self.assertIn("0.884x", rendered)
        self.assertIn("Tool E2E:", rendered)
        self.assertIn("Overall E2E:", rendered)

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

    def test_duplicate_query_ids_detects_earlier_token_mismatch(self) -> None:
        def row(tokens: list[int], dec: float, e2e: float) -> dict:
            return {
                "query": "same",
                "ok": True,
                "complete": True,
                "generated_ids": tokens,
                "path": "/proc/uptime",
                "prefill_seconds": e2e - dec,
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_path = tmp / "rc13.json"
            pilot_path = tmp / "pilot.json"
            rc13_path.write_text(json.dumps([row([7], 2.0, 3.0), row([7], 2.0, 3.0)]), encoding="utf-8")
            pilot_path.write_text(json.dumps([row([8], 1.0, 2.0), row([7], 1.0, 2.0)]), encoding="utf-8")

            rep = analyze_pilot.analyze(
                analyze_pilot.load_records([rc13_path]),
                analyze_pilot.load_records([pilot_path]),
            )
            self.assertEqual(rep["verdict"], "NO-GO")
            self.assertFalse(rep["go"])
            self.assertFalse(rep["identity"]["passed"])
            self.assertEqual(rep["identity"]["total_queries"], 2)
            self.assertEqual(rep["identity"]["identical_queries"], 1)
            self.assertEqual(len(rep["identity"]["failing_queries"]), 1)
            self.assertEqual(rep["identity"]["failing_queries"][0]["first_diff_index"], 0)
            self.assertEqual(rep["identity"]["failing_queries"][0]["occurrence"], 0)

            # Mismatched duplicate counts must also fail identity.
            pilot_path.write_text(json.dumps([row([7], 1.0, 2.0)]), encoding="utf-8")
            rep_missing = analyze_pilot.analyze(
                analyze_pilot.load_records([rc13_path]),
                analyze_pilot.load_records([pilot_path]),
            )
            self.assertEqual(rep_missing["verdict"], "NO-GO")
            self.assertEqual(rep_missing["identity"]["missing_in_pilot"], ["same"])

    def test_pilot_json_top_level_status_and_interrupted_snapshots(self) -> None:
        def make_pilot_doc(**extra: object) -> dict:
            doc = {
                "cases": [
                    {
                        "key": "case-0",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 2], "decode_seconds": 2.0},
                        "candidate": {"tokens": [1, 2], "decode_seconds": 1.0},
                    }
                ]
            }
            doc.update(extra)
            return doc

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            good_rc13 = tmp / "good_rc13.json"
            bad_pilot = tmp / "bad_pilot.json"
            missing_passed = tmp / "missing_passed.json"
            interrupted_snap = tmp / "interrupted_snap.json"
            bad_rc13 = tmp / "bad_rc13.json"
            good_pilot = tmp / "good_pilot.json"

            good_rc13.write_text(json.dumps(make_pilot_doc(passed=True, started_utc="2026-11-22T00:00:00Z", finished_utc="2026-11-22T00:01:00Z")), encoding="utf-8")
            good_pilot.write_text(
                json.dumps({
                    "passed": True,
                    "started_utc": "2026-11-22T00:00:00Z",
                    "finished_utc": "2026-11-22T00:01:00Z",
                    "cases": [
                        {
                            "key": "case-0",
                            "domain": "general",
                            "prefill_seconds": 0.8,
                            "identical": True,
                            "ar": {"tokens": [1, 2], "decode_seconds": 1.5},
                            "candidate": {"tokens": [1, 2], "decode_seconds": 0.7},
                        }
                    ],
                }),
                encoding="utf-8",
            )
            bad_pilot.write_text(json.dumps(make_pilot_doc(passed=False, error="interrupted")), encoding="utf-8")
            missing_passed.write_text(json.dumps(make_pilot_doc()), encoding="utf-8")
            interrupted_snap.write_text(json.dumps(make_pilot_doc(passed=True, started_utc="2026-11-22T00:00:00Z")), encoding="utf-8")
            bad_rc13.write_text(json.dumps(make_pilot_doc(passed=False)), encoding="utf-8")

            for bad_path in (bad_pilot, missing_passed, interrupted_snap, bad_rc13):
                with self.subTest(bad_path=bad_path.name):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([bad_path])

            cli_bad = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(good_rc13), "--pilot", str(bad_pilot), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(cli_bad.returncode, 0)
            self.assertNotIn("GO:", cli_bad.stdout)

            # Failed baseline input must also be rejected.
            cli_bad_rc13 = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(bad_rc13), "--pilot", str(good_pilot), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(cli_bad_rc13.returncode, 0)
            self.assertNotIn("GO:", cli_bad_rc13.stdout)

            # Valid terminal snapshots succeed.
            rep_ok = analyze_pilot.analyze(
                analyze_pilot.load_records([good_rc13]),
                analyze_pilot.load_records([good_pilot]),
            )
            self.assertEqual(rep_ok["verdict"], "GO")

    def test_full_precision_gating_no_rounding_false_go(self) -> None:
        def rec(dec: float, e2e: float) -> dict:
            return {
                "query": "q1",
                "ok": True,
                "complete": True,
                "generated_ids": [1, 2, 3],
                "path": "/proc/uptime",
                "prefill_seconds": e2e - dec,
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_path = tmp / "rc13.json"
            pilot_path = tmp / "pilot.json"
            rc13_path.write_text(json.dumps([rec(1.02996, 1.99996)]), encoding="utf-8")
            pilot_path.write_text(json.dumps([rec(1.0, 2.0)]), encoding="utf-8")

            rep = analyze_pilot.analyze(
                analyze_pilot.load_records([rc13_path]),
                analyze_pilot.load_records([pilot_path]),
            )
            self.assertEqual(rep["verdict"], "NO-GO")
            self.assertFalse(rep["go"])
            self.assertLess(rep["overall"]["decode_speedup"], 1.03)
            self.assertLess(rep["overall"]["e2e_speedup"], 1.00)
            self.assertIn("NO-GO:", rep["go_line"])
            self.assertIn("1.02996", rep["go_line"])
            self.assertIn("0.99998", rep["go_line"])

            # Exact threshold passes.
            rc13_path.write_text(json.dumps([rec(1.03, 2.0)]), encoding="utf-8")
            rep_pass = analyze_pilot.analyze(
                analyze_pilot.load_records([rc13_path]),
                analyze_pilot.load_records([pilot_path]),
            )
            self.assertEqual(rep_pass["verdict"], "GO")

    def test_disjoint_query_ids_cli_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_path = tmp / "rc13.json"
            pilot_path = tmp / "pilot.json"
            rc13_path.write_text(
                json.dumps([{"query": "only-rc13", "ok": True, "complete": True, "generated_ids": [1], "decode_seconds": 1.0, "elapsed_seconds": 2.0}]),
                encoding="utf-8",
            )
            pilot_path.write_text(
                json.dumps([{"query": "only-pilot", "ok": True, "complete": True, "generated_ids": [1], "decode_seconds": 0.5, "elapsed_seconds": 1.0}]),
                encoding="utf-8",
            )

            r_check = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_path), "--pilot", str(pilot_path), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_check.returncode, 1, r_check.stderr)
            self.assertIn("NO-GO:", r_check.stdout)
            self.assertIn("OVERALL (n=0): no matched queries", r_check.stdout)

            r_nocheck = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_path), "--pilot", str(pilot_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_nocheck.returncode, 0, r_nocheck.stderr)
            self.assertIn("NO-GO:", r_nocheck.stdout)


if __name__ == "__main__":
    unittest.main()
