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
        def row(tokens: list[int], dec: float, e2e: float, *, speculate: str = "rc1.3-costaware") -> dict:
            return {
                "query": "same",
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "prefix_tokens_reused": 32,
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
            rc13_path.write_text(
                json.dumps([
                    row([7], 2.0, 3.0, speculate="rc1.3-costaware"),
                    row([7], 2.0, 3.0, speculate="rc1.3-costaware"),
                ]),
                encoding="utf-8",
            )
            pilot_path.write_text(
                json.dumps([
                    row([8], 1.0, 2.0, speculate="rc1.4-costaware"),
                    row([7], 1.0, 2.0, speculate="rc1.4-costaware"),
                ]),
                encoding="utf-8",
            )

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
            pilot_path.write_text(json.dumps([row([7], 1.0, 2.0, speculate="rc1.4-costaware")]), encoding="utf-8")
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
                        "ar": {"tokens": [1, 2], "logit_bits": [101, 102], "kv_sha256": "kv0", "decode_seconds": 2.0},
                        "candidate": {"tokens": [1, 2], "logit_bits": [101, 102], "kv_sha256": "kv0", "decode_seconds": 1.0},
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
                            "ar": {"tokens": [1, 2], "logit_bits": [101, 102], "kv_sha256": "kv0", "decode_seconds": 1.5},
                            "candidate": {"tokens": [1, 2], "logit_bits": [101, 102], "kv_sha256": "kv0", "decode_seconds": 0.7},
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

            # Error snapshot even with finished_utc remains ineligible.
            err_finished = tmp / "err_finished.json"
            err_finished.write_text(
                json.dumps(make_pilot_doc(
                    passed=False,
                    started_utc="2026-11-22T00:00:00Z",
                    finished_utc="2026-11-22T00:01:00Z",
                    error="RuntimeError: board timeout",
                )),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                analyze_pilot.load_records([err_finished])

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
        def rec(dec: float, e2e: float, *, speculate: str = "rc1.3-costaware") -> dict:
            return {
                "query": "q1",
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "prefix_tokens_reused": 32,
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
            rc13_path.write_text(json.dumps([rec(1.02996, 1.99996, speculate="rc1.3-costaware")]), encoding="utf-8")
            pilot_path.write_text(json.dumps([rec(1.0, 2.0, speculate="rc1.4-costaware")]), encoding="utf-8")

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
            rc13_path.write_text(json.dumps([rec(1.03, 2.0, speculate="rc1.3-costaware")]), encoding="utf-8")
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

    def test_completed_v9h_pilot_failure_cli_reports_nogo(self) -> None:
        ref_doc = {
            "passed": True,
            "started_utc": "2026-11-22T00:00:00Z",
            "finished_utc": "2026-11-22T00:02:00Z",
            "cases": [
                {
                    "key": "case-0",
                    "index": 0,
                    "domain": "general",
                    "prefill_seconds": 1.0,
                    "ar_equal_v9e": True,
                    "candidate_equal_v9e": True,
                    "identical": True,
                    "ar": {"tokens": [10, 20], "logit_bits": [1, 2], "kv_sha256": "aaa", "decode_seconds": 2.0},
                    "candidate": {"tokens": [10, 20], "logit_bits": [1, 2], "kv_sha256": "aaa", "decode_seconds": 1.8},
                },
                {
                    "key": "case-5",
                    "index": 5,
                    "domain": "general",
                    "prefill_seconds": 1.2,
                    "ar_equal_v9e": True,
                    "candidate_equal_v9e": True,
                    "identical": True,
                    "ar": {"tokens": [10, 11], "logit_bits": [3, 4], "kv_sha256": "bbb", "decode_seconds": 2.2},
                    "candidate": {"tokens": [10, 11], "logit_bits": [3, 4], "kv_sha256": "bbb", "decode_seconds": 2.0},
                },
            ],
        }
        cand_fail_doc = {
            "passed": False,
            "started_utc": "2026-11-22T01:00:00Z",
            "finished_utc": "2026-11-22T01:02:00Z",
            "cases": [
                {
                    "key": "case-0",
                    "index": 0,
                    "domain": "general",
                    "prefill_seconds": 0.9,
                    "ar_equal_v9e": True,
                    "candidate_equal_v9e": True,
                    "identical": True,
                    "ar": {"tokens": [10, 20], "logit_bits": [1, 2], "kv_sha256": "aaa", "decode_seconds": 1.9},
                    "candidate": {"tokens": [10, 20], "logit_bits": [1, 2], "kv_sha256": "aaa", "decode_seconds": 1.2},
                },
                {
                    "key": "case-5",
                    "index": 5,
                    "domain": "general",
                    "prefill_seconds": 1.0,
                    "ar_equal_v9e": True,
                    "candidate_equal_v9e": False,
                    "identical": False,
                    "ar": {"tokens": [10, 11], "logit_bits": [3, 4], "kv_sha256": "bbb", "decode_seconds": 2.1},
                    "candidate": {"tokens": [10, 12], "logit_bits": [3, 9], "kv_sha256": "ccc", "decode_seconds": 1.4},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_p = tmp / "rc13_pilot.json"
            fail_p = tmp / "v9i_pilot.json"
            out_p = tmp / "report.json"
            rc13_p.write_text(json.dumps(ref_doc), encoding="utf-8")
            fail_p.write_text(json.dumps(cand_fail_doc), encoding="utf-8")

            r_report = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(fail_p), "--out", str(out_p)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_report.returncode, 0, r_report.stderr)
            self.assertIn("=== (a) Output Identity vs RC1.3 ===", r_report.stdout)
            self.assertIn("[MATCH] case-0", r_report.stdout)
            self.assertIn("[DIFF(idx=1)] case-5", r_report.stdout)
            self.assertIn("NO-GO: identity failed (1/2 identical, top-level passed=False)", r_report.stdout)
            saved = json.loads(out_p.read_text(encoding="utf-8"))
            self.assertEqual(saved["verdict"], "NO-GO")
            self.assertEqual(saved["identity"]["failing_queries"][0]["id"], "case-5")
            self.assertEqual(saved["identity"]["failing_queries"][0]["first_diff_index"], 1)

            r_check = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(fail_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_check.returncode, 1, r_check.stderr)
            self.assertIn("NO-GO:", r_check.stdout)

            # Top-level passed=False with finished_utc must still fail even if all cases say identical=True.
            inconsistent = json.loads(json.dumps(cand_fail_doc))
            inconsistent["cases"][1]["identical"] = True
            inconsistent["cases"][1]["candidate_equal_v9e"] = True
            inconsistent["cases"][1]["candidate"] = dict(ref_doc["cases"][1]["candidate"], decode_seconds=1.4)
            inconsistent_p = tmp / "inconsistent.json"
            inconsistent_p.write_text(json.dumps(inconsistent), encoding="utf-8")
            r_incons = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(inconsistent_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_incons.returncode, 1, r_incons.stderr)
            self.assertIn("NO-GO:", r_incons.stdout)
            self.assertIn("top-level passed=False", r_incons.stdout)

    def test_completed_rc13_bench_failure_row_cli_reports_nogo_and_excludes_unavailable_timings(self) -> None:
        rc13_rows = json.loads((FIXTURES / "rc13_bench.json").read_text(encoding="utf-8"))
        pilot_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))
        # Realistic install_rc13.py bench failure: ok=False, complete=None, null generated_ids/timings, non-null wall_seconds.
        pilot_rows[0] = {
            "query": pilot_rows[0]["query"],
            "ok": False,
            "complete": None,
            "speculate": None,
            "prefix_tokens_reused": None,
            "generated_ids": None,
            "path": None,
            "prefill_seconds": None,
            "decode_seconds": None,
            "elapsed_seconds": None,
            "wall_seconds": 0.05,
            "speculation": None,
        }
        # Partial failure row with available tokens (mismatch at idx 2) and unavailable decode/elapsed.
        pilot_rows[1] = {
            "query": pilot_rows[1]["query"],
            "ok": False,
            "complete": False,
            "speculate": "v9i",
            "prefix_tokens_reused": 32,
            "generated_ids": [151657, 198, 99999],
            "path": None,
            "prefill_seconds": 0.4,
            "decode_seconds": None,
            "elapsed_seconds": None,
            "wall_seconds": 0.42,
            "speculation": None,
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_p = tmp / "rc13.json"
            pilot_p = tmp / "pilot.json"
            out_p = tmp / "out.json"
            rc13_p.write_text(json.dumps(rc13_rows), encoding="utf-8")
            pilot_p.write_text(json.dumps(pilot_rows), encoding="utf-8")

            r_cli = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(pilot_p), "--out", str(out_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_cli.returncode, 1, r_cli.stderr)
            self.assertIn("[FAIL(status)] " + pilot_rows[0]["query"], r_cli.stdout)
            self.assertIn("[DIFF(idx=2)] " + pilot_rows[1]["query"], r_cli.stdout)
            self.assertIn("NO-GO: identity failed (19/21 identical)", r_cli.stdout)

            rep = json.loads(out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep["verdict"], "NO-GO")
            self.assertEqual(rep["overall"]["n"], 21)
            self.assertEqual(rep["overall"]["decode_n"], 19)
            self.assertEqual(rep["overall"]["e2e_n"], 19)
            expected_rc13_dec = sum(r["decode_seconds"] for r in rc13_rows[2:])
            expected_pilot_dec = sum(p["decode_seconds"] for p in pilot_rows[2:])
            expected_rc13_e2e = sum(r["elapsed_seconds"] for r in rc13_rows[2:])
            expected_pilot_e2e = sum(p["elapsed_seconds"] for p in pilot_rows[2:])
            self.assertAlmostEqual(rep["overall"]["rc13_decode_total_s"], expected_rc13_dec)
            self.assertAlmostEqual(rep["overall"]["pilot_decode_total_s"], expected_pilot_dec)
            self.assertAlmostEqual(rep["overall"]["rc13_e2e_total_s"], expected_rc13_e2e)
            self.assertAlmostEqual(rep["overall"]["pilot_e2e_total_s"], expected_pilot_e2e)
            self.assertEqual(rep["identity"]["failing_queries"][0]["first_diff_index"], None)
            self.assertEqual(rep["identity"]["failing_queries"][1]["first_diff_index"], 2)

            # All rows failing with unavailable timings still report NO-GO cleanly.
            all_fail_p = tmp / "all_fail.json"
            all_fail = [
                {
                    "query": r["query"],
                    "ok": False,
                    "complete": None,
                    "generated_ids": None,
                    "prefill_seconds": None,
                    "decode_seconds": None,
                    "elapsed_seconds": None,
                    "wall_seconds": 0.01,
                }
                for r in rc13_rows
            ]
            all_fail_p.write_text(json.dumps(all_fail), encoding="utf-8")
            r_all_fail = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(all_fail_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_all_fail.returncode, 1, r_all_fail.stderr)
            self.assertIn("OVERALL (n=21): decode N/A, e2e N/A", r_all_fail.stdout)
            self.assertIn("NO-GO:", r_all_fail.stdout)

    def test_invalid_qualification_data_rejected_no_false_go(self) -> None:
        rc13_path = FIXTURES / "rc13_bench.json"
        go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))

        def assert_rejected(payload: object, label: str) -> None:
            with tempfile.TemporaryDirectory() as td:
                bad_p = Path(td) / "bad.json"
                bad_p.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(case=label):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([bad_p])
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(rc13_path), "--pilot", str(bad_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertNotIn("GO:", res.stdout)

        # Missing ok / complete on GO fixture row.
        no_ok = json.loads(json.dumps(go_rows))
        del no_ok[0]["ok"]
        assert_rejected(no_ok, "bench_missing_ok")

        no_complete = json.loads(json.dumps(go_rows))
        del no_complete[0]["complete"]
        assert_rejected(no_complete, "bench_missing_complete")

        no_both = json.loads(json.dumps(go_rows))
        del no_both[0]["ok"]
        del no_both[0]["complete"]
        assert_rejected(no_both, "bench_missing_ok_and_complete")

        # Non-boolean ok / complete.
        str_ok = json.loads(json.dumps(go_rows))
        str_ok[0]["ok"] = "true"
        assert_rejected(str_ok, "bench_string_ok")

        null_comp_on_ok = json.loads(json.dumps(go_rows))
        null_comp_on_ok[0]["complete"] = None
        assert_rejected(null_comp_on_ok, "bench_null_complete_when_ok_true")

        # Negative, boolean, or non-finite timings on bench rows.
        neg_dec = json.loads(json.dumps(go_rows))
        neg_dec[0]["decode_seconds"] = -1.0
        assert_rejected(neg_dec, "bench_negative_decode")

        neg_pre = json.loads(json.dumps(go_rows))
        neg_pre[0]["prefill_seconds"] = -0.1
        assert_rejected(neg_pre, "bench_negative_prefill")

        neg_e2e = json.loads(json.dumps(go_rows))
        neg_e2e[0]["elapsed_seconds"] = -1.0
        assert_rejected(neg_e2e, "bench_negative_elapsed")

        bool_dec = json.loads(json.dumps(go_rows))
        bool_dec[0]["decode_seconds"] = True
        assert_rejected(bool_dec, "bench_bool_decode")

        target_dec = f'"decode_seconds": {go_rows[0]["decode_seconds"]}'
        for special in ("NaN", "Infinity", "-Infinity"):
            with tempfile.TemporaryDirectory() as td:
                bad_p = Path(td) / "special.json"
                orig_text = (FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8")
                self.assertIn(target_dec, orig_text)
                raw_text = orig_text.replace(target_dec, f'"decode_seconds": {special}', 1)
                bad_p.write_text(raw_text, encoding="utf-8")
                with self.subTest(case=f"bench_{special}"):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([bad_p])
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(rc13_path), "--pilot", str(bad_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertNotIn("GO:", res.stdout)

        # pilot.json invalid qualification data.
        base_pilot = {
            "passed": True,
            "started_utc": "2026-11-22T00:00:00Z",
            "finished_utc": "2026-11-22T00:01:00Z",
            "cases": [
                {
                    "key": "case-0",
                    "domain": "general",
                    "prefill_seconds": 1.0,
                    "identical": True,
                    "ar": {"tokens": [1, 2], "decode_seconds": 2.0},
                    "candidate": {"tokens": [1, 2], "decode_seconds": 1.0},
                }
            ],
        }
        no_ident = json.loads(json.dumps(base_pilot))
        del no_ident["cases"][0]["identical"]
        assert_rejected(no_ident, "pilot_missing_identical")

        no_cand = json.loads(json.dumps(base_pilot))
        del no_cand["cases"][0]["candidate"]
        assert_rejected(no_cand, "pilot_missing_candidate_no_ar_fallback")

        neg_cand_dec = json.loads(json.dumps(base_pilot))
        neg_cand_dec["cases"][0]["candidate"]["decode_seconds"] = -1.0
        assert_rejected(neg_cand_dec, "pilot_negative_candidate_decode")

        neg_ar_dec = json.loads(json.dumps(base_pilot))
        neg_ar_dec["cases"][0]["ar"]["decode_seconds"] = -0.5
        assert_rejected(neg_ar_dec, "pilot_negative_ar_decode")

        bad_flag = json.loads(json.dumps(base_pilot))
        bad_flag["cases"][0]["candidate_equal_v9e"] = "false"
        assert_rejected(bad_flag, "pilot_nonbool_candidate_equal_v9e")

    def test_no_fabricated_e2e_or_prefill_and_no_mixed_timing_boundaries(self) -> None:
        ref_bench = [
            {
                "query": "q1",
                "ok": True,
                "complete": True,
                "generated_ids": [1, 2],
                "path": "/proc/uptime",
                "prefill_seconds": 1.0,
                "decode_seconds": 1.0,
                "elapsed_seconds": 2.2,
            }
        ]
        ref_raw = {
            "passed": True,
            "started_utc": "2026-11-22T00:00:00Z",
            "finished_utc": "2026-11-22T00:01:00Z",
            "cases": [
                {
                    "key": "q1",
                    "domain": "general",
                    "prefill_seconds": 1.0,
                    "identical": True,
                    "ar": {"tokens": [1, 2], "decode_seconds": 1.0},
                    "candidate": {"tokens": [1, 2], "decode_seconds": 1.0},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ref_bench_p = tmp / "ref_bench.json"
            ref_raw_p = tmp / "ref_raw.json"
            ref_bench_p.write_text(json.dumps(ref_bench), encoding="utf-8")
            ref_raw_p.write_text(json.dumps(ref_raw), encoding="utf-8")

            # (1a) Bench missing elapsed_seconds and wall_seconds (previously fabricated 1.8s -> 1.222x GO).
            bench_no_elapsed = [
                {
                    "query": "q1",
                    "ok": True,
                    "complete": True,
                    "generated_ids": [1, 2],
                    "path": "/proc/uptime",
                    "prefill_seconds": 1.0,
                    "decode_seconds": 0.8,
                }
            ]
            # (1b) Bench missing elapsed_seconds with wall_seconds present.
            bench_wall_only = [dict(bench_no_elapsed[0], wall_seconds=1.9)]
            # (1c) Bench with null elapsed_seconds and wall_seconds present.
            bench_null_elapsed = [dict(bench_no_elapsed[0], elapsed_seconds=None, wall_seconds=1.9)]

            for label, payload in (
                ("bench_no_elapsed", bench_no_elapsed),
                ("bench_wall_only", bench_wall_only),
                ("bench_null_elapsed", bench_null_elapsed),
            ):
                p = tmp / f"{label}.json"
                p.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(case=label):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([p])
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(ref_bench_p), "--pilot", str(p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res.returncode, 0)
                    self.assertNotIn("GO:", res.stdout)

            # Failed bench row with prefill+decode and no elapsed must keep e2e_seconds=None.
            bench_fail_no_elapsed = tmp / "bench_fail_no_elapsed.json"
            bench_fail_no_elapsed.write_text(
                json.dumps([
                    {
                        "query": "q1",
                        "ok": False,
                        "complete": False,
                        "generated_ids": [1, 2],
                        "path": "/proc/uptime",
                        "prefill_seconds": 0.4,
                        "decode_seconds": 0.5,
                        "elapsed_seconds": None,
                        "wall_seconds": 0.95,
                    }
                ]),
                encoding="utf-8",
            )
            fail_recs = analyze_pilot.load_records([bench_fail_no_elapsed])
            self.assertIsNone(fail_recs[0]["e2e_seconds"])

            # (1d) Raw pilot.json case missing prefill_seconds (previously fabricated 0.0s -> 2.500x GO).
            raw_no_prefill = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "q1",
                        "domain": "general",
                        "identical": True,
                        "ar": {"tokens": [1, 2], "decode_seconds": 1.0},
                        "candidate": {"tokens": [1, 2], "decode_seconds": 0.8},
                    }
                ],
            }
            raw_no_prefill_p = tmp / "raw_no_prefill.json"
            raw_no_prefill_p.write_text(json.dumps(raw_no_prefill), encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_pilot.load_records([raw_no_prefill_p])
            res_raw = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(ref_raw_p), "--pilot", str(raw_no_prefill_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_raw.returncode, 0)
            self.assertNotIn("GO:", res_raw.stdout)

            # Failed raw case without prefill_seconds must keep prefill_seconds=None and e2e_seconds=None.
            raw_fail_no_prefill = json.loads(json.dumps(raw_no_prefill))
            raw_fail_no_prefill["passed"] = False
            raw_fail_no_prefill["cases"][0]["identical"] = False
            raw_fail_p = tmp / "raw_fail_no_prefill.json"
            raw_fail_p.write_text(json.dumps(raw_fail_no_prefill), encoding="utf-8")
            raw_fail_recs = analyze_pilot.load_records([raw_fail_p])
            self.assertIsNone(raw_fail_recs[0]["prefill_seconds"])
            self.assertIsNone(raw_fail_recs[0]["e2e_seconds"])

            # (1e) Mixed timing boundaries: bench reference vs raw pilot_cases for same ID must force NO-GO.
            raw_valid = json.loads(json.dumps(raw_no_prefill))
            raw_valid["cases"][0]["prefill_seconds"] = 0.8
            raw_valid_p = tmp / "raw_valid.json"
            raw_valid_p.write_text(json.dumps(raw_valid), encoding="utf-8")
            res_mixed = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(ref_bench_p), "--pilot", str(raw_valid_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_mixed.returncode, 1)
            self.assertIn("NO-GO:", res_mixed.stdout)
            self.assertIn("mixed timing boundaries", res_mixed.stdout)

            # Direct analyze() call with missing E2E on one successful row must force NO-GO.
            r1 = dict(analyze_pilot.load_records([ref_bench_p])[0])
            r2 = dict(r1, id="q2", label="q2")
            p1 = dict(r1, decode_seconds=0.5, e2e_seconds=1.5)
            p2 = dict(r2, decode_seconds=0.5, e2e_seconds=None)
            rep_partial = analyze_pilot.analyze([r1, r2], [p1, p2])
            self.assertEqual(rep_partial["verdict"], "NO-GO")
            self.assertFalse(rep_partial["go"])

    def test_empty_files_rejected_even_alongside_passing_files(self) -> None:
        rc13_p = FIXTURES / "rc13_bench.json"
        pilot_go_p = FIXTURES / "pilot_go_bench.json"

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            empty_failed_pilot = tmp / "empty_failed_pilot.json"
            empty_failed_pilot.write_text(
                json.dumps({
                    "started_utc": "start",
                    "finished_utc": "finish",
                    "passed": False,
                    "cases": [],
                }),
                encoding="utf-8",
            )
            empty_passed_pilot = tmp / "empty_passed_pilot.json"
            empty_passed_pilot.write_text(
                json.dumps({
                    "started_utc": "start",
                    "finished_utc": "finish",
                    "passed": True,
                    "cases": [],
                }),
                encoding="utf-8",
            )
            empty_list = tmp / "empty_list.json"
            empty_list.write_text("[]", encoding="utf-8")

            for empty_p in (empty_failed_pilot, empty_passed_pilot, empty_list):
                with self.subTest(empty_file=empty_p.name):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([pilot_go_p, empty_p])
                    res_pilot = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(pilot_go_p), str(empty_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res_pilot.returncode, 0)
                    self.assertNotIn("GO:", res_pilot.stdout)

                    res_rc13 = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), str(empty_p), "--pilot", str(pilot_go_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(res_rc13.returncode, 0)
                    self.assertNotIn("GO:", res_rc13.stdout)

    def test_prefix_tokens_reused_mismatch_excluded_and_blocks_go(self) -> None:
        def bench_row(
            qid: str,
            *,
            speculate: str = "rc1.3-costaware",
            reused: object = 32,
            include_reused: bool = True,
            dec: float = 1.0,
            e2e: float = 2.0,
        ) -> dict:
            row = {
                "query": qid,
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "generated_ids": [1, 7],
                "path": "/proc/uptime",
                "prefill_seconds": max(0.0, e2e - dec),
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }
            if include_reused:
                row["prefix_tokens_reused"] = reused
            return row

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Exact P1 reproducer: baseline reused=0, dec=1.0, e2e=2.0 vs candidate reused=32, dec=0.9, e2e=0.95.
            base_p = tmp / "base_cold.json"
            cand_p = tmp / "cand_warm.json"
            out_p = tmp / "out_p1.json"
            base_p.write_text(json.dumps([bench_row("q1", speculate="rc1.3-costaware", reused=0, dec=1.0, e2e=2.0)]), encoding="utf-8")
            cand_p.write_text(json.dumps([bench_row("q1", speculate="rc1.4-costaware", reused=32, dec=0.9, e2e=0.95)]), encoding="utf-8")

            r_repro = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base_p), "--pilot", str(cand_p), "--out", str(out_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_repro.returncode, 1, r_repro.stdout + r_repro.stderr)
            self.assertIn("NO-GO:", r_repro.stdout)
            self.assertIn("mismatched measured cache conditions", r_repro.stdout)
            self.assertIn("[CACHE-MISMATCH]", r_repro.stdout)
            self.assertIn("reused=0/32", r_repro.stdout)
            self.assertIn("EXCLUDED (mismatched prefix_tokens_reused): q1 (0 vs 32)", r_repro.stdout)
            self.assertIn("OVERALL (n=1): decode N/A, e2e N/A", r_repro.stdout)

            rep = json.loads(out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep["verdict"], "NO-GO")
            self.assertFalse(rep["go"])
            self.assertEqual(rep["per_query"][0]["rc13_prefix_tokens_reused"], 0)
            self.assertEqual(rep["per_query"][0]["pilot_prefix_tokens_reused"], 32)
            self.assertFalse(rep["per_query"][0]["cache_comparable"])
            self.assertFalse(rep["per_query"][0]["decode_comparable"])
            self.assertFalse(rep["per_query"][0]["e2e_comparable"])
            self.assertIsNone(rep["per_query"][0]["decode_speedup"])
            self.assertIsNone(rep["per_query"][0]["e2e_speedup"])
            self.assertEqual(rep["overall"]["decode_n"], 0)
            self.assertEqual(rep["overall"]["e2e_n"], 0)
            self.assertIsNone(rep["overall"]["decode_speedup"])
            self.assertIsNone(rep["overall"]["e2e_speedup"])
            self.assertEqual(len(rep["cache_condition_mismatches"]), 1)

            # Partial mismatch: q1 matches (32 vs 32), q2 mismatches (0 vs 32) -> q2 excluded from totals/speedup & GO blocked.
            mixed_base = tmp / "mixed_base.json"
            mixed_cand = tmp / "mixed_cand.json"
            mixed_out = tmp / "mixed_out.json"
            mixed_base.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", reused=32, dec=2.0, e2e=3.0),
                    bench_row("q2", speculate="rc1.3-costaware", reused=0, dec=1.0, e2e=2.0),
                ]),
                encoding="utf-8",
            )
            mixed_cand.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", reused=32, dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", reused=32, dec=0.5, e2e=0.8),
                ]),
                encoding="utf-8",
            )
            r_mixed = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(mixed_base), "--pilot", str(mixed_cand), "--out", str(mixed_out), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_mixed.returncode, 1, r_mixed.stdout + r_mixed.stderr)
            mixed_rep = json.loads(mixed_out.read_text(encoding="utf-8"))
            self.assertEqual(mixed_rep["verdict"], "NO-GO")
            self.assertEqual(mixed_rep["overall"]["n"], 2)
            self.assertEqual(mixed_rep["overall"]["decode_n"], 1)
            self.assertEqual(mixed_rep["overall"]["e2e_n"], 1)
            self.assertAlmostEqual(mixed_rep["overall"]["rc13_decode_total_s"], 2.0)
            self.assertAlmostEqual(mixed_rep["overall"]["pilot_decode_total_s"], 1.0)
            self.assertAlmostEqual(mixed_rep["overall"]["rc13_e2e_total_s"], 3.0)
            self.assertAlmostEqual(mixed_rep["overall"]["pilot_e2e_total_s"], 2.0)
            self.assertEqual(mixed_rep["measured_vs_modelled"]["overall"]["measured_n"], 1)
            self.assertEqual([m["id"] for m in mixed_rep["cache_condition_mismatches"]], ["q2"])

            # One-sided missing prefix_tokens_reused on an ok=True row also blocks GO.
            onesided_cand = tmp / "onesided_cand.json"
            onesided_cand.write_text(
                json.dumps([bench_row("q1", speculate="rc1.4-costaware", include_reused=False, dec=0.5, e2e=1.0)]),
                encoding="utf-8",
            )
            r_one = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base_p), "--pilot", str(onesided_cand), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_one.returncode, 1)
            self.assertIn("mismatched measured cache conditions", r_one.stdout)

            # Matching cold-vs-cold (reused=0 vs reused=0) is comparable and allowed to GO.
            cold_cand = tmp / "cold_cand.json"
            cold_cand.write_text(json.dumps([bench_row("q1", speculate="rc1.4-costaware", reused=0, dec=0.8, e2e=1.8)]), encoding="utf-8")
            r_cold_go = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base_p), "--pilot", str(cold_cand), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_cold_go.returncode, 0, r_cold_go.stdout + r_cold_go.stderr)
            self.assertIn("GO:", r_cold_go.stdout)

            # Invalid prefix_tokens_reused values are rejected.
            for bad_reused in (True, 32.0, -1, "32"):
                bad_p = tmp / "bad_reused.json"
                bad_p.write_text(json.dumps([bench_row("q1", reused=bad_reused)]), encoding="utf-8")
                with self.subTest(bad_reused=bad_reused):
                    with self.assertRaises(ValueError):
                        analyze_pilot.load_records([bad_p])

    def test_malformed_token_ids_rejected_across_formats_and_direct_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_bench = tmp / "rc13_bench.json"
            rc13_bench.write_text(
                json.dumps([
                    {
                        "query": "q1",
                        "ok": True,
                        "complete": True,
                        "generated_ids": [1, 7],
                        "prefill_seconds": 0.5,
                        "decode_seconds": 1.0,
                        "elapsed_seconds": 1.5,
                    }
                ]),
                encoding="utf-8",
            )
            rc13_pilot = tmp / "rc13_pilot.json"
            rc13_pilot.write_text(
                json.dumps({
                    "passed": True,
                    "started_utc": "2026-11-22T00:00:00Z",
                    "finished_utc": "2026-11-22T00:01:00Z",
                    "cases": [
                        {
                            "key": "case-0",
                            "domain": "general",
                            "prefill_seconds": 0.5,
                            "identical": True,
                            "ar": {"tokens": [1, 7], "decode_seconds": 1.0},
                            "candidate": {"tokens": [1, 7], "decode_seconds": 1.0},
                        }
                    ],
                }),
                encoding="utf-8",
            )

            malformed_lists: list[tuple[str, object]] = [
                ("bool_and_float_repro", [True, 7.0]),
                ("bool_only", [True, 7]),
                ("float_only", [1, 7.0]),
                ("negative_int", [-1, 7]),
                ("string_token", ["1", 7]),
                ("null_token", [None, 7]),
            ]

            for label, bad_tokens in malformed_lists:
                # Bench generated_ids and tokens fallback (both ok=True and ok=False).
                for key, ok_val, comp_val in (
                    ("generated_ids", True, True),
                    ("tokens", True, True),
                    ("generated_ids", False, False),
                ):
                    cand_bench = tmp / f"bench_{label}_{key}_{ok_val}.json"
                    cand_bench.write_text(
                        json.dumps([
                            {
                                "query": "q1",
                                "ok": ok_val,
                                "complete": comp_val,
                                key: bad_tokens,
                                "prefill_seconds": 0.4,
                                "decode_seconds": 0.5,
                                "elapsed_seconds": 0.9,
                            }
                        ]),
                        encoding="utf-8",
                    )
                    with self.subTest(format="bench", label=label, key=key, ok=ok_val):
                        with self.assertRaises(ValueError):
                            analyze_pilot.load_records([cand_bench])
                        res = subprocess.run(
                            [sys.executable, str(SCRIPT), "--rc13", str(rc13_bench), "--pilot", str(cand_bench), "--check"],
                            capture_output=True,
                            text=True,
                        )
                        self.assertNotEqual(res.returncode, 0)
                        self.assertNotIn("GO:", res.stdout)

                # pilot.json candidate.tokens and raw ar.tokens.
                for target in ("candidate", "ar"):
                    cand_pilot = tmp / f"pilot_{label}_{target}.json"
                    doc = {
                        "passed": True,
                        "started_utc": "2026-11-22T00:00:00Z",
                        "finished_utc": "2026-11-22T00:01:00Z",
                        "cases": [
                            {
                                "key": "case-0",
                                "domain": "general",
                                "prefill_seconds": 0.4,
                                "identical": True,
                                "ar": {"tokens": bad_tokens if target == "ar" else [1, 7], "decode_seconds": 1.0},
                                "candidate": {"tokens": bad_tokens if target == "candidate" else [1, 7], "decode_seconds": 0.5},
                            }
                        ],
                    }
                    cand_pilot.write_text(json.dumps(doc), encoding="utf-8")
                    with self.subTest(format="pilot_json", label=label, target=target):
                        with self.assertRaises(ValueError):
                            analyze_pilot.load_records([cand_pilot])
                        res = subprocess.run(
                            [sys.executable, str(SCRIPT), "--rc13", str(rc13_pilot), "--pilot", str(cand_pilot), "--check"],
                            capture_output=True,
                            text=True,
                        )
                        self.assertNotEqual(res.returncode, 0)
                        self.assertNotIn("GO:", res.stdout)

            # Direct analyze() call with [True, 7.0] tokens or ar_tokens must also fail validation.
            base_rec = analyze_pilot.load_records([rc13_bench])[0]
            bad_tok_rec = dict(base_rec, tokens=[True, 7.0], decode_seconds=0.5, e2e_seconds=1.0)
            with self.assertRaises(ValueError):
                analyze_pilot.analyze([base_rec], [bad_tok_rec])
            bad_ar_rec = dict(base_rec, ar_tokens=[True, 7.0], decode_seconds=0.5, e2e_seconds=1.0)
            with self.assertRaises(ValueError):
                analyze_pilot.analyze([base_rec], [bad_ar_rec])

    def test_both_socket_rows_missing_prefix_tokens_reused_blocks_go_while_raw_pilot_cases_allowed(self) -> None:
        def bench_row(
            qid: str,
            *,
            speculate: str = "rc1.3-costaware",
            reused: object = None,
            include_reused: bool = True,
            dec: float = 1.0,
            e2e: float = 2.0,
        ) -> dict:
            row = {
                "query": qid,
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "generated_ids": [1, 7],
                "path": "/proc/uptime",
                "prefill_seconds": max(0.0, e2e - dec),
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }
            if include_reused:
                row["prefix_tokens_reused"] = reused
            return row

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Exact reviewer reproducer (1): both socket rows have prefix_tokens_reused=null,
            # RC1.3 dec/e2e = 1.0/2.0 s, pilot dec/e2e = 0.9/0.95 s -> must NOT GO.
            rc13_null_p = tmp / "rc13_null.json"
            pilot_null_p = tmp / "pilot_null.json"
            out_null_p = tmp / "out_null.json"
            rc13_null_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.3-costaware", reused=None, dec=1.0, e2e=2.0)]),
                encoding="utf-8",
            )
            pilot_null_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.4-costaware", reused=None, dec=0.9, e2e=0.95)]),
                encoding="utf-8",
            )
            r_null = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_null_p), "--pilot", str(pilot_null_p), "--out", str(out_null_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_null.returncode, 1, r_null.stdout + r_null.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_null.stdout.splitlines()))
            self.assertIn("NO-GO:", r_null.stdout)
            self.assertIn("unmeasured cache conditions", r_null.stdout)
            self.assertIn("[CACHE-UNMEASURED]", r_null.stdout)
            self.assertIn("EXCLUDED (missing prefix_tokens_reused): q1", r_null.stdout)
            self.assertIn("OVERALL (n=1): decode N/A, e2e N/A", r_null.stdout)

            rep_null = json.loads(out_null_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_null["verdict"], "NO-GO")
            self.assertFalse(rep_null["go"])
            self.assertFalse(rep_null["per_query"][0]["cache_comparable"])
            self.assertFalse(rep_null["per_query"][0]["decode_comparable"])
            self.assertFalse(rep_null["per_query"][0]["e2e_comparable"])
            self.assertIsNone(rep_null["per_query"][0]["decode_speedup"])
            self.assertIsNone(rep_null["per_query"][0]["e2e_speedup"])
            self.assertEqual(rep_null["overall"]["decode_n"], 0)
            self.assertEqual(rep_null["overall"]["e2e_n"], 0)
            self.assertIsNone(rep_null["overall"]["decode_speedup"])
            self.assertIsNone(rep_null["overall"]["e2e_speedup"])

            # Omitting prefix_tokens_reused on both socket rows also blocks GO.
            rc13_omit_p = tmp / "rc13_omit.json"
            pilot_omit_p = tmp / "pilot_omit.json"
            rc13_omit_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.3-costaware", include_reused=False, dec=1.0, e2e=2.0)]),
                encoding="utf-8",
            )
            pilot_omit_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.4-costaware", include_reused=False, dec=0.9, e2e=0.95)]),
                encoding="utf-8",
            )
            r_omit = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_omit_p), "--pilot", str(pilot_omit_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_omit.returncode, 1, r_omit.stdout + r_omit.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_omit.stdout.splitlines()))
            self.assertIn("NO-GO:", r_omit.stdout)

            # Partial unmeasured reuse: q1 matches (32 vs 32), q2 has null vs null -> q2 excluded & GO blocked.
            part_rc13_p = tmp / "part_rc13.json"
            part_pilot_p = tmp / "part_pilot.json"
            part_out_p = tmp / "part_out.json"
            part_rc13_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", reused=32, dec=2.0, e2e=3.0),
                    bench_row("q2", speculate="rc1.3-costaware", reused=None, dec=1.0, e2e=2.0),
                ]),
                encoding="utf-8",
            )
            part_pilot_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", reused=32, dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", reused=None, dec=0.9, e2e=0.95),
                ]),
                encoding="utf-8",
            )
            r_part = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(part_rc13_p), "--pilot", str(part_pilot_p), "--out", str(part_out_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_part.returncode, 1, r_part.stdout + r_part.stderr)
            rep_part = json.loads(part_out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_part["verdict"], "NO-GO")
            self.assertEqual(rep_part["overall"]["decode_n"], 1)
            self.assertEqual(rep_part["overall"]["e2e_n"], 1)
            self.assertAlmostEqual(rep_part["overall"]["e2e_speedup"], 1.5)

            # Raw pilot.json cases explicitly run full prefill and remain distinct (reused=None allowed to GO).
            raw_rc13 = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "case-0",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 7], "logit_bits": [11, 12], "kv_sha256": "kv_raw", "decode_seconds": 2.0},
                        "candidate": {"tokens": [1, 7], "logit_bits": [11, 12], "kv_sha256": "kv_raw", "decode_seconds": 1.0},
                    }
                ],
            }
            raw_pilot = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "case-0",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 7], "logit_bits": [11, 12], "kv_sha256": "kv_raw", "decode_seconds": 1.8},
                        "candidate": {"tokens": [1, 7], "logit_bits": [11, 12], "kv_sha256": "kv_raw", "decode_seconds": 0.9},
                    }
                ],
            }
            raw_rc13_p = tmp / "raw_rc13.json"
            raw_pilot_p = tmp / "raw_pilot.json"
            raw_rc13_p.write_text(json.dumps(raw_rc13), encoding="utf-8")
            raw_pilot_p.write_text(json.dumps(raw_pilot), encoding="utf-8")
            r_raw = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(raw_rc13_p), "--pilot", str(raw_pilot_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_raw.returncode, 0, r_raw.stdout + r_raw.stderr)
            self.assertIn("GO:", r_raw.stdout)

    def test_zero_duration_successful_rows_invalidated_and_block_go(self) -> None:
        def bench_row(
            qid: str,
            *,
            speculate: str = "rc1.3-costaware",
            tokens: list[int] | None = None,
            dec: float = 1.0,
            e2e: float = 2.0,
        ) -> dict:
            toks = [1, 7] if tokens is None else tokens
            return {
                "query": qid,
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "prefix_tokens_reused": 32,
                "generated_ids": toks,
                "path": "/proc/uptime",
                "prefill_seconds": max(0.0, e2e - dec),
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Exact reviewer reproducer (2): two queries generating [1, 7] with reuse=32,
            # baseline 1.0/2.0 s twice, pilot 1.0/2.0 s and 0/0 s -> must NOT GO at 2.000x.
            rc13_p = tmp / "rc13.json"
            pilot_zero_p = tmp / "pilot_zero.json"
            out_zero_p = tmp / "out_zero.json"
            rc13_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.3-costaware", dec=1.0, e2e=2.0),
                ]),
                encoding="utf-8",
            )
            pilot_zero_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", dec=0.0, e2e=0.0),
                ]),
                encoding="utf-8",
            )
            r_zero = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(pilot_zero_p), "--out", str(out_zero_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_zero.returncode, 1, r_zero.stdout + r_zero.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_zero.stdout.splitlines()))
            self.assertIn("NO-GO:", r_zero.stdout)
            self.assertIn("invalid non-positive timing", r_zero.stdout)
            self.assertIn("[INVALID-TIMING]", r_zero.stdout)
            self.assertIn("EXCLUDED (non-positive timing): q2", r_zero.stdout)

            rep_zero = json.loads(out_zero_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_zero["verdict"], "NO-GO")
            self.assertFalse(rep_zero["go"])
            self.assertEqual(rep_zero["overall"]["n"], 2)
            self.assertEqual(rep_zero["overall"]["decode_n"], 1)
            self.assertEqual(rep_zero["overall"]["e2e_n"], 1)
            self.assertAlmostEqual(rep_zero["overall"]["decode_speedup"], 1.0)
            self.assertAlmostEqual(rep_zero["overall"]["e2e_speedup"], 1.0)
            self.assertFalse(rep_zero["per_query"][1]["timing_valid"])
            self.assertFalse(rep_zero["per_query"][1]["decode_comparable"])
            self.assertFalse(rep_zero["per_query"][1]["e2e_comparable"])
            self.assertIsNone(rep_zero["per_query"][1]["decode_speedup"])
            self.assertIsNone(rep_zero["per_query"][1]["e2e_speedup"])
            self.assertEqual([x["id"] for x in rep_zero["invalid_timings"]], ["q2"])

            # Even when q1 easily beats thresholds (2.0x), zero-duration q2 still blocks GO.
            pilot_fast_plus_zero_p = tmp / "pilot_fast_plus_zero.json"
            pilot_fast_plus_zero_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", dec=0.5, e2e=1.0),
                    bench_row("q2", speculate="rc1.4-costaware", dec=0.0, e2e=0.0),
                ]),
                encoding="utf-8",
            )
            r_fast_zero = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(pilot_fast_plus_zero_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_fast_zero.returncode, 1, r_fast_zero.stdout + r_fast_zero.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_fast_zero.stdout.splitlines()))
            self.assertIn("NO-GO: invalid non-positive timing", r_fast_zero.stdout)

            # Zero decode on multi-token query even with positive E2E blocks GO.
            pilot_zero_dec_p = tmp / "pilot_zero_dec.json"
            pilot_zero_dec_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", dec=0.5, e2e=1.5),
                    bench_row("q2", speculate="rc1.4-costaware", dec=0.0, e2e=1.0),
                ]),
                encoding="utf-8",
            )
            r_zero_dec = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_p), "--pilot", str(pilot_zero_dec_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_zero_dec.returncode, 1, r_zero_dec.stdout + r_zero_dec.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_zero_dec.stdout.splitlines()))
            self.assertIn("invalid non-positive timing", r_zero_dec.stdout)

            # Zero-duration on baseline row also blocks GO.
            base_zero_p = tmp / "base_zero.json"
            base_zero_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.3-costaware", dec=0.0, e2e=0.0),
                ]),
                encoding="utf-8",
            )
            pilot_valid_p = tmp / "pilot_valid.json"
            pilot_valid_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", dec=1.0, e2e=2.0),
                ]),
                encoding="utf-8",
            )
            r_base_zero = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base_zero_p), "--pilot", str(pilot_valid_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_base_zero.returncode, 1, r_base_zero.stdout + r_base_zero.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_base_zero.stdout.splitlines()))
            self.assertIn("invalid non-positive timing", r_base_zero.stdout)

            # Single-token query requires no decode work: dec=0.0 with positive E2E does not block GO
            # when another query measures >= 1.03x decode speedup, while dec=0.0 is excluded from decode_n.
            rc13_1tok_p = tmp / "rc13_1tok.json"
            pilot_1tok_p = tmp / "pilot_1tok.json"
            out_1tok_p = tmp / "out_1tok.json"
            rc13_1tok_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", tokens=[1, 7], dec=2.0, e2e=3.0),
                    bench_row("q2", speculate="rc1.3-costaware", tokens=[7], dec=0.0, e2e=1.0),
                ]),
                encoding="utf-8",
            )
            pilot_1tok_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", tokens=[1, 7], dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", tokens=[7], dec=0.0, e2e=1.0),
                ]),
                encoding="utf-8",
            )
            r_1tok_ok = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_1tok_p), "--pilot", str(pilot_1tok_p), "--out", str(out_1tok_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_1tok_ok.returncode, 0, r_1tok_ok.stdout + r_1tok_ok.stderr)
            self.assertIn("GO:", r_1tok_ok.stdout)
            rep_1tok = json.loads(out_1tok_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_1tok["overall"]["decode_n"], 1)
            self.assertEqual(rep_1tok["overall"]["e2e_n"], 2)
            self.assertAlmostEqual(rep_1tok["overall"]["decode_speedup"], 2.0)
            self.assertAlmostEqual(rep_1tok["overall"]["e2e_speedup"], 4.0 / 3.0)

            # Single-token query with zero E2E is invalid and blocks GO.
            pilot_1tok_zero_e2e_p = tmp / "pilot_1tok_zero_e2e.json"
            pilot_1tok_zero_e2e_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", tokens=[1, 7], dec=1.0, e2e=2.0),
                    bench_row("q2", speculate="rc1.4-costaware", tokens=[7], dec=0.0, e2e=0.0),
                ]),
                encoding="utf-8",
            )
            r_1tok_bad = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_1tok_p), "--pilot", str(pilot_1tok_zero_e2e_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_1tok_bad.returncode, 1, r_1tok_bad.stdout + r_1tok_bad.stderr)
            self.assertIn("invalid non-positive timing", r_1tok_bad.stdout)

            # Raw pilot.json zero-duration row also blocked on CLI.
            raw_ref = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "c1",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 7], "logit_bits": [21, 22], "kv_sha256": "kv1", "decode_seconds": 1.0},
                        "candidate": {"tokens": [1, 7], "logit_bits": [21, 22], "kv_sha256": "kv1", "decode_seconds": 1.0},
                    },
                    {
                        "key": "c2",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 7], "logit_bits": [23, 24], "kv_sha256": "kv2", "decode_seconds": 1.0},
                        "candidate": {"tokens": [1, 7], "logit_bits": [23, 24], "kv_sha256": "kv2", "decode_seconds": 1.0},
                    },
                ],
            }
            raw_zero = json.loads(json.dumps(raw_ref))
            raw_zero["cases"][1]["prefill_seconds"] = 0.0
            raw_zero["cases"][1]["candidate"]["decode_seconds"] = 0.0
            raw_ref_p = tmp / "raw_ref.json"
            raw_zero_p = tmp / "raw_zero.json"
            raw_ref_p.write_text(json.dumps(raw_ref), encoding="utf-8")
            raw_zero_p.write_text(json.dumps(raw_zero), encoding="utf-8")
            r_raw_zero = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(raw_ref_p), "--pilot", str(raw_zero_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_raw_zero.returncode, 1, r_raw_zero.stdout + r_raw_zero.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_raw_zero.stdout.splitlines()))
            self.assertIn("invalid non-positive timing", r_raw_zero.stdout)

    def test_inconsistent_socket_timings_excluded_and_block_go(self) -> None:
        def bench_row(
            qid: str,
            *,
            speculate: str = "rc1.3-costaware",
            prefill: float | None = 0.5,
            dec: float = 1.0,
            e2e: float = 1.6,
            wall: float | None = 1.65,
        ) -> dict:
            row: dict[str, object] = {
                "query": qid,
                "ok": True,
                "complete": True,
                "speculate": speculate,
                "prefix_tokens_reused": 32,
                "generated_ids": [1, 7],
                "path": "/proc/uptime",
                "decode_seconds": dec,
                "elapsed_seconds": e2e,
            }
            if prefill is not None:
                row["prefill_seconds"] = prefill
            if wall is not None:
                row["wall_seconds"] = wall
            return row

        pilot_go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Exact reviewer reproducer: checked-in rc13_bench.json and pilot_go_bench.json with all
            # pilot elapsed_seconds=0.01 and wall_seconds=0.02 (leaving tokens, cache, stage timings untouched).
            tampered_pilot = json.loads(json.dumps(pilot_go_rows))
            for row in tampered_pilot:
                row["elapsed_seconds"] = 0.01
                row["wall_seconds"] = 0.02
            tampered_p = tmp / "pilot_tampered_elapsed.json"
            tampered_out_p = tmp / "tampered_out.json"
            tampered_p.write_text(json.dumps(tampered_pilot), encoding="utf-8")

            r_repro = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(FIXTURES / "rc13_bench.json"),
                    "--pilot",
                    str(tampered_p),
                    "--out",
                    str(tampered_out_p),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_repro.returncode, 1, r_repro.stdout + r_repro.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_repro.stdout.splitlines()))
            self.assertIn("NO-GO: inconsistent socket timing on 21/21", r_repro.stdout)
            self.assertIn("[INVALID-TIMING]", r_repro.stdout)
            self.assertIn("EXCLUDED (inconsistent socket timing):", r_repro.stdout)
            self.assertIn("OVERALL (n=21): decode N/A, e2e N/A", r_repro.stdout)

            rep_repro = json.loads(tampered_out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_repro["verdict"], "NO-GO")
            self.assertFalse(rep_repro["go"])
            self.assertEqual(rep_repro["overall"]["n"], 21)
            self.assertEqual(rep_repro["overall"]["decode_n"], 0)
            self.assertEqual(rep_repro["overall"]["e2e_n"], 0)
            self.assertIsNone(rep_repro["overall"]["decode_speedup"])
            self.assertIsNone(rep_repro["overall"]["e2e_speedup"])
            self.assertEqual(len(rep_repro["invalid_timings"]), 21)
            self.assertFalse(rep_repro["per_query"][0]["timing_valid"])
            self.assertFalse(rep_repro["per_query"][0]["decode_comparable"])
            self.assertFalse(rep_repro["per_query"][0]["e2e_comparable"])

            # Partial invalidation: q1 valid (2.0x), q2 has elapsed < prefill+decode -> q2 excluded & NO-GO.
            base2_p = tmp / "base2.json"
            base2_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", prefill=1.0, dec=2.0, e2e=3.2, wall=3.25),
                    bench_row("q2", speculate="rc1.3-costaware", prefill=1.0, dec=2.0, e2e=3.2, wall=3.25),
                ]),
                encoding="utf-8",
            )
            part_stage_p = tmp / "part_stage.json"
            part_stage_out = tmp / "part_stage_out.json"
            part_stage_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                    bench_row("q2", speculate="rc1.4-costaware", prefill=0.6, dec=0.8, e2e=1.2, wall=1.25),
                ]),
                encoding="utf-8",
            )
            r_part = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base2_p), "--pilot", str(part_stage_p), "--out", str(part_stage_out), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_part.returncode, 1, r_part.stdout + r_part.stderr)
            self.assertIn("NO-GO: inconsistent socket timing on 1/2", r_part.stdout)
            rep_part = json.loads(part_stage_out.read_text(encoding="utf-8"))
            self.assertEqual(rep_part["verdict"], "NO-GO")
            self.assertEqual(rep_part["overall"]["n"], 2)
            self.assertEqual(rep_part["overall"]["decode_n"], 1)
            self.assertEqual(rep_part["overall"]["e2e_n"], 1)
            self.assertAlmostEqual(rep_part["overall"]["rc13_decode_total_s"], 2.0)
            self.assertAlmostEqual(rep_part["overall"]["pilot_decode_total_s"], 1.0)
            self.assertAlmostEqual(rep_part["overall"]["rc13_e2e_total_s"], 3.2)
            self.assertAlmostEqual(rep_part["overall"]["pilot_e2e_total_s"], 1.6)
            self.assertEqual([x["id"] for x in rep_part["invalid_timings"]], ["q2"])

            # wall_seconds < elapsed_seconds (even when elapsed >= prefill+decode) excluded & forces NO-GO.
            part_wall_p = tmp / "part_wall.json"
            part_wall_out = tmp / "part_wall_out.json"
            part_wall_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                    bench_row("q2", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.50),
                ]),
                encoding="utf-8",
            )
            r_wall = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base2_p), "--pilot", str(part_wall_p), "--out", str(part_wall_out), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_wall.returncode, 1, r_wall.stdout + r_wall.stderr)
            self.assertIn("NO-GO: inconsistent socket timing on 1/2", r_wall.stdout)
            rep_wall = json.loads(part_wall_out.read_text(encoding="utf-8"))
            self.assertEqual(rep_wall["overall"]["decode_n"], 1)
            self.assertEqual(rep_wall["overall"]["e2e_n"], 1)
            self.assertEqual([x["id"] for x in rep_wall["invalid_timings"]], ["q2"])

            # Omitted prefill_seconds still enforces elapsed >= decode.
            no_pre_p = tmp / "no_pre.json"
            no_pre_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                    bench_row("q2", speculate="rc1.4-costaware", prefill=None, dec=1.0, e2e=0.9, wall=1.0),
                ]),
                encoding="utf-8",
            )
            r_nopre = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(base2_p), "--pilot", str(no_pre_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_nopre.returncode, 1, r_nopre.stdout + r_nopre.stderr)
            self.assertIn("inconsistent socket timing on 1/2", r_nopre.stdout)

            # Inconsistent baseline (rc13) row also excluded & forces NO-GO.
            bad_base_wall_p = tmp / "bad_base_wall.json"
            bad_base_wall_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.3-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                    bench_row("q2", speculate="rc1.3-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.50),
                ]),
                encoding="utf-8",
            )
            valid_p = tmp / "valid.json"
            valid_p.write_text(
                json.dumps([
                    bench_row("q1", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                    bench_row("q2", speculate="rc1.4-costaware", prefill=0.5, dec=1.0, e2e=1.6, wall=1.65),
                ]),
                encoding="utf-8",
            )
            r_bad_base = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(bad_base_wall_p), "--pilot", str(valid_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_bad_base.returncode, 1, r_bad_base.stdout + r_bad_base.stderr)
            self.assertIn("inconsistent socket timing on 1/2", r_bad_base.stdout)

            # Binary float rounding (0.1 + 0.2 = 0.30000000000000004 > 0.3) and omitted wall_seconds pass cleanly.
            tol_rc13_p = tmp / "tol_rc13.json"
            tol_pilot_p = tmp / "tol_pilot.json"
            tol_rc13_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.3-costaware", prefill=0.2, dec=0.4, e2e=0.6, wall=None)]),
                encoding="utf-8",
            )
            tol_pilot_p.write_text(
                json.dumps([bench_row("q1", speculate="rc1.4-costaware", prefill=0.1, dec=0.2, e2e=0.3, wall=None)]),
                encoding="utf-8",
            )
            r_tol = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(tol_rc13_p), "--pilot", str(tol_pilot_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_tol.returncode, 0, r_tol.stdout + r_tol.stderr)
            self.assertIn("GO:", r_tol.stdout)

    def test_raw_arm_completeness_and_ar_logit_kv_regressions(self) -> None:
        cases = []
        for idx in range(0, 180, 5):
            toks = [100 + idx, 200 + idx, 300 + idx]
            bits = [0x3F800000 + idx, 0x40000000 + idx, 0x40400000 + idx]
            kv = f"{idx:064x}"
            cases.append({
                "key": f"case-{idx}",
                "index": idx,
                "domain": "tool" if idx < 60 else "general",
                "prefill_seconds": 1.0 + 0.01 * idx,
                "identical": True,
                "ar_equal_v9e": True,
                "candidate_equal_v9e": True,
                "ar": {
                    "tokens": list(toks),
                    "logit_bits": list(bits),
                    "kv_sha256": kv,
                    "decode_seconds": 2.5 + 0.01 * idx,
                },
                "candidate": {
                    "tokens": list(toks),
                    "logit_bits": list(bits),
                    "kv_sha256": kv,
                    "decode_seconds": 2.0 + 0.01 * idx,
                },
            })
        ref_doc = {
            "passed": True,
            "started_utc": "2026-11-22T00:00:00Z",
            "finished_utc": "2026-11-22T00:10:00Z",
            "cases": cases,
        }
        pilot_go_doc = json.loads(json.dumps(ref_doc))
        for c in pilot_go_doc["cases"]:
            c["prefill_seconds"] *= 0.8
            c["candidate"]["decode_seconds"] *= 0.8

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ref_p = tmp / "v9h_ref_36.json"
            go_p = tmp / "pilot_go_36.json"
            out_go_p = tmp / "out_go.json"
            ref_p.write_text(json.dumps(ref_doc), encoding="utf-8")
            go_p.write_text(json.dumps(pilot_go_doc), encoding="utf-8")

            r_go = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(ref_p), "--pilot", str(go_p), "--out", str(out_go_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_go.returncode, 0, r_go.stdout + r_go.stderr)
            self.assertIn("GO: 36/36 identical; decode speedup 1.250x", r_go.stdout)
            self.assertIn("e2e speedup 1.250x", r_go.stdout)

            mutations: list[tuple[str, object, str]] = [
                ("flip_ar_logit_bit0", lambda d: d["cases"][0]["ar"]["logit_bits"].__setitem__(0, d["cases"][0]["ar"]["logit_bits"][0] ^ 1), "ar_logit_identical"),
                ("remove_ar_tokens", lambda d: d["cases"][0]["ar"].pop("tokens"), "ar_tokens_identical"),
                ("remove_candidate_kv_sha256", lambda d: d["cases"][0]["candidate"].pop("kv_sha256"), "cand_kv_identical"),
                ("remove_ar_kv_sha256", lambda d: d["cases"][0]["ar"].pop("kv_sha256"), "ar_kv_identical"),
                ("remove_ar_logit_bits", lambda d: d["cases"][0]["ar"].pop("logit_bits"), "ar_logit_identical"),
                ("remove_candidate_logit_bits", lambda d: d["cases"][0]["candidate"].pop("logit_bits"), "cand_logit_identical"),
                ("remove_ar_arm", lambda d: d["cases"][0].pop("ar"), "ar_tokens_identical"),
                ("flip_candidate_logit_bit0", lambda d: d["cases"][0]["candidate"]["logit_bits"].__setitem__(0, d["cases"][0]["candidate"]["logit_bits"][0] ^ 1), "cand_logit_identical"),
                ("change_ar_token0", lambda d: d["cases"][0]["ar"]["tokens"].__setitem__(0, 99999), "ar_tokens_identical"),
                ("truncate_ar_logit_bits", lambda d: d["cases"][0]["ar"]["logit_bits"].pop(), "ar_logit_identical"),
                ("empty_candidate_kv_sha256", lambda d: d["cases"][0]["candidate"].__setitem__("kv_sha256", "  "), "cand_kv_identical"),
            ]

            for label, mutate, fail_flag in mutations:
                mut_doc = json.loads(json.dumps(pilot_go_doc))
                mutate(mut_doc)
                mut_p = tmp / f"{label}.json"
                mut_out_p = tmp / f"{label}_out.json"
                mut_p.write_text(json.dumps(mut_doc), encoding="utf-8")
                with self.subTest(case=label):
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(ref_p), "--pilot", str(mut_p), "--out", str(mut_out_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertFalse(any(line.startswith("GO:") for line in res.stdout.splitlines()))
                    self.assertIn("NO-GO: identity failed (35/36 identical)", res.stdout)
                    rep = json.loads(mut_out_p.read_text(encoding="utf-8"))
                    self.assertEqual(rep["verdict"], "NO-GO")
                    self.assertFalse(rep["go"])
                    self.assertEqual(rep["identity"]["identical_queries"], 35)
                    self.assertEqual(len(rep["identity"]["failing_queries"]), 1)
                    fq = rep["identity"]["failing_queries"][0]
                    self.assertEqual(fq["id"], "case-0")
                    self.assertFalse(fq[fail_flag])

            # Malformed logit_bits and non-string kv_sha256 are rejected at load time.
            bad_bits_doc = json.loads(json.dumps(pilot_go_doc))
            bad_bits_doc["cases"][0]["ar"]["logit_bits"] = [True, 1.5, 3]
            bad_bits_p = tmp / "bad_bits.json"
            bad_bits_p.write_text(json.dumps(bad_bits_doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_pilot.load_records([bad_bits_p])

            bad_kv_doc = json.loads(json.dumps(pilot_go_doc))
            bad_kv_doc["cases"][0]["candidate"]["kv_sha256"] = 12345
            bad_kv_p = tmp / "bad_kv.json"
            bad_kv_p.write_text(json.dumps(bad_kv_doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_pilot.load_records([bad_kv_p])

    def test_archived_wrapper_arm_selection_and_57_case_self_compare(self) -> None:
        rc13_rows = json.loads((FIXTURES / "rc13_bench.json").read_text(encoding="utf-8"))
        pilot_go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))
        raw_cases = []
        for idx in range(0, 180, 5):
            toks = [10 + idx, 20 + idx]
            bits = [1000 + idx, 2000 + idx]
            kv = f"{idx:064x}"
            raw_cases.append({
                "key": f"case-{idx}",
                "index": idx,
                "domain": "general",
                "prefill_seconds": 1.0,
                "identical": True,
                "ar": {"tokens": list(toks), "logit_bits": list(bits), "kv_sha256": kv, "decode_seconds": 2.0},
                "candidate": {"tokens": list(toks), "logit_bits": list(bits), "kv_sha256": kv, "decode_seconds": 1.5},
            })
        raw_ref = {
            "passed": True,
            "started_utc": "2026-11-22T00:00:00Z",
            "finished_utc": "2026-11-22T00:05:00Z",
            "cases": raw_cases,
        }
        template_cache_wrapper = {
            "note": "archived bench-template-cache shape",
            "before": rc13_rows,
            "shared": rc13_rows,
            "reset": rc13_rows,
        }
        compare_wrapper = {
            "rc11": rc13_rows,
            "rc12": rc13_rows,
            "rc13": rc13_rows,
        }
        pilot_wrapper = {
            "v9i": pilot_go_rows,
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            tc_p = tmp / "bench-template-cache.json"
            cmp_p = tmp / "bench-compare.json"
            pilot_wrap_p = tmp / "bench-pilot-wrapper.json"
            raw_p = tmp / "v9h_ref_36.json"
            go_bench_p = tmp / "pilot_go.json"
            tc_p.write_text(json.dumps(template_cache_wrapper), encoding="utf-8")
            cmp_p.write_text(json.dumps(compare_wrapper), encoding="utf-8")
            pilot_wrap_p.write_text(json.dumps(pilot_wrapper), encoding="utf-8")
            raw_p.write_text(json.dumps(raw_ref), encoding="utf-8")
            go_bench_p.write_text(json.dumps(pilot_go_rows), encoding="utf-8")

            # Without explicit arm, wrapper files fail with an actionable error listing available arms.
            with self.assertRaises(ValueError) as ctx_tc:
                analyze_pilot.load_records([tc_p])
            self.assertIn("shared", str(ctx_tc.exception))

            with self.assertRaises(ValueError) as ctx_cmp:
                analyze_pilot.load_records([cmp_p])
            self.assertIn("rc13", str(ctx_cmp.exception))

            r_no_arm = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(tc_p), "--pilot", str(go_bench_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r_no_arm.returncode, 0)
            self.assertIn("shared", r_no_arm.stderr)

            # Wrong arm name is rejected cleanly.
            with self.assertRaises(ValueError):
                analyze_pilot.load_records([cmp_p], arm="shared")

            # Explicit --rc13-arm rc13 works with pilot bench.
            r_cmp = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(cmp_p), "--rc13-arm", "rc13", "--pilot", str(go_bench_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_cmp.returncode, 0, r_cmp.stdout + r_cmp.stderr)
            self.assertIn("GO: 21/21 identical", r_cmp.stdout)

            # Self-comparing RC1.3 as pilot is blocked because pilot socket rows carry rc1.3-costaware instead of rc1.4-costaware.
            r_self_nogo = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(tc_p),
                    str(raw_p),
                    "--rc13-arm",
                    "shared",
                    "--pilot",
                    str(tc_p),
                    str(raw_p),
                    "--pilot-arm",
                    "shared",
                    "--min-decode-speedup",
                    "1.0",
                    "--min-e2e-speedup",
                    "1.0",
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_self_nogo.returncode, 1, r_self_nogo.stdout + r_self_nogo.stderr)
            self.assertIn("NO-GO:", r_self_nogo.stdout)
            self.assertIn("unexpected socket speculate mode", r_self_nogo.stdout)

            # Explicit --rc13-arm shared + --pilot-arm v9i + 36-case raw pilot.json -> 57/57 GO (raw cases unaffected).
            r_57 = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(tc_p),
                    str(raw_p),
                    "--rc13-arm",
                    "shared",
                    "--pilot",
                    str(pilot_wrap_p),
                    str(raw_p),
                    "--pilot-arm",
                    "v9i",
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_57.returncode, 0, r_57.stdout + r_57.stderr)
            self.assertIn("GO: 57/57 identical", r_57.stdout)

    def test_socket_speculate_label_validated_per_side_and_raw_unaffected(self) -> None:
        rc13_rows = json.loads((FIXTURES / "rc13_bench.json").read_text(encoding="utf-8"))
        pilot_go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))
        rc13_fixture_p = FIXTURES / "rc13_bench.json"

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            # Exact reviewer reproducer: bundled rc13_bench.json vs pilot_go_bench.json
            # with only pilot row 0 `speculate` edited from "rc1.4-costaware" to False.
            bad_pilot_rows = json.loads(json.dumps(pilot_go_rows))
            bad_pilot_rows[0]["speculate"] = False
            bad_pilot_p = tmp / "pilot_row0_speculate_false.json"
            bad_out_p = tmp / "pilot_row0_speculate_false_out.json"
            bad_pilot_p.write_text(json.dumps(bad_pilot_rows), encoding="utf-8")

            r_repro = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(rc13_fixture_p),
                    "--pilot",
                    str(bad_pilot_p),
                    "--out",
                    str(bad_out_p),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_repro.returncode, 1, r_repro.stdout + r_repro.stderr)
            self.assertFalse(any(line.startswith("GO:") for line in r_repro.stdout.splitlines()))
            self.assertIn("NO-GO:", r_repro.stdout)
            self.assertIn("[SPECULATE-MISMATCH]", r_repro.stdout)
            self.assertIn("EXCLUDED (unexpected speculate mode): Read /proc/sys/kernel/random/boot_id", r_repro.stdout)
            self.assertIn("unexpected socket speculate mode on 1/21 matched queries: Read /proc/sys/kernel/random/boot_id", r_repro.stdout)

            rep = json.loads(bad_out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep["verdict"], "NO-GO")
            self.assertFalse(rep["go"])
            self.assertFalse(rep["identity"]["passed"])
            self.assertEqual(rep["identity"]["identical_queries"], 20)
            self.assertEqual(len(rep["identity"]["failing_queries"]), 1)
            self.assertEqual(rep["identity"]["failing_queries"][0]["id"], "Read /proc/sys/kernel/random/boot_id")
            self.assertFalse(rep["identity"]["failing_queries"][0]["speculate_ok"])
            self.assertEqual(rep["identity"]["failing_queries"][0]["pilot_speculate"], False)
            self.assertFalse(rep["per_query"][0]["status_ok"])
            self.assertFalse(rep["per_query"][0]["speculate_ok"])
            self.assertFalse(rep["per_query"][0]["decode_comparable"])
            self.assertFalse(rep["per_query"][0]["e2e_comparable"])
            self.assertIsNone(rep["per_query"][0]["decode_speedup"])
            self.assertIsNone(rep["per_query"][0]["e2e_speedup"])
            self.assertEqual(rep["overall"]["n"], 21)
            self.assertEqual(rep["overall"]["decode_n"], 20)
            self.assertEqual(rep["overall"]["e2e_n"], 20)
            self.assertEqual(len(rep["speculate_mismatches"]), 1)
            self.assertEqual(rep["speculate_mismatches"][0]["id"], "Read /proc/sys/kernel/random/boot_id")
            self.assertEqual(rep["speculate_mismatches"][0]["rc13_speculate"], "rc1.3-costaware")
            self.assertEqual(rep["speculate_mismatches"][0]["pilot_speculate"], False)

            # Other invalid pilot speculate values (omitted, None, wrong-side label, adaptive, True) also fail --check.
            for label, mutator in (
                ("pilot_none", lambda r: r[0].__setitem__("speculate", None)),
                ("pilot_omitted", lambda r: r[0].pop("speculate", None)),
                ("pilot_wrong_side_rc13", lambda r: r[0].__setitem__("speculate", "rc1.3-costaware")),
                ("pilot_adaptive", lambda r: r[0].__setitem__("speculate", "adaptive")),
                ("pilot_bool_true", lambda r: r[0].__setitem__("speculate", True)),
            ):
                mut_rows = json.loads(json.dumps(pilot_go_rows))
                mutator(mut_rows)
                mut_p = tmp / f"{label}.json"
                mut_p.write_text(json.dumps(mut_rows), encoding="utf-8")
                with self.subTest(case=label):
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(rc13_fixture_p), "--pilot", str(mut_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertFalse(any(line.startswith("GO:") for line in res.stdout.splitlines()))
                    self.assertIn("unexpected socket speculate mode", res.stdout)

            # Invalid RC1.3 baseline speculate values (false, wrong-side rc1.4-costaware, None) also fail --check.
            pilot_fixture_p = FIXTURES / "pilot_go_bench.json"
            for label, val in (
                ("rc13_false", False),
                ("rc13_wrong_side_rc14", "rc1.4-costaware"),
                ("rc13_none", None),
            ):
                mut_rc13 = json.loads(json.dumps(rc13_rows))
                mut_rc13[2]["speculate"] = val
                mut_rc13_p = tmp / f"{label}.json"
                mut_rc13_p.write_text(json.dumps(mut_rc13), encoding="utf-8")
                with self.subTest(case=label):
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), "--rc13", str(mut_rc13_p), "--pilot", str(pilot_fixture_p), "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertFalse(any(line.startswith("GO:") for line in res.stdout.splitlines()))
                    self.assertIn("Read /proc/version", res.stdout)
                    self.assertIn("unexpected socket speculate mode", res.stdout)

            # All 21 pilot rows invalid -> decode_n=0, e2e_n=0, OVERALL N/A, NO-GO without spurious speedup unavailable.
            all_bad = json.loads(json.dumps(pilot_go_rows))
            for r in all_bad:
                r["speculate"] = False
            all_bad_p = tmp / "all_bad_speculate.json"
            all_bad_out_p = tmp / "all_bad_speculate_out.json"
            all_bad_p.write_text(json.dumps(all_bad), encoding="utf-8")
            r_all_bad = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_fixture_p), "--pilot", str(all_bad_p), "--out", str(all_bad_out_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_all_bad.returncode, 1, r_all_bad.stdout + r_all_bad.stderr)
            self.assertIn("OVERALL (n=21): decode N/A, e2e N/A", r_all_bad.stdout)
            self.assertNotIn("speedup unavailable", r_all_bad.stdout)
            rep_all_bad = json.loads(all_bad_out_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_all_bad["overall"]["decode_n"], 0)
            self.assertEqual(rep_all_bad["overall"]["e2e_n"], 0)
            self.assertEqual(len(rep_all_bad["speculate_mismatches"]), 21)

            # BENCH-JSON stdout format enforces the same socket speculate check.
            bench_log_p = tmp / "pilot_bad.stdout"
            bench_log_p.write_text("header\nBENCH-JSON " + json.dumps(bad_pilot_rows) + "\n", encoding="utf-8")
            r_log = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(rc13_fixture_p), "--pilot", str(bench_log_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_log.returncode, 1, r_log.stdout + r_log.stderr)
            self.assertIn("unexpected socket speculate mode", r_log.stdout)

            # Raw pilot.json cases have no speculate field and remain completely unaffected (still GO).
            raw_rc13 = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "case-0",
                        "domain": "general",
                        "prefill_seconds": 1.0,
                        "identical": True,
                        "ar": {"tokens": [1, 2], "logit_bits": [10, 20], "kv_sha256": "kv0", "decode_seconds": 2.0},
                        "candidate": {"tokens": [1, 2], "logit_bits": [10, 20], "kv_sha256": "kv0", "decode_seconds": 1.5},
                    }
                ],
            }
            raw_pilot = {
                "passed": True,
                "started_utc": "2026-11-22T00:00:00Z",
                "finished_utc": "2026-11-22T00:01:00Z",
                "cases": [
                    {
                        "key": "case-0",
                        "domain": "general",
                        "prefill_seconds": 0.9,
                        "identical": True,
                        "ar": {"tokens": [1, 2], "logit_bits": [10, 20], "kv_sha256": "kv0", "decode_seconds": 1.9},
                        "candidate": {"tokens": [1, 2], "logit_bits": [10, 20], "kv_sha256": "kv0", "decode_seconds": 1.1},
                    }
                ],
            }
            raw_rc13_p = tmp / "raw_rc13.json"
            raw_pilot_p = tmp / "raw_pilot.json"
            raw_rc13_p.write_text(json.dumps(raw_rc13), encoding="utf-8")
            raw_pilot_p.write_text(json.dumps(raw_pilot), encoding="utf-8")
            r_raw = subprocess.run(
                [sys.executable, str(SCRIPT), "--rc13", str(raw_rc13_p), "--pilot", str(raw_pilot_p), "--check"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_raw.returncode, 0, r_raw.stdout + r_raw.stderr)
            self.assertIn("GO: 1/1 identical", r_raw.stdout)

    def test_pre_template_cache_rc13_cold_provenance_and_explicit_cold_baseline(self) -> None:
        rc13_rows = json.loads((FIXTURES / "rc13_bench.json").read_text(encoding="utf-8"))
        pilot_go_rows = json.loads((FIXTURES / "pilot_go_bench.json").read_text(encoding="utf-8"))

        # Exact reviewer reproducer: pre-template-cache 0cc305b install_rc13.py omitted
        # prefix_tokens_reused while setting reset_cache=True on every request.
        legacy_rc13_rows = json.loads(json.dumps(rc13_rows))
        for row in legacy_rc13_rows:
            row.pop("prefix_tokens_reused", None)

        cold_pilot_rows = json.loads(json.dumps(pilot_go_rows))
        for row in cold_pilot_rows:
            row["prefix_tokens_reused"] = 0

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            legacy_wrap_p = tmp / "bench-compare.json"
            legacy_list_p = tmp / "rc13-compare.json"
            legacy_log_p = tmp / "rc13-compare.stdout"
            cold_pilot_p = tmp / "pilot_cold.json"
            cached_pilot_p = FIXTURES / "pilot_go_bench.json"
            out_go_p = tmp / "out_cold_go.json"

            legacy_wrap_p.write_text(json.dumps({"rc13": legacy_rc13_rows}), encoding="utf-8")
            legacy_list_p.write_text(json.dumps(legacy_rc13_rows), encoding="utf-8")
            legacy_log_p.write_text("header\nBENCH-JSON " + json.dumps(legacy_rc13_rows) + "\n", encoding="utf-8")
            cold_pilot_p.write_text(json.dumps(cold_pilot_rows), encoding="utf-8")

            # 1. Documented --rc13-arm rc13 against cold pilot (prefix_tokens_reused=0) -> GO 21/21.
            r_arm_go = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(legacy_wrap_p),
                    "--rc13-arm",
                    "rc13",
                    "--pilot",
                    str(cold_pilot_p),
                    "--out",
                    str(out_go_p),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_arm_go.returncode, 0, r_arm_go.stdout + r_arm_go.stderr)
            self.assertIn("GO: 21/21 identical; decode speedup 1.310x", r_arm_go.stdout)
            self.assertIn("e2e speedup 1.122x", r_arm_go.stdout)
            rep_arm_go = json.loads(out_go_p.read_text(encoding="utf-8"))
            self.assertEqual(rep_arm_go["verdict"], "GO")
            self.assertTrue(all(q["rc13_prefix_tokens_reused"] == 0 for q in rep_arm_go["per_query"]))
            self.assertTrue(all(q["pilot_prefix_tokens_reused"] == 0 for q in rep_arm_go["per_query"]))
            self.assertEqual(rep_arm_go["cache_condition_mismatches"], [])

            # 2. Legacy cold rc13 arm vs template-cached pilot (32) -> NO-GO (0 vs 32 mismatch).
            r_arm_vs_cached = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(legacy_wrap_p),
                    "--rc13-arm",
                    "rc13",
                    "--pilot",
                    str(cached_pilot_p),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_arm_vs_cached.returncode, 1, r_arm_vs_cached.stdout + r_arm_vs_cached.stderr)
            self.assertIn("mismatched measured cache conditions", r_arm_vs_cached.stdout)
            self.assertIn("21/21 matched queries", r_arm_vs_cached.stdout)

            # 3. Standalone extracted array without --rc13-cold-baseline stays gated (NO-GO).
            r_list_no_flag = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(legacy_list_p),
                    "--pilot",
                    str(cold_pilot_p),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_list_no_flag.returncode, 1, r_list_no_flag.stdout + r_list_no_flag.stderr)
            self.assertIn("NO-GO:", r_list_no_flag.stdout)
            self.assertIn("mismatched measured cache conditions", r_list_no_flag.stdout)

            # 4. Standalone extracted array and BENCH-JSON log with --rc13-cold-baseline -> GO 21/21.
            for label, src_p in (("extracted_list", legacy_list_p), ("bench_json_log", legacy_log_p)):
                with self.subTest(source=label):
                    r_cold_flag = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--rc13",
                            str(src_p),
                            "--rc13-cold-baseline",
                            "--pilot",
                            str(cold_pilot_p),
                            "--check",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(r_cold_flag.returncode, 0, r_cold_flag.stdout + r_cold_flag.stderr)
                    self.assertIn("GO: 21/21 identical; decode speedup 1.310x", r_cold_flag.stdout)
                    self.assertIn("e2e speedup 1.122x", r_cold_flag.stdout)

            # 5. Explicit null, partial omission, non-rc13 arm, and pilot omissions remain gated (NO-GO).
            null_rc13_rows = json.loads(json.dumps(legacy_rc13_rows))
            for row in null_rc13_rows:
                row["prefix_tokens_reused"] = None
            null_wrap_p = tmp / "null_wrap.json"
            null_list_p = tmp / "null_list.json"
            null_wrap_p.write_text(json.dumps({"rc13": null_rc13_rows}), encoding="utf-8")
            null_list_p.write_text(json.dumps(null_rc13_rows), encoding="utf-8")

            mixed_rc13_rows = json.loads(json.dumps(legacy_rc13_rows))
            mixed_rc13_rows[1]["prefix_tokens_reused"] = 0
            mixed_wrap_p = tmp / "mixed_wrap.json"
            mixed_wrap_p.write_text(json.dumps({"rc13": mixed_rc13_rows}), encoding="utf-8")

            shared_omitted_wrap_p = tmp / "shared_omitted_wrap.json"
            shared_omitted_wrap_p.write_text(json.dumps({"shared": legacy_rc13_rows}), encoding="utf-8")

            omit_pilot_rows = json.loads(json.dumps(cold_pilot_rows))
            for row in omit_pilot_rows:
                row.pop("prefix_tokens_reused", None)
            omit_pilot_p = tmp / "omit_pilot.json"
            omit_pilot_wrap_p = tmp / "omit_pilot_wrap.json"
            omit_pilot_p.write_text(json.dumps(omit_pilot_rows), encoding="utf-8")
            omit_pilot_wrap_p.write_text(json.dumps({"rc13": omit_pilot_rows}), encoding="utf-8")

            gated_cases = [
                ("explicit_null_under_rc13_arm", ["--rc13", str(null_wrap_p), "--rc13-arm", "rc13", "--pilot", str(cold_pilot_p)]),
                ("explicit_null_under_cold_flag", ["--rc13", str(null_list_p), "--rc13-cold-baseline", "--pilot", str(cold_pilot_p)]),
                ("mixed_omission_under_rc13_arm", ["--rc13", str(mixed_wrap_p), "--rc13-arm", "rc13", "--pilot", str(cold_pilot_p)]),
                ("non_rc13_shared_arm_omitted", ["--rc13", str(shared_omitted_wrap_p), "--rc13-arm", "shared", "--pilot", str(cold_pilot_p)]),
                ("pilot_omitted_with_cold_flag", ["--rc13", str(legacy_list_p), "--rc13-cold-baseline", "--pilot", str(omit_pilot_p)]),
                ("pilot_omitted_under_pilot_arm_rc13", ["--rc13", str(legacy_wrap_p), "--rc13-arm", "rc13", "--pilot", str(omit_pilot_wrap_p), "--pilot-arm", "rc13"]),
            ]
            for label, cli_args in gated_cases:
                with self.subTest(case=label):
                    res = subprocess.run(
                        [sys.executable, str(SCRIPT), *cli_args, "--check"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertFalse(any(line.startswith("GO:") for line in res.stdout.splitlines()))
                    self.assertIn("NO-GO:", res.stdout)

    def test_rc14_pilot_md_combined_21_plus_36_schemas_and_source_format_split(self) -> None:
        paths = ["/proc/sys/kernel/random/boot_id", "/proc/uptime", "/proc/version"]
        domains = ["general", "maintenance", "long", "tool"]
        rc13_rows = []
        v9i_rows = []
        for i in range(21):
            p = paths[i % 3]
            q = f"Read {p} #{i}"
            rc13_rows.append({
                "query": q,
                "ok": True,
                "complete": True,
                "speculate": "rc1.3-costaware",
                "prefix_tokens_reused": 32,
                "generated_ids": [100, 200, i + 1],
                "path": p,
                "prefill_seconds": 0.55,
                "decode_seconds": 0.50,
                "elapsed_seconds": 1.07,
                "wall_seconds": 1.09,
                "speculation": {"passes": 3, "ar_steps": 0, "drafted": 6, "accepted": 4},
            })
            v9i_rows.append({
                "query": q,
                "ok": True,
                "complete": True,
                "speculate": "rc1.4-costaware",
                "prefix_tokens_reused": 32,
                "generated_ids": [100, 200, i + 1],
                "path": p,
                "prefill_seconds": 0.54,
                "decode_seconds": 0.38,
                "elapsed_seconds": 0.94,
                "wall_seconds": 0.96,
                "speculation": {"passes": 2, "ar_steps": 0, "drafted": 6, "accepted": 4},
            })

        ref_cases = []
        pilot_cases = []
        for k, idx in enumerate(range(0, 180, 5)):
            dom = domains[idx % 4]
            key = f"tool:Read {paths[k % 3]} #{idx}" if dom == "tool" else f"case-{idx}"
            toks = [10, 20, 30 + k]
            bits = [1001, 1002, 1003 + k]
            kv = f"sha256-{idx}"
            ref_cases.append({
                "key": key,
                "index": idx,
                "domain": dom,
                "prompt_tokens": 50 + k,
                "max_new": 64,
                "reference": "v9e-ref.json",
                "prefill_seconds": 1.2,
                "ar": {"passes": 3, "ar_steps": 3, "drafted": 0, "accepted": 0, "decode_seconds": 2.0, "kv_sha256": kv, "tokens": toks, "logit_bits": bits},
                "candidate": {"passes": 2, "ar_steps": 0, "drafted": 4, "accepted": 2, "decode_seconds": 1.5, "kv_sha256": kv, "tokens": toks, "logit_bits": bits},
                "ar_equal_v9e": True,
                "candidate_equal_v9e": True,
                "generated": len(toks),
                "identical": True,
            })
            pilot_cases.append({
                "key": key,
                "index": idx,
                "domain": dom,
                "prompt_tokens": 50 + k,
                "max_new": 64,
                "reference": "reference-pilot.json",
                "prefill_seconds": 1.15,
                "ar": {"passes": 3, "ar_steps": 3, "drafted": 0, "accepted": 0, "decode_seconds": 1.9, "kv_sha256": kv, "tokens": toks, "logit_bits": bits},
                "candidate": {"passes": 2, "ar_steps": 0, "drafted": 4, "accepted": 2, "decode_seconds": 1.35, "kv_sha256": kv, "tokens": toks, "logit_bits": bits},
                "ar_equal_v9e": True,
                "candidate_equal_v9e": True,
                "generated": len(toks),
                "identical": True,
            })

        ref_doc = {"passed": True, "started_utc": "2026-11-20T00:00:00Z", "finished_utc": "2026-11-20T00:10:00Z", "cases": ref_cases}
        pilot_doc = {"passed": True, "started_utc": "2026-11-22T00:00:00Z", "finished_utc": "2026-11-22T00:10:00Z", "cases": pilot_cases}

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc13_shared = tmp / "bench-rc13-shared.json"
            ref_pilot = tmp / "reference-pilot.json"
            bench_v9i = tmp / "bench-v9i.json"
            bench_log = tmp / "bench-v9i.log"
            raw_pilot = tmp / "pilot.json"
            out_json = tmp / "pilot-analysis.json"

            rc13_shared.write_text(json.dumps(rc13_rows), encoding="utf-8")
            ref_pilot.write_text(json.dumps(ref_doc), encoding="utf-8")
            bench_v9i.write_text(json.dumps(v9i_rows), encoding="utf-8")
            bench_log.write_text("info\nBENCH-JSON " + json.dumps(v9i_rows) + "\n", encoding="utf-8")
            raw_pilot.write_text(json.dumps(pilot_doc), encoding="utf-8")

            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(rc13_shared),
                    str(ref_pilot),
                    "--pilot",
                    str(bench_v9i),
                    str(raw_pilot),
                    "--out",
                    str(out_json),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertIn("GO: 57/57 identical", res.stdout)
            self.assertIn("SOURCE[bench] (n=21, id=21/21):", res.stdout)
            self.assertIn("SOURCE[pilot_cases] (n=36, id=36/36):", res.stdout)
            self.assertIn("Socket Tool E2E:", res.stdout)

            saved = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(saved["identity"]["total_queries"], 57)
            self.assertEqual(set(saved["by_source_format"].keys()), {"bench", "pilot_cases"})
            self.assertEqual(saved["by_source_format"]["bench"]["n"], 21)
            self.assertEqual(saved["by_source_format"]["pilot_cases"]["n"], 36)
            self.assertAlmostEqual(saved["by_source_format"]["bench"]["e2e_speedup"], 1.07 / 0.94, places=6)
            self.assertAlmostEqual(saved["measured_vs_modelled"]["socket_tool"]["measured_e2e_speedup"], 1.07 / 0.94, places=6)
            self.assertEqual(saved["measured_vs_modelled"]["scope"]["measured_socket_tool_cases"], 21)
            self.assertEqual(saved["measured_vs_modelled"]["scope"]["measured_raw_tool_cases"], 9)

            res_log = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--rc13",
                    str(rc13_shared),
                    "--pilot",
                    str(bench_log),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_log.returncode, 0, res_log.stdout + res_log.stderr)
            self.assertIn("GO: 21/21 identical", res_log.stdout)


if __name__ == "__main__":
    unittest.main()
