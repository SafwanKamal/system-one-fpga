"""Bad deployment inputs must never replace the running FPGA app."""
import hashlib
import json
from pathlib import Path
import struct
import sys

import pytest

from scripts.v2.kr260 import deploy_app as app


@pytest.fixture
def board(tmp_path, monkeypatch):
    dt = tmp_path / "dt"
    region = dt / "reserved-memory/sysone@60000000"
    region.mkdir(parents=True)
    (dt / "model").write_bytes(b"ZynqMP KR260 revB\0")
    (region / "no-map").touch()
    (region / "reg").write_bytes(struct.pack(">IIII", 0, 0x60000000, 0, 64 << 20))
    iomem = tmp_path / "iomem"
    iomem.write_text("60000000-63ffffff : reserved\n")
    package = tmp_path / "package"
    package.mkdir()
    hashes = {}
    for name in ("sysone-v2.bit.bin", "sysone-v2.dtbo", "shell.json"):
        payload = name.encode()
        (package / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    (package / "build.json").write_text(json.dumps({"files_sha256": hashes,
        "clock_requested_hz": 75000000, "clock_timing_max_hz": 80000000}))
    target = tmp_path / "installed-app"
    redirects = {"/sys/firmware/devicetree/base": dt, "/proc/iomem": iomem,
                 "/lib/firmware/xilinx/sysone-v2": target}
    state = tmp_path / "state"
    state.write_text("operating\n")
    clocks = tmp_path / "clocks"
    clocks.write_text("pl0_ref 1 1 0 100000000\n")
    redirects.update({"/sys/class/fpga_manager/fpga0/state": state,
                      "/sys/kernel/debug/clk/clk_summary": clocks})
    (dt / "__symbols__").mkdir()
    (dt / "__symbols__/amba").write_bytes(b"/axi\0")
    monkeypatch.setattr(app, "Path", lambda path: redirects.get(str(path), Path(path)))
    monkeypatch.setattr(app.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(app.shutil, "which", lambda name: "/usr/bin/xmutil")
    calls = []
    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["deploy_app.py", str(package)])
    return region, iomem, package, target, calls


def test_corrupt_bitstream_cannot_install_or_unload(board):
    _, _, package, target, calls = board
    (package / "sysone-v2.bit.bin").write_bytes(b"corrupt transfer")
    with pytest.raises(SystemExit, match="Package hash mismatch"):
        app.main()
    assert not target.exists()
    assert calls == []


def test_missing_no_map_cannot_install_or_unload(board):
    region, _, _, target, calls = board
    (region / "no-map").unlink()
    with pytest.raises(SystemExit, match="no-map boot reservation"):
        app.main()
    assert not target.exists()
    assert calls == []


def test_kernel_ram_cannot_install_or_unload(board):
    _, iomem, _, target, calls = board
    iomem.write_text("60000000-63ffffff : System RAM\n")
    with pytest.raises(SystemExit, match="iomem does not confirm"):
        app.main()
    assert not target.exists()
    assert calls == []


def test_frontier_without_routed_hold_cannot_install_or_unload(board):
    _, _, package, target, calls = board
    manifest = json.loads((package / "build.json").read_text())
    hashes = {}
    for name, digest in manifest["files_sha256"].items():
        renamed = name.replace("sysone-v2.", "sysone-v2-frontier.")
        (package / name).rename(package / renamed)
        hashes[renamed] = digest
    manifest.update(files_sha256=hashes, app_name="sysone-v2-frontier", max_hidden=1024,
                    mac_input_registers=1, exp_table_in_bram=1, pipelined_uram=1,
                    activation_read_latency=4, stream_results=1, local_query_registers=1,
                    perf_counters=1, local_accumulator_controls=1, pipelined_dot=1,
                    registered_requests=1, timing_qualified=True,
                    routed_setup_slack_ns=0.4, routed_hold_slack_ns=-0.01)
    (package / "build.json").write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="routed timing evidence"):
        app.main()
    assert not target.exists()
    assert calls == []


def test_expanded_boot_reservation_passes_deploy_memory_checks(board,monkeypatch):
    region,iomem,_,_,_ = board
    (region / "reg").write_bytes(struct.pack(">QQ",0x60000000,256 << 20))
    iomem.write_text("60000000-6fffffff : reserved\n")
    monkeypatch.setattr(app, "bound", lambda *args: True)
    # Fixture's deliberately excessive live clock rejects before MMIO, proving
    # that the valid expanded memory region passed all earlier deployment guards.
    with pytest.raises(SystemExit, match="outside the requested/validated range"):
        app.main()


