"""Assemble the offline RC1.4 (v9i) board-pilot archive."""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = "sysone-qwen-decoder-v9i"
OLD_APP = "sysone-qwen-decoder-v9h"
FEATURES = ["steps", "step_pos", "passes_small", "passes_large",
            "pass_tokens", "pass_pos", "pass_pos_groups"]
CASE_INDICES = list(range(0, 180, 5))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return text.replace(old, new)


def model(fit):
    coef = list(fit["coef_v9h"])
    if fit["fit"]["features"] != FEATURES or len(coef) != 7 or not all(map(math.isfinite, coef)):
        raise ValueError("Expected a finite 7-coefficient v9h fit in fit_v9h.py order")
    # model_p2.py dual+p2: every supported pass uses both ports, with ceil(k / 2)
    # attention groups. Equal pass constants decouple CostAwareDrafter's split from P.
    coef[3] = coef[2]
    return coef


def make_app(stage, impl, v9h, bootgen):
    project = impl / "vivado"
    bit = impl / "system_wrapper.bit"
    xsa = impl / "qwen_decoder.xsa"
    if not bit.exists():
        bit = project / "qwen_decoder_kr260.runs/impl_1/system_wrapper.bit"
    if not xsa.exists():
        xsa = project / "qwen_decoder.xsa"
    with zipfile.ZipFile(xsa) as archive:
        bits = [name for name in archive.namelist() if name.endswith(".bit")]
        if len(bits) != 1 or archive.read(bits[0]) != bit.read_bytes():
            raise ValueError("v9i XSA does not contain the selected bitstream")

    regs = v9h / "registers-v9h.json"
    header = impl / "hls/solution/impl/ip/drivers/qwen_decoder_v1_0/src/xqwen_decoder_hw.h"
    addr = dict(re.findall(r"#define XQWEN_DECODER_CONTROL_ADDR_(\w+)_DATA\s+0x([\da-fA-F]+)",
                           header.read_text(encoding="utf-8")))
    register_map = load(regs)
    if (int(addr["MODEL_B"], 16) != 0x70 or register_map.get("scratch") != 0x7c
            or any(int(addr.get(k.upper(), "-1"), 16) != v for k, v in register_map.items())):
        raise ValueError("v9i HLS CSR offsets differ from the v9h register map")
    shutil.copyfile(regs, stage / regs.name)

    artifacts = stage / "artifacts"
    artifacts.mkdir()
    shutil.copyfile(bit, artifacts / "system_wrapper.bit")
    shutil.copyfile(xsa, artifacts / "qwen_decoder.xsa")
    app = stage / APP
    app.mkdir()
    bif = artifacts / "bitstream.bif"
    bif.write_text("all:\n{\n system_wrapper.bit\n}\n", encoding="ascii")
    subprocess.run([str(bootgen), "-arch", "zynqmp", "-image", bif.name,
                    "-w", "-process_bitstream", "bin"], cwd=artifacts, check=True)
    (artifacts / "system_wrapper.bit.bin").rename(app / f"{APP}.bit.bin")
    bif.unlink()

    template = v9h / OLD_APP
    dts = (template / f"{OLD_APP}.dts").read_text(encoding="utf-8")
    dts = replace_once(dts, f"{OLD_APP}.bit.bin", f"{APP}.bit.bin")
    dts = replace_once(dts, "xlnx,qwen-decoder-v9h-1.0", "xlnx,qwen-decoder-v9i-1.0")
    (app / f"{APP}.dts").write_text(dts, encoding="ascii")
    shutil.copyfile(template / "shell.json", app / "shell.json")
    build = load(template / "build.json")
    build.update(app_name=APP, candidate="v9i", baseline="v9h", bitstream_sha256=sha(bit),
                 xsa_sha256=sha(xsa), changes_vs_v9h=["full dual weight port", "P=2 attention"])
    build.pop("changes_vs_v9g", None)
    build.pop("routed_timing_sha256", None)
    write(app / "build.json", build)
    return {name: sha(app / name) for name in (f"{APP}.bit.bin", f"{APP}.dts", "shell.json")}


