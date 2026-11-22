"""C-sim exactness audit harness for Qwen3-0.6B HLS decoder variants.

Runs Vitis HLS C-sim (csim_design) on a baseline source directory and a
variant source directory using a shared testbench (experiments/attn_reclaim/audit/testbench.cpp),
caches baseline dumps by source+testbench hash, compares dumps word-for-word
(hidden state, K/V cache, norm, tokens, logit bits), and prints a JSON verdict
with differing word counts per field and the first mismatch location.

Usage:
  python audit.py --baseline SRC_DIR --variant SRC_DIR [--mode decode|prefill] [--batch 8|16]
  python audit.py --baseline V9I_DIR --variant V9K_DIR --mode prefill --baseline-batch 8 --batch 16 --no-tile-cross
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
DEFAULT_BATCH = 8
SUPPORTED_BATCHES = (8, 16)
META_REL_PATH = Path("build/v2/schedule-invariance-audit/meta.bin")
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


def validate_batch(batch: int) -> int:
    if isinstance(batch, bool) or batch not in SUPPORTED_BATCHES:
        raise ValueError(
            f"Unsupported batch size {batch!r}; expected one of {SUPPORTED_BATCHES}"
        )
    return int(batch)


def plan_groups(
    mode: str, n_base: int, batch: int = DEFAULT_BATCH, tile_cross: bool = True
) -> list[dict]:
    """Mirror testbench.cpp position grouping for prefill and decode."""
    if mode not in ("decode", "prefill"):
        raise ValueError(f"Unsupported mode: {mode!r}")
    b = validate_batch(batch)
    if n_base <= 0 or n_base >= 2048:
        raise ValueError(f"Invalid base position count: {n_base}")
    groups: list[dict] = []
    if mode == "prefill":
        for start in range(0, n_base, b):
            count = min(b, n_base - start)
            groups.append(
                {"start": start, "size": count, "keep": count, "seed_before": False}
            )
        if tile_cross:
            tile_start = 256 - b // 2
            if n_base > tile_start:
                raise ValueError("base positions overlap tile_cross window")
            groups.append(
                {
                    "start": tile_start,
                    "size": b,
                    "keep": b,
                    "seed_before": True,
                    "seed_from": n_base,
                    "seed_to": tile_start,
                }
            )
    else:
        for p in range(n_base):
            groups.append({"start": p, "size": 1, "keep": 1, "seed_before": False})
        if tile_cross:
            if n_base > 255:
                raise ValueError("base positions overlap decode tile_cross window")
            groups.append(
                {
                    "start": 255,
                    "size": 1,
                    "keep": 1,
                    "seed_before": True,
                    "seed_from": n_base,
                    "seed_to": 255,
                }
            )
            groups.append({"start": 256, "size": 1, "keep": 1, "seed_before": False})
            groups.append({"start": 257, "size": 1, "keep": 1, "seed_before": False})
    return groups


def expected_positions(
    mode: str, n_base: int, batch: int = DEFAULT_BATCH, tile_cross: bool = True
) -> list[int]:
    positions: list[int] = []
    for g in plan_groups(mode, n_base, batch=batch, tile_cross=tile_cross):
        positions.extend(range(g["start"], g["start"] + g["keep"]))
    return positions


def derive_groups(
    mode: str,
    positions: list[int],
    batch: int = DEFAULT_BATCH,
    tile_cross: bool = True,
) -> list[dict] | None:
    b = validate_batch(batch)
    tail_len = 0
    if tile_cross:
        tail_len = b if mode == "prefill" else 3
    n_base = len(positions) - tail_len
    if n_base <= 0 or n_base >= 2048:
        return None
    try:
        groups = plan_groups(mode, n_base, batch=b, tile_cross=tile_cross)
    except ValueError:
        return None
    expected: list[int] = []
    for g in groups:
        expected.extend(range(g["start"], g["start"] + g["keep"]))
    if positions != expected:
        return None
    return [
        {"start": g["start"], "size": g["size"], "keep": g["keep"]} for g in groups
    ]


def compute_meta_hash(meta_path: Path) -> str:
    h = hashlib.sha256()
    if meta_path.is_file():
        h.update(b"present\0")
        h.update(meta_path.read_bytes())
    else:
        h.update(b"missing\0")
    return h.hexdigest()


def is_single_port(src_dir: Path) -> bool:
    txt = (src_dir / "qwen_decoder.cpp").read_text(errors="replace")
    return re.search(r"weight_word\s*\*\s*model_b\b", txt) is None


def compute_tb_hash(
    testbench_bytes: bytes,
    mode: str,
    tile_cross: bool,
    single_port: bool,
    batch: int = DEFAULT_BATCH,
) -> str:
    b = validate_batch(batch)
    h = hashlib.sha256()
    h.update(testbench_bytes)
    h.update(
        f"\0{mode}\0{int(tile_cross)}\0{int(single_port)}\0{b}".encode("utf-8")
    )
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
    batch: int = DEFAULT_BATCH,
) -> str:
    d = normalize_drive(drive)
    b = validate_batch(batch)
    tb_cflags = "-std=c++14 -DSINGLE_PORT" if single_port else "-std=c++14"
    argv = (
        f"{d}:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf "
        f"{d}:/build/v2/schedule-invariance-audit/meta.bin "
        f"{d}:/build/v2/qwen-fpga-decoder-v9e/rope.bin "
        f"{run_rel_drive}/results.json "
        f"{run_rel_drive}/dump.bin "
        f"{mode} {1 if tile_cross else 0} {b}"
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
    batch: int = DEFAULT_BATCH,
) -> tuple[Path, Path]:
    b = validate_batch(batch)
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
        render_tcl(
            run_rel_drive, mode, tile_cross, single_port, drive=d, batch=b
        ),
        encoding="utf-8",
    )

    lock_path = source_checkout / "build/v2/attn-reclaim/gemini/.vitis.lock"
    log_path = run_dir / "csim-console.log"
    with VitisLock(lock_path):
        log(
            f"Running csim_design ({mode}, batch={b}, single_port={single_port}, drive={d}:) for {src_dir}"
        )
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


def _word_index_for_pos(
    field: str, base_idx: int, m: int, perm: list[int]
) -> int:
    """Map a baseline flat word index to the matching variant flat word index by position."""
    if field == "hidden":
        layer = base_idx // (m * H)
        pos_idx = (base_idx // H) % m
        elem = base_idx % H
        return (layer * m + perm[pos_idx]) * H + elem
    if field == "kv":
        word_in_row = base_idx % KV_WORDS_PER_ROW
        pos_idx = (base_idx // KV_WORDS_PER_ROW) % m
        rem = base_idx // (KV_WORDS_PER_ROW * m)
        return (rem * m + perm[pos_idx]) * KV_WORDS_PER_ROW + word_in_row
    if field == "norm":
        pos_idx = base_idx // H
        elem = base_idx % H
        return perm[pos_idx] * H + elem
    return perm[base_idx]


def compare_dumps(
    base_dump: Path,
    var_dump: Path,
    positions: list[int],
    var_positions: list[int] | None = None,
) -> tuple[dict, int, dict | None]:
    a = load_dump(base_dump)
    b = load_dump(var_dump)
    fields_out: dict[str, dict] = {}
    total_diff = 0
    first_overall: dict | None = None

    same_order = var_positions is None or var_positions == positions
    perm: list[int] | None = None
    if not same_order:
        if len(var_positions) != len(positions) or len(set(var_positions)) != len(var_positions):
            raise ValueError("Baseline and variant tested different position counts")
        if set(var_positions) != set(positions):
            raise ValueError("Baseline and variant tested different positions")
        var_pos_to_idx = {pos: idx for idx, pos in enumerate(var_positions)}
        perm = [var_pos_to_idx[pos] for pos in positions]
    m = len(positions)

    for name in FIELDS:
        xa, xb = a[name], b[name]
        if len(xa) != len(xb):
            raise ValueError(
                f"Field {name} byte length mismatch: baseline={len(xa)} vs variant={len(xb)}"
            )
        words = len(xa) // 4
        if same_order and xa == xb:
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
        first_var_word = 0
        if same_order:
            for i in range(words):
                if va[i] != vb[i]:
                    if first_idx < 0:
                        first_idx = i
                        first_var_word = int(vb[i])
                    diff_count += 1
        else:
            assert perm is not None
            for i in range(words):
                vi = _word_index_for_pos(name, i, m, perm)
                if va[i] != vb[vi]:
                    if first_idx < 0:
                        first_idx = i
                        first_var_word = int(vb[vi])
                    diff_count += 1

        if diff_count == 0:
            fields_out[name] = {
                "words": words,
                "differing": 0,
                "first_mismatch": None,
            }
            continue

        loc = decode_mismatch_location(
            name, first_idx, int(va[first_idx]), first_var_word, positions
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
    batch: int = DEFAULT_BATCH,
) -> tuple[Path, Path, str, bool]:
    b = validate_batch(batch)
    base_hash = compute_source_hash(base_dir)
    meta_path = source_checkout / META_REL_PATH
    meta_hash = compute_meta_hash(meta_path)
    tb_hash = compute_tb_hash(
        TESTBENCH_PATH.read_bytes(),
        mode,
        tile_cross,
        is_single_port(base_dir),
        batch=b,
    )
    cache_dir = (
        source_checkout
        / "build/v2/attn-reclaim/gemini/cache"
        / mode
        / f"{base_hash[:16]}_{tb_hash[:12]}_{meta_hash[:12]}"
    )
    cached_dump = cache_dir / "dump.bin"
    cached_results = cache_dir / "results.json"

    if use_cache and cached_dump.is_file() and cached_results.is_file():
        log(f"Baseline cache hit: {cache_dir}")
        return cached_dump, cached_results, base_hash, True

    run_dir = (
        source_checkout
        / "build/v2/attn-reclaim/gemini/runs"
        / f"baseline_{mode}_b{b}_{base_hash[:12]}"
    )
    dump_path, results_path = run_csim(
        base_dir, run_dir, source_checkout, mode, tile_cross, drive=drive, batch=b
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
                    "meta_hash": meta_hash,
                    "meta_path": str(meta_path),
                    "mode": mode,
                    "batch": b,
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
    batch: int = DEFAULT_BATCH,
    baseline_batch: int | None = None,
) -> dict:
    var_batch = validate_batch(batch)
    base_batch = validate_batch(var_batch if baseline_batch is None else baseline_batch)
    if mode == "prefill" and tile_cross and base_batch != var_batch:
        raise ValueError(
            f"Mixed-size prefill (--baseline-batch {base_batch} vs --batch {var_batch}) "
            "with TILE crossing enabled cannot compare equal position sets; "
            "pass --no-tile-cross when comparing different batch sizes"
        )
    base_dir = resolve_src_dir(baseline_arg, source_checkout)
    var_dir = resolve_src_dir(variant_arg, source_checkout)
    var_hash = compute_source_hash(var_dir)

    base_dump, base_results_path, base_hash, cache_hit = obtain_baseline(
        base_dir,
        source_checkout,
        mode,
        tile_cross,
        use_cache,
        drive=drive,
        batch=base_batch,
    )
    base_res = json.loads(base_results_path.read_text(encoding="utf-8"))

    if base_hash == var_hash and base_batch == var_batch:
        var_dump = base_dump
        var_res = base_res
        var_same_source = True
    else:
        var_same_source = False
        run_dir = (
            source_checkout
            / "build/v2/attn-reclaim/gemini/runs"
            / f"variant_{mode}_b{var_batch}_{var_hash[:12]}"
        )
        var_dump, var_results_path = run_csim(
            var_dir,
            run_dir,
            source_checkout,
            mode,
            tile_cross,
            drive=drive,
            batch=var_batch,
        )
        var_res = json.loads(var_results_path.read_text(encoding="utf-8"))

    positions = base_res["positions"]
    var_positions = var_res["positions"]
    if len(var_positions) != len(positions) or set(var_positions) != set(positions):
        raise RuntimeError(
            "Baseline and variant tested different positions "
            f"(baseline={len(positions)} @ batch={base_batch}, "
            f"variant={len(var_positions)} @ batch={var_batch}; "
            "pass --no-tile-cross when comparing different batch sizes)"
        )

    fields_out, total_diff, first_overall = compare_dumps(
        base_dump, var_dump, positions, var_positions=var_positions
    )
    nan_ok = (base_res.get("kv_nan_values", 0) == 0) and (
        var_res.get("kv_nan_values", 0) == 0
    )
    passed = (total_diff == 0) and nan_ok
    base_groups = base_res.get("groups") or derive_groups(
        mode, positions, batch=base_batch, tile_cross=tile_cross
    )
    var_groups = var_res.get("groups") or derive_groups(
        mode, var_positions, batch=var_batch, tile_cross=tile_cross
    )

    return {
        "verdict": "PASS" if passed else "FAIL",
        "exact_match": total_diff == 0,
        "mode": mode,
        "batch": var_batch,
        "baseline_batch": base_batch,
        "tile_boundary_crossed": bool(base_res.get("tile_boundary_crossed")),
        "tile_boundary_method": base_res.get("tile_boundary_method", "none"),
        "positions": positions,
        "baseline": {
            "src_dir": str(base_dir),
            "source_hash": base_hash,
            "batch": base_batch,
            "groups": base_groups,
            "cache_hit": cache_hit,
            "dump_path": str(base_dump),
            "kv_nan_values": base_res.get("kv_nan_values"),
            "elapsed_seconds": base_res.get("elapsed_seconds"),
        },
        "variant": {
            "src_dir": str(var_dir),
            "source_hash": var_hash,
            "batch": var_batch,
            "groups": var_groups,
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

        # N=16 argument handling and validation
        import contextlib
        import io

        parser = build_parser()
        args_default = parser.parse_args(["--baseline", "a", "--variant", "b"])
        assert args_default.batch == 8 and args_default.baseline_batch is None
        args_b16 = parser.parse_args(
            [
                "--baseline",
                "a",
                "--variant",
                "b",
                "--mode",
                "prefill",
                "--baseline-batch",
                "8",
                "--batch",
                "16",
                "--no-tile-cross",
            ]
        )
        assert args_b16.batch == 16 and args_b16.baseline_batch == 8
        assert args_b16.no_tile_cross is True
        for bad_batch in ("4", "12", "32"):
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    parser.parse_args(["--baseline", "a", "--variant", "b", "--batch", bad_batch])
                raise AssertionError(f"Expected invalid --batch {bad_batch} to fail")
            except SystemExit:
                pass
        for bad_val in (0, 4, 12, 32, True):
            try:
                validate_batch(bad_val)  # type: ignore[arg-type]
                raise AssertionError(f"Expected validate_batch({bad_val!r}) to fail")
            except ValueError:
                pass

        # Position grouping for N=8 vs N=16 across 24 and 32 prompt positions
        g8_24 = plan_groups("prefill", 24, batch=8, tile_cross=False)
        g16_24 = plan_groups("prefill", 24, batch=16, tile_cross=False)
        assert [(g["start"], g["size"]) for g in g8_24] == [(0, 8), (8, 8), (16, 8)]
        assert [(g["start"], g["size"]) for g in g16_24] == [(0, 16), (16, 8)]
        assert expected_positions("prefill", 24, batch=8, tile_cross=False) == list(range(24))
        assert expected_positions("prefill", 24, batch=16, tile_cross=False) == list(range(24))

        g8_32 = plan_groups("prefill", 32, batch=8, tile_cross=False)
        g16_32 = plan_groups("prefill", 32, batch=16, tile_cross=False)
        assert [(g["start"], g["size"]) for g in g8_32] == [
            (0, 8),
            (8, 8),
            (16, 8),
            (24, 8),
        ]
        assert [(g["start"], g["size"]) for g in g16_32] == [(0, 16), (16, 16)]
        assert expected_positions("prefill", 32, batch=8, tile_cross=False) == list(range(32))
        assert expected_positions("prefill", 32, batch=16, tile_cross=False) == list(range(32))

        g8_tc = plan_groups("prefill", 24, batch=8, tile_cross=True)
        g16_tc = plan_groups("prefill", 24, batch=16, tile_cross=True)
        assert [(g["start"], g["size"]) for g in g8_tc] == [
            (0, 8),
            (8, 8),
            (16, 8),
            (252, 8),
        ]
        assert g8_tc[-1]["seed_from"] == 24 and g8_tc[-1]["seed_to"] == 252
        assert [(g["start"], g["size"]) for g in g16_tc] == [
            (0, 16),
            (16, 8),
            (248, 16),
        ]
        assert g16_tc[-1]["seed_from"] == 24 and g16_tc[-1]["seed_to"] == 248
        assert expected_positions("prefill", 24, batch=8, tile_cross=True) == (
            list(range(24)) + list(range(252, 260))
        )
        assert expected_positions("prefill", 24, batch=16, tile_cross=True) == (
            list(range(24)) + list(range(248, 264))
        )

        # Per-position comparison even when group boundaries or position order differ
        pos24 = list(range(24))
        m24 = len(pos24)
        h24 = [0x3F800000 + (i % m24) for i in range(NL * m24 * H)]
        k24 = [0x3F803F80 + ((i // KV_WORDS_PER_ROW) % m24) for i in range(NL * 2 * NK * m24 * KV_WORDS_PER_ROW)]
        n24 = [0x40000000 + (i // H) for i in range(m24 * H)]
        t24 = [500 + p for p in pos24]
        l24 = [0x41200000 + p for p in pos24]
        # Give each position distinct values in hidden/norm/kv so reordering proves per-position lookup
        for layer in range(NL):
            for pidx in range(m24):
                h24[(layer * m24 + pidx) * H] = 0x3F800000 + layer * 100 + pidx
        d_b8_24 = td / "b8_24.bin"
        d_b16_24 = td / "b16_24.bin"
        make_dump(d_b8_24, h24, k24, n24, t24, l24)
        # Reorder variant positions to verify per-position (not positional-slot) mapping
        perm_pos = list(reversed(pos24))
        h24_perm = list(h24)
        k24_perm = list(k24)
        n24_perm = list(n24)
        for layer in range(NL):
            for new_i, old_i in enumerate(reversed(range(m24))):
                s0 = (layer * m24 + old_i) * H
                d0 = (layer * m24 + new_i) * H
                h24_perm[d0 : d0 + H] = h24[s0 : s0 + H]
        for layer in range(NL):
            for kv in range(2):
                for head in range(NK):
                    for new_i, old_i in enumerate(reversed(range(m24))):
                        s0 = (((layer * 2 + kv) * NK + head) * m24 + old_i) * KV_WORDS_PER_ROW
                        d0 = (((layer * 2 + kv) * NK + head) * m24 + new_i) * KV_WORDS_PER_ROW
                        k24_perm[d0 : d0 + KV_WORDS_PER_ROW] = k24[s0 : s0 + KV_WORDS_PER_ROW]
        for new_i, old_i in enumerate(reversed(range(m24))):
            n24_perm[new_i * H : (new_i + 1) * H] = n24[old_i * H : (old_i + 1) * H]
        t24_perm = list(reversed(t24))
        l24_perm = list(reversed(l24))
        make_dump(d_b16_24, h24_perm, k24_perm, n24_perm, t24_perm, l24_perm)
        f_perm, tot_perm, first_perm = compare_dumps(
            d_b8_24, d_b16_24, pos24, var_positions=perm_pos
        )
        assert tot_perm == 0 and first_perm is None
        assert all(f_perm[f]["differing"] == 0 for f in FIELDS)
        # Flip position 16 (group 2 in batch-8, group 1 in batch-16) and verify exact localization
        t24_perm_diff = list(t24_perm)
        t24_perm_diff[perm_pos.index(16)] ^= 1
        d_b16_24_diff = td / "b16_24_diff.bin"
        make_dump(d_b16_24_diff, h24_perm, k24_perm, n24_perm, t24_perm_diff, l24_perm)
        f_pdiff, tot_pdiff, first_pdiff = compare_dumps(
            d_b8_24, d_b16_24_diff, pos24, var_positions=perm_pos
        )
        assert tot_pdiff == 1 and first_pdiff is not None
        assert first_pdiff["field"] == "token" and first_pdiff["position"] == 16

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
        assert "decode 1 8" in tcl
        tcl_t = render_tcl(
            "T:/build/v2/attn-reclaim/gemini/runs/test",
            "prefill",
            False,
            False,
            drive="T:",
            batch=16,
        )
        assert "T:/models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf" in tcl_t
        assert "prefill 0 16" in tcl_t
        assert normalize_drive("t:") == "T"

        # Cache key differentiation (mode, tile_cross, single_port, batch)
        tb_b = b"tb"
        assert compute_tb_hash(tb_b, "decode", True, False) != compute_tb_hash(
            tb_b, "prefill", True, False
        )
        assert compute_tb_hash(tb_b, "prefill", True, False) != compute_tb_hash(
            tb_b, "prefill", False, False
        )
        assert compute_tb_hash(tb_b, "prefill", False, False, batch=8) != compute_tb_hash(
            tb_b, "prefill", False, False, batch=16
        )

        # Windows subst output parsing and ensure_subst
        subs = parse_subst_output(
            "S:\\: => C:\\Users\\user\\OneDrive - Texas Tech University\\Desktop\\Code\\FPGA Project\\system-one-fpga\\system-one-fpga\n"
        )
        assert subs["S"].endswith("system-one-fpga")

        from unittest import mock

        space_checkout = td / "OneDrive - Space Test" / "system-one-fpga"
        space_checkout.mkdir(parents=True)
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                ["subst"], 0, stdout=f"T:\\: => {space_checkout}\n", stderr=""
            ),
        ):
            assert ensure_subst(space_checkout, "t:") == "T"
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                ["subst"], 0, stdout="T:\\: => C:\\Other\\Path\n", stderr=""
            ),
        ):
            try:
                ensure_subst(space_checkout, "T")
                raise AssertionError("Expected conflicting subst mapping to raise")
            except RuntimeError:
                pass

        # run_csim() must launch vitis-run with cwd=run_rel_drive (no spaces), not run_dir
        space_run = space_checkout / "build/v2/attn-reclaim/gemini/runs/csim_cwd_test"
        fake_vitis = td / "vitis-run.bat"
        fake_vitis.write_text("@echo off\n", encoding="utf-8")
        fake_tb = td / "testbench.cpp"
        fake_tb.write_text("int main() { return 0; }\n", encoding="utf-8")
        captured: dict = {}

        def write_meta_bin(path: Path, tok_ids: list[int]) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            words = [0] * (3 + NL * 11) + [len(tok_ids)] + list(tok_ids)
            path.write_bytes(struct.pack(f"<{len(words)}I", *words))

        def make_dummy_dump_and_results(run_path: Path, pos_list: list[int], mode_name: str, tc: bool) -> None:
            m_len = len(pos_list)
            make_dump(
                run_path / "dump.bin",
                [0x3F800000] * (NL * m_len * H),
                [0x3F803F80] * (NL * 2 * NK * m_len * KV_WORDS_PER_ROW),
                [0x40000000] * (m_len * H),
                [100 + p for p in pos_list],
                [0x41200000] * m_len,
            )
            (run_path / "results.json").write_text(
                json.dumps(
                    {
                        "mode": mode_name,
                        "tile_boundary_crossed": tc,
                        "tile_boundary_method": "deterministic_kv_seed" if tc else "none",
                        "positions": pos_list,
                        "tokens": [100 + p for p in pos_list],
                        "kv_nan_values": 0,
                        "elapsed_seconds": 0.1,
                    }
                ),
                encoding="utf-8",
            )

        meta_file = space_checkout / META_REL_PATH
        write_meta_bin(meta_file, list(range(10, 34)))

        def fake_subprocess_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["cwd"] = kwargs.get("cwd")
            captured["calls"] = captured.get("calls", 0) + 1
            run_path = Path(
                str(kwargs["cwd"])
                .replace("S:/", str(space_checkout) + "/")
                .replace("T:/", str(space_checkout) + "/")
            )
            tcl_txt = (run_path / "run_csim.tcl").read_text(encoding="utf-8")
            m_argv = re.search(r'-argv "([^"]+)"', tcl_txt)
            assert m_argv is not None
            argv_parts = m_argv.group(1).split()
            mode_name = argv_parts[-3]
            tc = argv_parts[-2] != "0"
            b_val = int(argv_parts[-1])
            meta_bytes = meta_file.read_bytes()
            n_meta = struct.unpack_from("<I", meta_bytes, (3 + NL * 11) * 4)[0]
            pos_list = expected_positions(mode_name, n_meta, batch=b_val, tile_cross=tc)
            make_dummy_dump_and_results(run_path, pos_list, mode_name, tc)
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

        # Verify N=16 subst-drive cwd and run_audit comparing batch=8 baseline vs batch=16 variant
        space_run_b16 = space_checkout / "build/v2/attn-reclaim/gemini/runs/csim_cwd_b16_test"
        with (
            mock.patch.object(sys.modules[__name__], "VITIS_RUN", fake_vitis),
            mock.patch.object(sys.modules[__name__], "TESTBENCH_PATH", fake_tb),
            mock.patch.object(sys.modules[__name__], "ensure_subst", return_value="T"),
            mock.patch.object(sys.modules[__name__], "active_vitis_processes", return_value=[]),
            mock.patch.object(subprocess, "run", side_effect=fake_subprocess_run),
        ):
            dump_b16, res_b16 = run_csim(
                s1,
                space_run_b16,
                space_checkout,
                "prefill",
                False,
                drive="T:",
                batch=16,
            )
        expected_b16_drive = "T:/build/v2/attn-reclaim/gemini/runs/csim_cwd_b16_test"
        assert captured["cwd"] == expected_b16_drive, captured
        assert " " not in str(captured["cwd"])
        assert captured["cmd"][-1] == f"{expected_b16_drive}/run_csim.tcl"
        assert "prefill 0 16" in (space_run_b16 / "run_csim.tcl").read_text(encoding="utf-8")
        assert dump_b16 == space_run_b16 / "dump.bin" and res_b16 == space_run_b16 / "results.json"

        # Original results.json schema (no batch/groups keys) still derives groups in verdict
        with (
            mock.patch.object(sys.modules[__name__], "VITIS_RUN", fake_vitis),
            mock.patch.object(sys.modules[__name__], "TESTBENCH_PATH", fake_tb),
            mock.patch.object(sys.modules[__name__], "ensure_subst", return_value="S"),
            mock.patch.object(sys.modules[__name__], "active_vitis_processes", return_value=[]),
            mock.patch.object(subprocess, "run", side_effect=fake_subprocess_run),
        ):
            verdict = run_audit(
                str(s1),
                str(s1),
                "prefill",
                space_checkout,
                tile_cross=False,
                use_cache=True,
                drive="S",
                batch=16,
                baseline_batch=8,
            )
        assert verdict["verdict"] == "PASS"
        assert verdict["baseline_batch"] == 8 and verdict["batch"] == 16
        assert verdict["baseline"]["groups"] == [
            {"start": 0, "size": 8, "keep": 8},
            {"start": 8, "size": 8, "keep": 8},
            {"start": 16, "size": 8, "keep": 8},
        ]
        assert verdict["variant"]["groups"] == [
            {"start": 0, "size": 16, "keep": 16},
            {"start": 16, "size": 8, "keep": 8},
        ]
        assert verdict["variant"]["same_source_as_baseline"] is False
        assert verdict["positions"] == pos24
        assert verdict["total_differing_words"] == 0

        # [P1] Baseline cache must include meta.bin content digest before same-source reuse
        captured["calls"] = 0
        write_meta_bin(meta_file, list(range(100, 124)))
        with (
            mock.patch.object(sys.modules[__name__], "VITIS_RUN", fake_vitis),
            mock.patch.object(sys.modules[__name__], "TESTBENCH_PATH", fake_tb),
            mock.patch.object(sys.modules[__name__], "ensure_subst", return_value="S"),
            mock.patch.object(sys.modules[__name__], "active_vitis_processes", return_value=[]),
            mock.patch.object(subprocess, "run", side_effect=fake_subprocess_run),
        ):
            v_24_a = run_audit(
                str(s1),
                str(s1),
                "prefill",
                space_checkout,
                tile_cross=True,
                use_cache=True,
                drive="S",
                batch=8,
            )
            assert v_24_a["baseline"]["cache_hit"] is False
            assert captured["calls"] == 1
            assert len(v_24_a["positions"]) == 32

            v_24_b = run_audit(
                str(s1),
                str(s1),
                "prefill",
                space_checkout,
                tile_cross=True,
                use_cache=True,
                drive="S",
                batch=8,
            )
            assert v_24_b["baseline"]["cache_hit"] is True
            assert captured["calls"] == 1

            # Rewrite meta.bin to 32 positions and different token IDs -> cache miss + rerun
            write_meta_bin(meta_file, list(range(200, 232)))
            v_32_a = run_audit(
                str(s1),
                str(s1),
                "prefill",
                space_checkout,
                tile_cross=True,
                use_cache=True,
                drive="S",
                batch=8,
            )
            assert v_32_a["baseline"]["cache_hit"] is False
            assert captured["calls"] == 2
            assert len(v_32_a["positions"]) == 40

            # Same 32-position length but different token IDs -> cache miss + rerun
            write_meta_bin(meta_file, list(range(300, 332)))
            v_32_b = run_audit(
                str(s1),
                str(s1),
                "prefill",
                space_checkout,
                tile_cross=True,
                use_cache=True,
                drive="S",
                batch=8,
            )
            assert v_32_b["baseline"]["cache_hit"] is False
            assert captured["calls"] == 3

        # [P2] Reject mixed-size prefill with tile_cross=True before cache lookup or simulation
        with (
            mock.patch.object(sys.modules[__name__], "obtain_baseline") as m_cache,
            mock.patch.object(sys.modules[__name__], "run_csim") as m_csim,
        ):
            try:
                run_audit(
                    str(s1),
                    str(s1),
                    "prefill",
                    space_checkout,
                    tile_cross=True,
                    use_cache=True,
                    drive="S",
                    batch=16,
                    baseline_batch=8,
                )
                raise AssertionError("Expected mixed-size prefill with tile_cross=True to fail")
            except ValueError as exc:
                assert "--no-tile-cross" in str(exc)
            assert m_cache.call_count == 0 and m_csim.call_count == 0

            cli_err = io.StringIO()
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "audit.py",
                        "--baseline",
                        str(s1),
                        "--variant",
                        str(s1),
                        "--mode",
                        "prefill",
                        "--baseline-batch",
                        "8",
                        "--batch",
                        "16",
                    ],
                ),
                contextlib.redirect_stderr(cli_err),
            ):
                try:
                    main()
                    raise AssertionError("Expected CLI mixed-size prefill without --no-tile-cross to fail")
                except SystemExit as exc:
                    assert exc.code != 0
            assert "--no-tile-cross" in cli_err.getvalue()
            assert m_cache.call_count == 0 and m_csim.call_count == 0

    print(json.dumps({"self_test": "PASS"}, indent=2))


def build_parser() -> argparse.ArgumentParser:
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
        "--batch",
        type=int,
        choices=SUPPORTED_BATCHES,
        default=DEFAULT_BATCH,
        help="Prefill batch size N (8 or 16; default: 8)",
    )
    ap.add_argument(
        "--baseline-batch",
        type=int,
        choices=SUPPORTED_BATCHES,
        default=None,
        help="Optional baseline batch size N (defaults to --batch); e.g. --baseline-batch 8 --batch 16",
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
        help="Run only the cold prefix positions without crossing TILE=256",
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
    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    if not args.baseline or not args.variant:
        ap.error("--baseline and --variant are required unless --self-test is specified")

    if (
        args.mode == "prefill"
        and not args.no_tile_cross
        and args.baseline_batch is not None
        and args.baseline_batch != args.batch
    ):
        ap.error(
            f"Mixed-size prefill (--baseline-batch {args.baseline_batch} vs --batch {args.batch}) "
            "with TILE crossing enabled cannot compare equal position sets; "
            "pass --no-tile-cross when comparing different batch sizes"
        )

    verdict = run_audit(
        args.baseline,
        args.variant,
        args.mode,
        args.source_checkout,
        tile_cross=not args.no_tile_cross,
        use_cache=not args.no_cache,
        drive=args.drive,
        batch=args.batch,
        baseline_batch=args.baseline_batch,
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
