"""Exercise real RC1.4 packaging and staging in a temporary directory, offline."""
import argparse
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    with tempfile.TemporaryDirectory(prefix="rc14-dry-run-") as tmp:
        root = Path(tmp)
        archive = root / "rc14.tar"
        subprocess.run([sys.executable, str(ROOT / "scripts/v2/package_rc14.py"),
                        "--source", str(source), "--out", str(archive)], check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter="data")
        staged = root / "rc14"
        spec = importlib.util.spec_from_file_location("install_rc14", staged / "install_rc14.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        installer.RC1 = source / "build/v2/hardware-consolidated-rc1/deployment-r2"
        installer.BUNDLE = root / "var/rc1-4-pilot"
        installer.FIRMWARE = root / "firmware"
        installer.RC13 = root / "etc/20-rc13.conf"
        installer.RC13.parent.mkdir()
        shutil.copyfile(ROOT / "firmware/rc1_3/20-rc13.conf", installer.RC13)
        rc13_digest = installer.sha(installer.RC13)
        installer.DROPIN = root / "run/30-rc14-pilot.conf"
        installer.OUT = root / "results"
        commands = []
        failed_mode = None

        def run(command):
            if command[0] == "cp":
                shutil.copytree(command[2], command[3], symlinks=True)
            elif command[0] == "dtc":
                subprocess.run(command, check=True)
            elif command[0] == "systemctl":
                commands.append((command[1], installer.DROPIN.exists()))
            elif command[0] == "/usr/bin/python3":
                assert command[1:] == [installer.BUNDLE / "rc14_image.py", "down"]
                commands.append(("image-down", installer.DROPIN.exists()))
            else:
                raise AssertionError(command)

        def probe(mode):
            commands.append((mode, installer.DROPIN.exists()))
            if mode == failed_mode:
                raise RuntimeError("simulated READY probe failure")

        installer.run = run
        installer.probe = probe
        expected = [("rc1.3-costaware", False), ("stop", False), ("daemon-reload", True),
                    ("start", True), ("rc1.4-costaware", True), ("stop", True),
                    ("image-down", True), ("daemon-reload", False), ("start", False),
                    ("rc1.3-costaware", False)]

        tampered = staged / "queries.json"
        query_bytes = tampered.read_bytes()
        tampered.write_bytes(query_bytes + b" ")
        try:
            installer.stage(staged)
        except RuntimeError as exc:
            assert "Bundle file differs" in str(exc)
        else:
            raise AssertionError("Tampered staging was accepted")
        assert not installer.BUNDLE.exists() and not installer.FIRMWARE.exists()
        tampered.write_bytes(query_bytes)

        installer.stage(staged)
        assert not commands and not installer.DROPIN.exists()
        bundle, app = installer.BUNDLE, installer.APP
        assert (bundle / "package/registers.json").read_bytes() == (staged / "registers-v9h.json").read_bytes()
        overlay = installer.FIRMWARE / app / f"{app}.dtbo"
        assert overlay.read_bytes().startswith(bytes.fromhex("d00dfeed"))
        assert len(installer.load(bundle / "queries.json")) == 21
        ref = installer.load(bundle / "check/reference-pilot.json")
        assert [row["index"] for row in ref["cases"]] == list(range(0, 180, 5))
        assert ref["passed"]
        for path in staged.glob("*.py"):
            compile(path.read_bytes(), str(path), "exec")

        cfg = installer.load(bundle / "config.json")
        sys.path.insert(0, str(bundle))
        from drafters import CostAwareDrafter
        c = cfg["coef_v9i"]
        draft = CostAwareDrafter(None, c, P=cfg["attention_lanes"])
        assert c[2] == c[3] and cfg["split_all_passes"] and cfg["cost_model"].startswith("modelled")
        for k in range(1, 9):
            expected_cost = c[0] + c[1] * 600 if k == 1 else c[2] + c[4]*k + c[5]*600 + c[6]*600*math.ceil(k/2)
            assert math.isclose(draft.cost(k, 600), expected_cost)

        installer.enable()
        installer.rollback()
        assert commands == expected
        commands.clear()
        failed_mode = "rc1.4-costaware"
        try:
            installer.enable()
        except RuntimeError as exc:
            assert str(exc) == "simulated READY probe failure"
        else:
            raise AssertionError("Failed probe did not abort")
        assert commands == expected
        assert installer.sha(installer.RC13) == rc13_digest

        reference_tool = source / "build/v2/rc1-3/board/bench-template-cache.json"
        reference_rows = installer.load(reference_tool)["shared"]
        by_query = {row["query"]: row for row in reference_rows}

        def exchange(req):
            assert req["reset_cache"] is False
            row = by_query[req["query"]]
            return dict(ok=True, result=dict(row, speculate="rc1.4-costaware",
                                             tool_result=dict(path=row["path"])))

        installer.exchange = exchange
        installer.bench("local", keep_cache=True)
        rows = installer.load(installer.OUT / "bench-local.json")
        assert [row["query"] for row in rows] == [row["query"] for row in reference_rows]
        assert all(row.keys() == ref_row.keys() and row["generated_ids"] == ref_row["generated_ids"]
                   for row, ref_row in zip(rows, reference_rows))
    print(json.dumps(dict(result="PASS", packaged_queries=21, check_cases=36, dtc="real",
                          transitions="mocked", failed_probe_rollback="PASS", tamper_rejection="PASS")))


if __name__ == "__main__":
    main()