def stage_inputs(stage, source):
    build = source / "build/v2"
    fit_path = build / "rc1-3/fit.json"
    fit = load(fit_path)
    work = load(build / "spec-qual/workload.json")
    queries = [case["query"] for case in work["cases"] if "query" in case]
    if len(queries) != 21 or len(set(queries)) != 21:
        raise ValueError("Expected the 21 distinct RC1.3 tool queries")
    write(stage / "queries.json", queries)

    check = stage / "check"
    check.mkdir()
    cases = [case for case in work["cases"] if case["index"] in CASE_INDICES]
    reference = load(build / "v9h-board/pilot.json")
    ref_cases = [case for case in reference["cases"] if case["index"] in CASE_INDICES]
    if (not reference["passed"] or [c["index"] for c in cases] != CASE_INDICES
            or [c["key"] for c in cases] != [c["key"] for c in ref_cases]
            or not all(case["identical"] for case in ref_cases)):
        raise ValueError("Expected 36 matching, passing v9h reference cases")
    write(check / "workload.json", dict(work, cases=cases))
    write(check / "reference-pilot.json", dict(reference, cases=ref_cases))
    shutil.copyfile(build / "draft-board/expected.json", check / "expected.json")
    checker = (ROOT / "experiments/dual_port/v9h_pilot.py").read_text(encoding="utf-8")
    checker = '"""Run the two-arm v9i raw check against the RC1.3 hardware reference."""\n' + checker.split('"""', 2)[2]
    checker = checker.replace("v9h", "v9i").replace("--v9e", "--reference").replace("a.v9e", "a.reference")
    checker = replace_once(checker, "cases = [c for c in work['cases'] if c['index'] % 5 == 0]",
                           "cases = work['cases']")
    checker = replace_once(checker, "        if any('query' in c for c in cases):",
                           "        if len(cases) != 36 or len(ref) != 36:\n"
                           "            raise RuntimeError('Expected exactly 36 cases and reference rows')\n"
                           "        if any('query' in c for c in cases):")
    checker = replace_once(checker, "            rec['identical'] = rec['ar_equal_v9e'] and rec['candidate_equal_v9e']",
                          "            rec['identical'] = (rec['ar_equal_v9e'] and rec['candidate_equal_v9e']\n"
                          "                                and all(s[k] == o['candidate'][k]\n"
                          "                                        for k in ('tokens', 'logit_bits', 'kv_sha256')))")
    checker = replace_once(checker, "if __name__ == '__main__':", "    if not res['passed']:\n        raise SystemExit(1)\n\n\nif __name__ == '__main__':")
    (stage / "check_v9i.py").write_text(checker, encoding="utf-8")
    return dict(coef_v9i=model(fit), cost_features=FEATURES, cost_model="modelled from v9h board fit",
                cost_model_source="experiments/attn_reclaim/model_p2.py dual+p2",
                v9h_fit_sha256=sha(fit_path), attention_lanes=2, split_all_passes=True,
                rc1_package_manifest_sha256=sha(
                    build / "hardware-consolidated-rc1/deployment-r2/package-sha256.json"))


def package(source, output, bootgen):
    with tempfile.TemporaryDirectory(prefix="rc14-", dir=output.parent) as tmp:
        stage = Path(tmp) / "rc14"
        stage.mkdir()
        for name in ("rc14_image.py", "spec_service_rc14.py", "install_rc14.py", "30-rc14-pilot.conf", "README.md"):
            shutil.copyfile(ROOT / "firmware/rc1_4" / name, stage / name)
        for name, path in (("spec_decode.py", "experiments/spec_service/spec_decode.py"),
                           ("drafters.py", "experiments/draft_research/drafters.py")):
            shutil.copyfile(ROOT / path, stage / name)
        config = stage_inputs(stage, source)
        config["v9i_firmware_sha256"] = make_app(
            stage, source / "build/v2/v9i/impl",
            source / "build/v2/qwen-fpga-decoder-v9h/pilot", bootgen)
        write(stage / "config.json", config)
        manifest = {p.relative_to(stage).as_posix(): sha(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        write(stage / "bundle-sha256.json", manifest)
        archive = Path(tmp) / "rc14.tar"
        with tarfile.open(archive, "w") as tar:
            for key in sorted((*manifest, "bundle-sha256.json")):
                path = stage / key
                entry = tar.gettarinfo(path, arcname=f"rc14/{key}")
                entry.mtime = entry.uid = entry.gid = 0
                entry.uname = entry.gname = ""
                entry.mode = 0o644
                with path.open("rb") as stream:
                    tar.addfile(entry, stream)
        archive.replace(output)
    return dict(tar=str(output), sha256=sha(output), files=len(manifest), queries=21, check_cases=36)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT, help="Checkout containing routed build and RC1.3 data")
    parser.add_argument("--out", type=Path, default=ROOT / "build/v2/rc1-4/rc14.tar")
    parser.add_argument("--bootgen", type=Path, default=Path("C:/AMDDesignTools/2025.2/Vivado/bin/bootgen.bat"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(package(args.source.resolve(), args.out.resolve(), args.bootgen.resolve())))


if __name__ == "__main__":
    main()
