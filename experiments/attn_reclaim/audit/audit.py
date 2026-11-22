"""C-sim exactness audit harness for Qwen3-0.6B HLS decoder variants.

Runs Vitis HLS C-sim (csim_design) on a baseline source directory and a
variant source directory using a shared testbench (experiments/attn_reclaim/audit/testbench.cpp),
caches baseline dumps by source+testbench hash, compares dumps word-for-word
(hidden state, K/V cache, norm, tokens, logit bits), and prints a JSON verdict
with differing word counts per field and the first mismatch location.

Usage:
  python audit.py --baseline SRC_DIR --variant SRC_DIR [--mode decode|prefill]
  python audit.py --self-test
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTBENCH_PATH = HERE / "testbench.cpp"
DEFAULT_SOURCE_CHECKOUT = Path(
    "C:/Users/user/OneDrive - Texas Tech University/Desktop/Code/FPGA Project/system-one-fpga/system-one-fpga"
)
VITIS_RUN = Path("C:/AMDDesignTools/2025.2/Vitis/bin/vitis-run.bat")

NL = 28
NK = 8
H = 1024
KV_WORDS_PER_ROW = 64
FIELDS = ("hidden", "kv", "norm", "token", "logit")
VITIS_PROCESS_NAMES = {
    "vitis_hls.exe",
    "vivado_hls.exe",
    "vitis-run.exe",
    "apcc.exe",
    "clang++.exe",
}


def log(msg: str) -> None:
    print(f"[audit] {msg}", file=sys.stderr, flush=True)


def resolve_src_dir(arg: str, source_checkout: Path) -> Path:
    p = Path(arg)
    if p.exists():
        return p.resolve()
    rel = source_checkout / arg
    if rel.exists():
        return rel.resolve()
    raise FileNotFoundError(f"Source directory not found: {arg}")


def collect_source_files(src_dir: Path) -> list[Path]:
    exts = {".cpp", ".cc", ".c", ".hpp", ".hh", ".h"}
    files = [
        p
        for p in sorted(src_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in exts
    ]
    if not (src_dir / "qwen_decoder.cpp").is_file():
        raise FileNotFoundError(f"Missing qwen_decoder.cpp in {src_dir}")
    return files


def compute_source_hash(src_dir: Path) -> str:
    h = hashlib.sha256()
    for p in collect_source_files(src_dir):
        rel = p.relative_to(src_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def is_single_port(src_dir: Path) -> bool:
    txt = (src_dir / "qwen_decoder.cpp").read_text(errors="replace")
    return re.search(r"weight_word\s*\*\s*model_b\b", txt) is None


def compute_tb_hash(
    testbench_bytes: bytes, mode: str, tile_cross: bool, single_port: bool
) -> str:
    h = hashlib.sha256()
    h.update(testbench_bytes)
    h.update(f"\0{mode}\0{int(tile_cross)}\0{int(single_port)}".encode("utf-8"))
    return h.hexdigest()


def parse_subst_output(stdout: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in stdout.splitlines():
        m = re.match(r"^([A-Za-z]):\\:?\s*=>\s*(.+)$", line.strip())
        if m:
            mapping[m.group(1).upper()] = m.group(2).strip()
    return mapping


def normalize_drive(drive: str) -> str:
    d = drive.strip().rstrip(":\\/").upper()
    if len(d) != 1 or not ("A" <= d <= "Z"):
        raise ValueError(f"Invalid Windows drive letter: {drive!r}")
    return d


def ensure_subst(source_checkout: Path, drive: str = "S") -> str:
    """Ensure subst drive (default S:) maps to source_checkout (no spaces for Vitis make)."""
    d = normalize_drive(drive)
    expected = os.path.normcase(os.path.normpath(str(source_checkout)))
    res = subprocess.run(["subst"], capture_output=True, text=True, check=True)
    mapping = parse_subst_output(res.stdout)
    if d in mapping:
        actual = os.path.normcase(os.path.normpath(mapping[d]))
        if actual == expected:
            return d
        raise RuntimeError(
            f"Drive {d}: is already mapped to {mapping[d]}, expected {source_checkout}"
        )
    log(f"Mapping {d}: -> {source_checkout}")
    subprocess.run(["subst", f"{d}:", str(source_checkout)], check=True)
    return d


def active_vitis_processes() -> list[str]:
    res = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False
    )
    running = []
    for line in res.stdout.splitlines():
        parts = [c.strip().strip('"') for c in line.split(",")]
        if parts and parts[0].lower() in VITIS_PROCESS_NAMES:
            running.append(f"{parts[0]}(pid={parts[1]})" if len(parts) > 1 else parts[0])
    return running


class VitisLock:
    """Serialize Vitis HLS runs on this 14 GB machine via lockfile + process check."""

    def __init__(self, lock_path: Path, poll_seconds: float = 5.0):
        self.lock_path = lock_path
        self.poll_seconds = poll_seconds
        self.fh = None

    def __enter__(self):
        import msvcrt

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.lock_path, "a+")
        while True:
            try:
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                log("Waiting for existing audit Vitis lock...")
                time.sleep(self.poll_seconds)

        while True:
            procs = active_vitis_processes()
            if not procs:
                break
            log(f"Waiting for active Vitis/HLS process(es): {', '.join(procs)}")
            time.sleep(self.poll_seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import msvcrt

        if self.fh is not None:
            try:
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self.fh.close()
                self.fh = None


def render_tcl(
    run_rel_drive: str,
    mode: str,
    tile_cross: bool,
    single_port: bool,
    drive: str = "S",
) -> str:
    d = normalize_drive(drive)
    tb_cflags = "-std=c++14 -DSINGLE_PORT" if single_port else "-std=c++14"
    argv = (
        f"{d}:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf "
        f"{d}:/build/v2/schedule-invariance-audit/meta.bin "
        f"{d}:/build/v2/qwen-fpga-decoder-v9e/rope.bin "
        f"{run_rel_drive}/results.json "
        f"{run_rel_drive}/dump.bin "
        f"{mode} {1 if tile_cross else 0}"
    )
    return "\n".join(
        [
            f"open_project {run_rel_drive}/csim",
            "set_top qwen_decoder",
            f'add_files {run_rel_drive}/src/qwen_decoder.cpp -cflags "-std=c++14"',
            "open_solution solution -flow_target vivado",
            "set_part {xck26-sfvc784-2LV-c}",
            "create_clock -period 8 -name default",
            "config_compile -pipeline_loops 0",
            f'add_files -tb {run_rel_drive}/tb/testbench.cpp -cflags "{tb_cflags}"',
            f'csim_design -clean -O -argv "{argv}"',
            "exit",
            "",
        ]
    )


def run_csim(
    src_dir: Path,
    run_dir: Path,
    source_checkout: Path,
    mode: str,
    tile_cross: bool,
    drive: str = "S",
) -> tuple[Path, Path]:
    if not VITIS_RUN.is_file():
        raise FileNotFoundError(f"Vitis launcher not found: {VITIS_RUN}")
    d = ensure_subst(source_checkout, drive)

    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "src").mkdir(parents=True)
    (run_dir / "tb").mkdir(parents=True)

    for p in collect_source_files(src_dir):
        dst = run_dir / "src" / p.relative_to(src_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    shutil.copyfile(TESTBENCH_PATH, run_dir / "tb" / "testbench.cpp")

    rel_from_root = run_dir.resolve().relative_to(source_checkout.resolve()).as_posix()
    run_rel_drive = f"{d}:/{rel_from_root}"
    single_port = is_single_port(src_dir)
    tcl_path = run_dir / "run_csim.tcl"
    tcl_path.write_text(
        render_tcl(run_rel_drive, mode, tile_cross, single_port, drive=d),
        encoding="utf-8",
    )

    lock_path = source_checkout / "build/v2/attn-reclaim/gemini/.vitis.lock"
    log_path = run_dir / "csim-console.log"
    with VitisLock(lock_path):
        log(f"Running csim_design ({mode}, single_port={single_port}, drive={d}:) for {src_dir}")
        with open(log_path, "w", encoding="utf-8") as lf:
            rc = subprocess.run(
                [
                    str(VITIS_RUN),
                    "--mode",
                    "hls",
                    "--tcl",
                    f"{run_rel_drive}/run_csim.tcl",
                ],
                cwd=run_rel_drive,
                stdout=lf,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode

    dump_path = run_dir / "dump.bin"
    results_path = run_dir / "results.json"
    if rc != 0 or not dump_path.is_file() or not results_path.is_file():
        tail = ""
        if log_path.is_file():
            lines = log_path.read_text(errors="replace").splitlines()[-40:]
            tail = "\n" + "\n".join(lines)
        raise RuntimeError(
            f"Vitis C-sim failed (rc={rc}) for {src_dir}; log={log_path}{tail}"
        )
    return dump_path, results_path


def load_dump(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    out: dict[str, bytes] = {}
    at = 0
    for name in FIELDS:
        if at + 8 > len(data):
            raise ValueError(f"Truncated dump header for {name} in {path}")
        (n,) = struct.unpack_from("<Q", data, at)
        at += 8
        end = at + 4 * n
        if end > len(data):
            raise ValueError(f"Truncated dump payload for {name} in {path}")
        out[name] = data[at:end]
        at = end
    if at != len(data):
        raise ValueError(f"Trailing bytes in dump {path}: {len(data) - at}")
    return out


def format_word_hex(word: int) -> str:
    return f"0x{word:08x}"


def format_f32(word: int) -> float | str:
    val = struct.unpack("<f", struct.pack("<I", word))[0]
    if val != val:
        return "NaN"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return val


def decode_mismatch_location(
    field: str, idx: int, w_base: int, w_var: int, positions: list[int]
) -> dict:
    m = len(positions)
    loc: dict = {
        "field": field,
        "word_index": idx,
        "baseline_word": format_word_hex(w_base),
        "variant_word": format_word_hex(w_var),
    }
    if field in ("hidden", "norm", "logit"):
        loc["baseline_f32"] = format_f32(w_base)
        loc["variant_f32"] = format_f32(w_var)

    if field == "hidden":
        layer = idx // (m * H)
        pos_idx = (idx // H) % m
        elem = idx % H
        loc.update(
            layer=layer,
            position_index=pos_idx,
            position=positions[pos_idx],
            element=elem,
        )
    elif field == "kv":
        word_in_row = idx % KV_WORDS_PER_ROW
        pos_idx = (idx // KV_WORDS_PER_ROW) % m
        head = (idx // (KV_WORDS_PER_ROW * m)) % NK
        kv_kind = "K" if ((idx // (KV_WORDS_PER_ROW * m * NK)) % 2 == 0) else "V"
        layer = idx // (KV_WORDS_PER_ROW * m * NK * 2)
        loc.update(
            layer=layer,
            kv=kv_kind,
            head=head,
            position_index=pos_idx,
            position=positions[pos_idx],
            word_in_row=word_in_row,
        )
    elif field == "norm":
        pos_idx = idx // H
        elem = idx % H
        loc.update(
            position_index=pos_idx,
            position=positions[pos_idx],
            element=elem,
        )
    elif field in ("token", "logit"):
        loc.update(position_index=idx, position=positions[idx])
    return loc


def compare_dumps(
    base_dump: Path, var_dump: Path, positions: list[int]
) -> tuple[dict, int, dict | None]:
    a = load_dump(base_dump)
    b = load_dump(var_dump)
    fields_out: dict[str, dict] = {}
    total_diff = 0
    first_overall: dict | None = None

    for name in FIELDS:
        xa, xb = a[name], b[name]
        if len(xa) != len(xb):
            raise ValueError(
                f"Field {name} byte length mismatch: baseline={len(xa)} vs variant={len(xb)}"
            )
        words = len(xa) // 4
        if xa == xb:
            fields_out[name] = {
                "words": words,
                "differing": 0,
                "first_mismatch": None,
            }
            continue

        va = memoryview(xa).cast("I")
        vb = memoryview(xb).cast("I")
        diff_count = 0
        first_idx = -1
        for i in range(words):
            if va[i] != vb[i]:
                if first_idx < 0:
                    first_idx = i
                diff_count += 1
        loc = decode_mismatch_location(
            name, first_idx, int(va[first_idx]), int(vb[first_idx]), positions
        )
        fields_out[name] = {
            "words": words,
            "differing": diff_count,
            "first_mismatch": loc,
        }
        total_diff += diff_count
        if first_overall is None:
            first_overall = loc

    return fields_out, total_diff, first_overall


def obtain_baseline(
    base_dir: Path,
    source_checkout: Path,
    mode: str,
    tile_cross: bool,
    use_cache: bool,
    drive: str = "S",
) -> tuple[Path, Path, str, bool]:
    base_hash = compute_source_hash(base_dir)
    tb_hash = compute_tb_hash(
        TESTBENCH_PATH.read_bytes(), mode, tile_cross, is_single_port(base_dir)
    )
    cache_dir = (
        source_checkout
        / "build/v2/attn-reclaim/gemini/cache"
        / mode
        / f"{base_hash[:16]}_{tb_hash[:12]}"
    )
    cached_dump = cache_dir / "dump.bin"
    cached_results = cache_dir / "results.json"

    if use_cache and cached_dump.is_file() and cached_results.is_file():
        log(f"Baseline cache hit: {cache_dir}")
        return cached_dump, cached_results, base_hash, True

    run_dir = (
        source_checkout
        / "build/v2/attn-reclaim/gemini/runs"
        / f"baseline_{mode}_{base_hash[:12]}"
    )
    dump_path, results_path = run_csim(
        base_dir, run_dir, source_checkout, mode, tile_cross, drive=drive
    )
    if use_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dump_path, cached_dump)
        shutil.copyfile(results_path, cached_results)
        (cache_dir / "cache_info.json").write_text(
            json.dumps(
                {
                    "src_dir": str(base_dir),
                    "source_hash": base_hash,
                    "tb_hash": tb_hash,
                    "mode": mode,
                    "tile_cross": tile_cross,
                    "cached_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return cached_dump, cached_results, base_hash, False
    return dump_path, results_path, base_hash, False


def run_audit(
    baseline_arg: str,
    variant_arg: str,
    mode: str,
    source_checkout: Path,
    tile_cross: bool,
    use_cache: bool,
    drive: str = "S",
) -> dict:
    base_dir = resolve_src_dir(baseline_arg, source_checkout)
    var_dir = resolve_src_dir(variant_arg, source_checkout)
    var_hash = compute_source_hash(var_dir)

    base_dump, base_results_path, base_hash, cache_hit = obtain_baseline(
        base_dir, source_checkout, mode, tile_cross, use_cache, drive=drive
    )
    base_res = json.loads(base_results_path.read_text(encoding="utf-8"))

    if base_hash == var_hash:
        var_dump = base_dump
        var_res = base_res
        var_same_source = True
    else:
        var_same_source = False
        run_dir = (
            source_checkout
            / "build/v2/attn-reclaim/gemini/runs"
            / f"variant_{mode}_{var_hash[:12]}"
        )
        var_dump, var_results_path = run_csim(
            var_dir, run_dir, source_checkout, mode, tile_cross, drive=drive
        )
        var_res = json.loads(var_results_path.read_text(encoding="utf-8"))

    positions = base_res["positions"]
    if var_res["positions"] != positions:
        raise RuntimeError("Baseline and variant tested different positions")

    fields_out, total_diff, first_overall = compare_dumps(
        base_dump, var_dump, positions
    )
    nan_ok = (base_res.get("kv_nan_values", 0) == 0) and (
        var_res.get("kv_nan_values", 0) == 0
    )
    passed = (total_diff == 0) and nan_ok

    return {
        "verdict": "PASS" if passed else "FAIL",
        "exact_match": total_diff == 0,
        "mode": mode,
        "tile_boundary_crossed": bool(base_res.get("tile_boundary_crossed")),
        "tile_boundary_method": base_res.get("tile_boundary_method", "none"),
        "positions": positions,
        "baseline": {
            "src_dir": str(base_dir),
            "source_hash": base_hash,
            "cache_hit": cache_hit,
            "dump_path": str(base_dump),
            "kv_nan_values": base_res.get("kv_nan_values"),
            "elapsed_seconds": base_res.get("elapsed_seconds"),
        },
        "variant": {
            "src_dir": str(var_dir),
            "source_hash": var_hash,
            "same_source_as_baseline": var_same_source,
            "dump_path": str(var_dump),
            "kv_nan_values": var_res.get("kv_nan_values"),
            "elapsed_seconds": var_res.get("elapsed_seconds"),
        },
        "fields": fields_out,
        "total_differing_words": total_diff,
        "first_mismatch": first_overall,
    }


def self_test() -> None:
    """Offline unit tests for hashing, dump parsing, comparison, localization, and Tcl."""

    def make_dump(path: Path, hidden_w: list[int], kv_w: list[int], norm_w: list[int], tok_w: list[int], log_w: list[int]) -> None:
        buf = bytearray()
        for arr in (hidden_w, kv_w, norm_w, tok_w, log_w):
            buf += struct.pack("<Q", len(arr))
            buf += struct.pack(f"<{len(arr)}I", *arr)
        path.write_bytes(bytes(buf))

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        positions = list(range(24)) + list(range(252, 260))
        m = len(positions)
        h_n = NL * m * H
        k_n = NL * 2 * NK * m * KV_WORDS_PER_ROW
        n_n = m * H

        h0 = [0x3F800000] * h_n
        k0 = [0x3F803F80] * k_n
        n0 = [0x40000000] * n_n
        t0 = [100 + i for i in range(m)]
        l0 = [0x41200000] * m

        d_base = td / "base.bin"
        d_same = td / "same.bin"
        make_dump(d_base, h0, k0, n0, t0, l0)
        make_dump(d_same, h0, k0, n0, t0, l0)

        fields, total, first = compare_dumps(d_base, d_same, positions)
        assert total == 0 and first is None
        assert all(fields[f]["differing"] == 0 for f in FIELDS)

        # Signed zero difference in hidden: layer=2, pos_idx=25 (position=253), elem=7
        h1 = list(h0)
        idx_h = (2 * m + 25) * H + 7
        h1[idx_h] = 0x80000000
        h1[idx_h + 1] = 0x3F800001
        h0_zero = list(h0)
        h0_zero[idx_h] = 0x00000000
        d_zero_base = td / "zbase.bin"
        d_zero_var = td / "zvar.bin"
        make_dump(d_zero_base, h0_zero, k0, n0, t0, l0)
        make_dump(d_zero_var, h1, k0, n0, t0, l0)
        fields, total, first = compare_dumps(d_zero_base, d_zero_var, positions)
        assert total == 2
        assert fields["hidden"]["differing"] == 2
        assert first["field"] == "hidden"
        assert first["layer"] == 2
        assert first["position_index"] == 25
        assert first["position"] == 253
        assert first["element"] == 7
        assert first["baseline_word"] == "0x00000000"
        assert first["variant_word"] == "0x80000000"

        # KV mismatch: layer=1, kv=V, head=3, pos_idx=28 (pos=256), word=19
        k1 = list(k0)
        idx_k = ((((1 * 2 + 1) * NK + 3) * m + 28) * KV_WORDS_PER_ROW) + 19
        k1[idx_k] ^= 1
        d_kv = td / "kv.bin"
        make_dump(d_kv, h0, k1, n0, t0, l0)
        fields, total, first = compare_dumps(d_base, d_kv, positions)
        assert total == 1
        assert first["field"] == "kv"
        assert first["layer"] == 1 and first["kv"] == "V" and first["head"] == 3
        assert first["position"] == 256 and first["word_in_row"] == 19

        # Source hashing and port detection
        s1 = td / "src1"
        s1.mkdir()
        (s1 / "qwen_decoder.cpp").write_text(
            'extern "C" void qwen_decoder(weight_word *model, weight_word *model_b) {}\n'
        )
        (s1 / "matrix_q8.hpp").write_text("// header\n")
        assert not is_single_port(s1)
        hash_a = compute_source_hash(s1)
        (s1 / "matrix_q8.hpp").write_text("// header2\n")
        hash_b = compute_source_hash(s1)
        assert hash_a != hash_b

        s_single = td / "src_single"
        s_single.mkdir()
        (s_single / "qwen_decoder.cpp").write_text(
            'extern "C" void qwen_decoder(weight_word *model) {}\n'
        )
        assert is_single_port(s_single)
        tcl = render_tcl("S:/build/v2/attn-reclaim/gemini/runs/test", "decode", True, True)
        assert "-DSINGLE_PORT" in tcl
        assert "decode 1" in tcl
        tcl_t = render_tcl("T:/build/v2/attn-reclaim/gemini/runs/test", "prefill", True, False, drive="T:")
        assert "T:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf" in tcl_t
        assert normalize_drive("t:") == "T"

        # Cache key differentiation
        tb_b = b"tb"
        assert compute_tb_hash(tb_b, "decode", True, False) != compute_tb_hash(
            tb_b, "prefill", True, False
        )
        assert compute_tb_hash(tb_b, "prefill", True, False) != compute_tb_hash(
            tb_b, "prefill", False, False
        )

        # Windows subst output parsing
        subs = parse_subst_output(
            "S:\\: => C:\\Users\\user\\OneDrive - Texas Tech University\\Desktop\\Code\\FPGA Project\\system-one-fpga\\system-one-fpga\n"
        )
        assert subs["S"].endswith("system-one-fpga")

        # run_csim() must launch vitis-run with cwd=run_rel_drive (no spaces), not run_dir
        from unittest import mock

        space_checkout = td / "OneDrive - Space Test" / "system-one-fpga"
        space_checkout.mkdir(parents=True)
        space_run = space_checkout / "build/v2/attn-reclaim/gemini/runs/csim_cwd_test"
        fake_vitis = td / "vitis-run.bat"
        fake_vitis.write_text("@echo off\n", encoding="utf-8")
        fake_tb = td / "testbench.cpp"
        fake_tb.write_text("int main() { return 0; }\n", encoding="utf-8")
        captured: dict = {}

        def fake_subprocess_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["cwd"] = kwargs.get("cwd")
            make_dump(space_run / "dump.bin", h0, k0, n0, t0, l0)
            (space_run / "results.json").write_text(
                json.dumps({"positions": positions, "kv_nan_values": 0}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0)

        with (
            mock.patch.object(sys.modules[__name__], "VITIS_RUN", fake_vitis),
            mock.patch.object(sys.modules[__name__], "TESTBENCH_PATH", fake_tb),
            mock.patch.object(sys.modules[__name__], "ensure_subst", return_value="S"),
            mock.patch.object(sys.modules[__name__], "active_vitis_processes", return_value=[]),
            mock.patch.object(subprocess, "run", side_effect=fake_subprocess_run),
        ):
            dump_out, res_out = run_csim(
                s1, space_run, space_checkout, "prefill", True, drive="S"
            )
        expected_rel_drive = "S:/build/v2/attn-reclaim/gemini/runs/csim_cwd_test"
        assert captured["cwd"] == expected_rel_drive, captured
        assert " " not in str(captured["cwd"])
        assert captured["cmd"][-1] == f"{expected_rel_drive}/run_csim.tcl"
        assert dump_out == space_run / "dump.bin" and res_out == space_run / "results.json"

    print(json.dumps({"self_test": "PASS"}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", help="Baseline HLS source directory")
    ap.add_argument("--variant", help="Variant HLS source directory")
    ap.add_argument(
        "--mode",
        choices=("decode", "prefill"),
        default="prefill",
        help="Execution mode (default: prefill)",
    )
    ap.add_argument(
        "--source-checkout",
        type=Path,
        default=Path(os.environ.get("SYSONE_SOURCE_CHECKOUT", str(DEFAULT_SOURCE_CHECKOUT))),
        help="Read-only source checkout holding models/ and build/ (mapped to subst drive)",
    )
    ap.add_argument(
        "--drive",
        default=os.environ.get("SYSONE_SUBST_DRIVE", "S"),
        help="Windows subst drive letter for source checkout (default: S)",
    )
    ap.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cached baseline dump and re-run baseline C-sim",
    )
    ap.add_argument(
        "--no-tile-cross",
        action="store_true",
        help="Run only the 24-position cold prefix without crossing TILE=256",
    )
    ap.add_argument("--out", type=Path, help="Optional path to save JSON verdict")
    ap.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit with code 1 when verdict is FAIL",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="Run offline Python unit tests without invoking Vitis",
    )
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    if not args.baseline or not args.variant:
        ap.error("--baseline and --variant are required unless --self-test is specified")

    verdict = run_audit(
        args.baseline,
        args.variant,
        args.mode,
        args.source_checkout,
        tile_cross=not args.no_tile_cross,
        use_cache=not args.no_cache,
        drive=args.drive,
    )
    rendered = json.dumps(verdict, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if args.strict_exit and verdict["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