def test_live_clock_above_timing_ceiling_cannot_probe_mmio(board, monkeypatch):
    monkeypatch.setattr(app, "bound", lambda *args: True)
    def forbidden(*args, **kwargs):
        pytest.fail("MMIO must not be opened with a clock above the timing ceiling")
    monkeypatch.setattr(app.os, "open", forbidden)
    with pytest.raises(SystemExit, match="outside the requested/validated range"):
        app.main()


@pytest.mark.parametrize("candidate_app,wrong_feature", [
    (name,None) for name in ["sysone-v2-pipe","sysone-v2-bram","sysone-v2-wide","sysone-v2-memory","sysone-v2-frontier","sysone-v2-capture","sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"]
] + [("sysone-v2-request-window-embed",word) for word in (0x5361ffff,0x5362ffff,0x535affff)] + [("sysone-v2-attention16-distance",word) for word in (0x535a7fff,0x535abfff,0x53597fff)] + [("sysone-v2-capture-flags",0x5359017f),("sysone-v2-pipeline-cuts",0x535901ff),("sysone-v2-pipeline-cuts",0x535905ff),("sysone-v2-pipeline-cuts",0x535906ff)] + [("sysone-v2-operand-capture",word) for word in (0x535907ff,0x535917ff,0x53591bff,0x53590301)])
def test_pipeline_install_preserves_baseline_and_checks_live_clock(board, monkeypatch, candidate_app,wrong_feature):
    _, _, package, target, calls = board
    manifest = json.loads((package / "build.json").read_text())
    hashes = {}
    for name, digest in manifest["files_sha256"].items():
        renamed = name.replace("sysone-v2.", f"{candidate_app}.")
        (package / name).rename(package / renamed)
        hashes[renamed] = digest
    manifest.update(files_sha256=hashes, app_name=candidate_app, mac_input_registers=1,
                    exp_table_in_bram=int(candidate_app in {"sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory"}),
                    max_hidden=768 if candidate_app in {"sysone-v2-wide", "sysone-v2-memory"} else 384,
                    pipelined_uram=int(candidate_app == "sysone-v2-memory"),
                    activation_read_latency=4 if candidate_app == "sysone-v2-memory" else 3,
                    clock_requested_hz=125000000, clock_timing_max_hz=125000000)
    if candidate_app in {"sysone-v2-frontier","sysone-v2-capture","sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        manifest.update(candidate="request-window-embed-large" if candidate_app=="sysone-v2-request-window-embed" else "attention16-distance-large" if candidate_app=="sysone-v2-attention16-distance" else "source-row-bram-large" if candidate_app=="sysone-v2-source-row-bram" else "operand-capture-large" if candidate_app=="sysone-v2-operand-capture" else "pipeline-cuts-large" if candidate_app=="sysone-v2-pipeline-cuts" else "capture-flags-large" if candidate_app=="sysone-v2-capture-flags" else "capture-large" if candidate_app=="sysone-v2-capture" else "dot7-large",exp_table_in_bram=1,max_hidden=1024,pipelined_uram=1,
                        activation_read_latency=5 if candidate_app.startswith("sysone-v2-capture") or candidate_app in {"sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"} else 4,
                        local_read_capture=int(candidate_app.startswith("sysone-v2-capture") or candidate_app in {"sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}),registered_fifo_flags=int(candidate_app in {"sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}),probability_pipeline=int(candidate_app in {"sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}),pipelined_drain_select=int(candidate_app in {"sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}),local_accumulator_controls=3,stream_results=1,
                        local_query_registers=1,perf_counters=1,pipelined_dot=1,registered_requests=1,
                        timing_qualified=True,routed_setup_slack_ns=.401,routed_hold_slack_ns=.010)
    if candidate_app in {"sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        manifest.update(probability_input_capture=1,local_embed_controls=1,capability_word="0x53591fff")
    if candidate_app in {"sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        manifest.update(incremental_source_row=1,linear_accumulators_in_bram=1,capability_word="0x53597fff")
    if candidate_app in {"sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        manifest.update(attention_lanes=16,fabric_score_distance=1,capability_word="0x535affff",
                        numerical_cases=32,query_group_cases=4,partial_tile_cases=6,
                        nexys_default_cycles_unchanged=True,
                        encoder_cycle_change_vs_32query_range_percent=[0.0,5.320035251540278])
    if candidate_app in {"sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        manifest.update(cached_request_window=1,dsp_embed_row_address=1,capability_word="0x5363ffff",
                        clock_requested_hz=200000000,clock_timing_max_hz=200000000,
                        rtl_sha256={f'rtl/v2/source{i}.sv':'0'*64 for i in range(23)})
    if candidate_app=="sysone-v2-attention-context-capture":
        from scripts.v2.kr260.package_app import frontier_profile
        manifest.update(frontier_profile('attention-context-capture-large'))
        manifest.update(candidate='attention-context-capture-large',capability_word='0x5377ffff',clock_requested_hz=200000000,clock_timing_max_hz=200000000,numerical_cases=32,query_group_cases=4,partial_tile_cases=6,nexys_default_cycles_unchanged=True,encoder_cycle_change_vs_32query_range_percent=[0.0,5.320035251540278],rtl_sha256={f'rtl/v2/source{i}.sv':'0'*64 for i in range(23)})
    (package / "build.json").write_text(json.dumps(manifest))
    pipeline_target = target.parent / "pipeline-app"
    original_path = app.Path
    monkeypatch.setattr(app, "Path", lambda path: pipeline_target
        if str(path) == f"/lib/firmware/xilinx/{candidate_app}" else original_path(path))
    app.Path("/sys/kernel/debug/clk/clk_summary").write_text("pl0_ref 1 1 0 124999999\n")
    if candidate_app in {"sysone-v2-frontier","sysone-v2-capture","sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        app.Path("/sys/kernel/debug/clk/clk_summary").write_text("pl0_ref 1 1 0 124999999\npl1_ref 1 1 0 124999999\n")
    if candidate_app in {"sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:
        app.Path("/sys/kernel/debug/clk/clk_summary").write_text("pl0_ref 1 1 0 199999998\npl1_ref 1 1 0 199999998\n")
    monkeypatch.setattr(app, "bound", lambda *args: True)
    regs = bytearray(4096)
    struct.pack_into("<II", regs, 0x14, 0x53595332,
                     0x20804004 if candidate_app in {"sysone-v2-frontier","sysone-v2-capture","sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"} else
                     0x20803004 if candidate_app in {"sysone-v2-wide", "sysone-v2-memory"} else 0x20801804)
    if candidate_app in {"sysone-v2-frontier","sysone-v2-capture","sysone-v2-capture-flags","sysone-v2-pipeline-cuts","sysone-v2-operand-capture","sysone-v2-source-row-bram","sysone-v2-attention16-distance","sysone-v2-request-window-embed","sysone-v2-attention-context-capture"}:struct.pack_into("<I",regs,0x1c,wrong_feature if wrong_feature is not None else 0x5377ffff if candidate_app=="sysone-v2-attention-context-capture" else 0x5363ffff if candidate_app=="sysone-v2-request-window-embed" else 0x535affff if candidate_app=="sysone-v2-attention16-distance" else 0x53597fff if candidate_app=="sysone-v2-source-row-bram" else 0x53591fff if candidate_app=="sysone-v2-operand-capture" else 0x535907ff if candidate_app=="sysone-v2-pipeline-cuts" else 0x535901ff if candidate_app=="sysone-v2-capture-flags" else 0x5359017f if candidate_app=="sysone-v2-capture" else 0x5359013f)
    class Mapping:
        def __enter__(self): return regs
        def __exit__(self, *args): pass
    monkeypatch.setattr(app.os, "O_SYNC", 0, raising=False)
    monkeypatch.setattr(app.os, "open", lambda *args: 42)
    monkeypatch.setattr(app.os, "close", lambda *args: None)
    monkeypatch.setattr(app.mmap, "mmap", lambda *args, **kwargs: Mapping())
    monkeypatch.setattr(app.mmap, "MAP_SHARED", 1, raising=False)
    monkeypatch.setattr(app.mmap, "PROT_READ", 1, raising=False)
    if wrong_feature is not None:
        with pytest.raises(SystemExit,match="feature register mismatch"):app.main()
    else:
        app.main()
    assert pipeline_target.is_dir()
    assert not target.exists()
    assert any(args[0][-2:] == ["loadapp", candidate_app] for args in calls)


def test_bram_profile_is_required_before_installing_or_unloading(board):
    _, _, package, target, calls = board
    manifest = json.loads((package / "build.json").read_text())
    hashes = {}
    for name, digest in manifest["files_sha256"].items():
        renamed = name.replace("sysone-v2.", "sysone-v2-bram.")
        (package / name).rename(package / renamed)
        hashes[renamed] = digest
    manifest.update(files_sha256=hashes, app_name="sysone-v2-bram", mac_input_registers=1,
                    exp_table_in_bram=0, clock_requested_hz=125000000, clock_timing_max_hz=125000000)
    (package / "build.json").write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="Missing BRAM profile"):
        app.main()
    assert not calls
    assert not target.exists()


@pytest.mark.parametrize('updates', [
    {'probability_input_capture': 0}, {'local_embed_controls': 0},
    {'capability_word': '0x535907ff'}, {'capability_word': '0x535917ff'},
    {'candidate': 'pipeline-cuts-large'}, {'activation_read_latency': 4},
    {'routed_hold_slack_ns': 0}, {'timing_qualified': False},
])
def test_operand_partial_manifest_never_installs_or_unloads(board, updates):
    from scripts.v2.kr260.package_app import frontier_profile
    _, _, package, target, calls = board
    manifest = json.loads((package / 'build.json').read_text())
    app_name = 'sysone-v2-operand-capture'
    hashes = {}
    for name, digest in manifest['files_sha256'].items():
        renamed = name.replace('sysone-v2.', app_name + '.')
        (package / name).rename(package / renamed)
        hashes[renamed] = digest
    manifest.update(frontier_profile('operand-capture-large'))
    manifest.update(app_name=app_name, files_sha256=hashes,
                    candidate='operand-capture-large', activation_read_latency=5,
                    registered_requests=1, capability_word='0x53591fff',
                    clock_requested_hz=200000000, clock_timing_max_hz=200000000,
                    timing_qualified=True, routed_setup_slack_ns=.8, routed_hold_slack_ns=.02)
    manifest.update(updates)
    (package / 'build.json').write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match='profile|mismatch|timing evidence'):
        app.main()
    assert not calls and not target.exists()

@pytest.mark.parametrize('updates', [
    {'incremental_source_row': 0}, {'linear_accumulators_in_bram': 0}, {'capability_word': '0x53595fff'}, {'capability_word': '0x53596fff'}, {'probability_input_capture': 0}, {'local_embed_controls': 0},
    {'capability_word': '0x535907ff'}, {'capability_word': '0x535917ff'},
    {'candidate': 'pipeline-cuts-large'}, {'activation_read_latency': 4},
    {'routed_hold_slack_ns': 0}, {'timing_qualified': False},
])
def test_source_row_partial_manifest_never_installs_or_unloads(board, updates):
    from scripts.v2.kr260.package_app import frontier_profile
    _, _, package, target, calls = board
    manifest = json.loads((package / 'build.json').read_text())
    app_name = 'sysone-v2-source-row-bram'
    hashes = {}
    for name, digest in manifest['files_sha256'].items():
        renamed = name.replace('sysone-v2.', app_name + '.')
        (package / name).rename(package / renamed)
        hashes[renamed] = digest
    manifest.update(frontier_profile('source-row-bram-large'))
    manifest.update(app_name=app_name, files_sha256=hashes,
                    candidate='source-row-bram-large', activation_read_latency=5,
                    registered_requests=1, capability_word='0x53597fff',
                    clock_requested_hz=200000000, clock_timing_max_hz=200000000,
                    timing_qualified=True, routed_setup_slack_ns=.8, routed_hold_slack_ns=.02)
    manifest.update(updates)
    (package / 'build.json').write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match='profile|mismatch|timing evidence'):
        app.main()
    assert not calls and not target.exists()


@pytest.mark.parametrize('updates', [
    {'attention_lanes':32}, {'fabric_score_distance':0},
    {'capability_word':'0x535a7fff'}, {'capability_word':'0x535abfff'},
    {'capability_word':'0x53597fff'}, {'query_group_cases':0},
    {'encoder_cycle_change_vs_32query_range_percent':None},
    {'routed_hold_slack_ns':0}, {'nexys_default_cycles_unchanged':False},
])
def test_attention_distance_partial_manifest_never_installs_or_unloads(board, updates):
    from scripts.v2.kr260.package_app import frontier_profile
    _,_,package,target,calls=board
    manifest=json.loads((package/'build.json').read_text())
    app_name='sysone-v2-attention16-distance'
    hashes={}
    for name,digest in manifest['files_sha256'].items():
        renamed=name.replace('sysone-v2.',app_name+'.')
        (package/name).rename(package/renamed)
        hashes[renamed]=digest
    manifest.update(frontier_profile('attention16-distance-large'))
    manifest.update(app_name=app_name,files_sha256=hashes,candidate='attention16-distance-large',
                    activation_read_latency=5,registered_requests=1,capability_word='0x535affff',
                    clock_requested_hz=200000000,clock_timing_max_hz=200000000,
                    timing_qualified=True,routed_setup_slack_ns=.8,routed_hold_slack_ns=.02,
                    numerical_cases=32,query_group_cases=4,partial_tile_cases=6,
                    nexys_default_cycles_unchanged=True,
                    encoder_cycle_change_vs_32query_range_percent=[0.0,5.320035251540278])
    manifest.update(updates)
    (package/'build.json').write_text(json.dumps(manifest))
    with pytest.raises(SystemExit,match='profile|mismatch|timing evidence'):
        app.main()
    assert not calls and not target.exists()


@pytest.mark.parametrize('updates',[
    {'cached_request_window':0},{'dsp_embed_row_address':0},{'capability_word':'0x5361ffff'},
    {'capability_word':'0x5362ffff'},{'capability_word':'0x535affff'},{'rtl_sha256':{}},
    {'clock_requested_hz':125000000,'clock_timing_max_hz':125000000},
])
def test_paired_partial_manifest_never_installs_or_unloads(board,updates):
    from scripts.v2.kr260.package_app import frontier_profile
    _,_,package,target,calls=board
    manifest=json.loads((package/'build.json').read_text());app_name='sysone-v2-request-window-embed';hashes={}
    for name,digest in manifest['files_sha256'].items():
        renamed=name.replace('sysone-v2.',app_name+'.');(package/name).rename(package/renamed);hashes[renamed]=digest
    manifest.update(frontier_profile('request-window-embed-large'))
    manifest.update(app_name=app_name,files_sha256=hashes,candidate='request-window-embed-large',
                    activation_read_latency=5,registered_requests=1,capability_word='0x5363ffff',
                    clock_requested_hz=200000000,clock_timing_max_hz=200000000,
                    timing_qualified=True,routed_setup_slack_ns=.8,routed_hold_slack_ns=.02,
                    numerical_cases=32,query_group_cases=4,partial_tile_cases=6,
                    nexys_default_cycles_unchanged=True,
                    encoder_cycle_change_vs_32query_range_percent=[0.0,5.320035251540278],
                    rtl_sha256={f'rtl/v2/source{i}.sv':'0'*64 for i in range(23)})
    manifest.update(updates);(package/'build.json').write_text(json.dumps(manifest))
    with pytest.raises(SystemExit,match='profile|mismatch|timing evidence'):app.main()
    assert not calls and not target.exists()


@pytest.mark.parametrize('word',[0x5373ffff,0x5375ffff,0x5376ffff,0x5363ffff])
def test_context_install_rejects_stale_live_word(board,monkeypatch,word):
    test_pipeline_install_preserves_baseline_and_checks_live_clock(board,monkeypatch,'sysone-v2-attention-context-capture',word)


@pytest.mark.parametrize('updates',[
    {'fabric_context_capture':0},{'cached_request_window':0},{'dsp_embed_row_address':0},{'capability_word':'0x5373ffff'},
    {'capability_word':'0x5375ffff'},{'capability_word':'0x535affff'},{'rtl_sha256':{}},
    {'clock_requested_hz':125000000,'clock_timing_max_hz':125000000},
])
def test_context_partial_manifest_never_installs_or_unloads(board,updates):
    from scripts.v2.kr260.package_app import frontier_profile
    _,_,package,target,calls=board
    manifest=json.loads((package/'build.json').read_text());app_name='sysone-v2-attention-context-capture';hashes={}
    for name,digest in manifest['files_sha256'].items():
        renamed=name.replace('sysone-v2.',app_name+'.');(package/name).rename(package/renamed);hashes[renamed]=digest
    manifest.update(frontier_profile('attention-context-capture-large'))
    manifest.update(app_name=app_name,files_sha256=hashes,candidate='attention-context-capture-large',
                    activation_read_latency=5,registered_requests=1,capability_word='0x5377ffff',
                    clock_requested_hz=200000000,clock_timing_max_hz=200000000,
                    timing_qualified=True,routed_setup_slack_ns=.8,routed_hold_slack_ns=.02,
                    numerical_cases=32,query_group_cases=4,partial_tile_cases=6,
                    nexys_default_cycles_unchanged=True,
                    encoder_cycle_change_vs_32query_range_percent=[0.0,5.320035251540278],
                    rtl_sha256={f'rtl/v2/source{i}.sv':'0'*64 for i in range(23)})
    manifest.update(updates);(package/'build.json').write_text(json.dumps(manifest))
    with pytest.raises(SystemExit,match='profile|mismatch|timing evidence'):app.main()
    assert not calls and not target.exists()
