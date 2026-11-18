"""Linux state must be confirmed without touching absent PL registers."""
import json
import struct

import pytest

from sysone.v2 import kr260_runtime as runtime


@pytest.fixture
def boot(tmp_path, monkeypatch):
    dt = tmp_path / "sys/firmware/devicetree/base"
    files = {
        "sys/firmware/devicetree/base/model": b"ZynqMP KR260 revB\0",
        "sys/firmware/devicetree/base/__symbols__/amba": b"/axi\0",
        "sys/firmware/devicetree/base/axi/encoder@a0000000/compatible": b"xlnx,kr260-encoder-wrapper-1.0\0",
        "sys/firmware/devicetree/base/axi/encoder@a0000000/reg": struct.pack(">IIII", 0, 0xa0000000, 0, 4096),
        "sys/firmware/devicetree/base/fpga-region/firmware-name": b"sysone-v2.bit.bin\0",
        "sys/class/fpga_manager/fpga0/state": b"operating\n",
        "sys/kernel/debug/clk/clk_summary": b"pl0_ref 1 1 0 71428571\n",
        "sys/firmware/devicetree/base/reserved-memory/sysone@60000000/no-map": b"",
        "sys/firmware/devicetree/base/reserved-memory/sysone@60000000/reg": struct.pack(">IIII", 0, 0x60000000, 0, 64 << 20),
        "proc/iomem": b"60000000-63ffffff : reserved\n",
        "lib/firmware/xilinx/sysone-v2/build.json": json.dumps({
            "clock_requested_hz": 75000000, "clock_timing_max_hz": 80000000}).encode(),
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    monkeypatch.setattr(runtime, "_bound", lambda *args: True)
    return tmp_path, dt


def test_valid_runtime_reports_actual_clock(boot):
    root, _ = boot
    assert runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)["clock_hz"] == 71428571


def test_starter_app_after_reboot_refused_without_mmio(boot):
    root, dt = boot
    (dt / "axi/encoder@a0000000/reg").unlink()
    (dt / "axi/encoder@a0000000/compatible").unlink()
    (dt / "axi/encoder@a0000000").rmdir()
    with pytest.raises(IOError, match="overlay is absent"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


@pytest.mark.parametrize("clock,reason", [
    ("pl0_ref 0 0 0 71428571\n", "enabled/prepared"),
    ("pl0_ref 1 1 0 100000000\n", "validated range"),
])
def test_disabled_or_overspeed_clock_refused(boot, clock, reason):
    root, _ = boot
    (root / "sys/kernel/debug/clk/clk_summary").write_text(clock)
    with pytest.raises(IOError, match=reason):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def test_unbound_afi_refused(boot, monkeypatch):
    root, _ = boot
    monkeypatch.setattr(runtime, "_bound", lambda node, driver, root: driver != "afi-fpga")
    with pytest.raises(IOError, match="AXI port"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def test_missing_boot_reservation_refused(boot):
    root, dt = boot
    (dt / "reserved-memory/sysone@60000000/no-map").unlink()
    with pytest.raises(IOError, match="no-map"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def pipeline_profile(root, dt, firmware_app="sysone-v2-pipe", **updates):
    (dt / "fpga-region/firmware-name").write_bytes(f"{firmware_app}.bit.bin\0".encode())
    profile = dict(app_name=firmware_app, mac_input_registers=1,
                   exp_table_in_bram=int(firmware_app in {"sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory"}),
                   max_hidden=768 if firmware_app in {"sysone-v2-wide", "sysone-v2-memory"} else 384,
                   pipelined_uram=int(firmware_app == "sysone-v2-memory"),
                   activation_read_latency=4 if firmware_app == "sysone-v2-memory" else 3,
                   clock_requested_hz=125000000, clock_timing_max_hz=125000000)
    profile.update(updates)
    path = root / f"lib/firmware/xilinx/{firmware_app}/build.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile))
    (root / "sys/kernel/debug/clk/clk_summary").write_text("pl0_ref 1 1 0 124999999\n")


@pytest.mark.parametrize("firmware_app", ["sysone-v2-pipe", "sysone-v2-bram", "sysone-v2-wide", "sysone-v2-memory"])
def test_pipeline_uses_its_own_validated_profile(boot, firmware_app):
    root, dt = boot
    pipeline_profile(root, dt, firmware_app)
    assert runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)["clock_hz"] == 124999999


@pytest.mark.parametrize("updates,reason", [
    ({"app_name": "sysone-v2"}, "manifest does not match"),
    ({"mac_input_registers": 0}, "missing pipeline"),
    ({"clock_timing_max_hz": 126000000}, "invalid app clock profile"),
    ({"clock_requested_hz": 100000000, "clock_timing_max_hz": 100000000}, "validated range"),
])
def test_pipeline_refuses_mismatched_or_unsafe_profile(boot, updates, reason):
    root, dt = boot
    pipeline_profile(root, dt, **updates)
    with pytest.raises(IOError, match=reason):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def test_bram_firmware_requires_its_memory_profile(boot):
    root, dt = boot
    pipeline_profile(root, dt, "sysone-v2-bram", exp_table_in_bram=0)
    with pytest.raises(IOError, match="missing BRAM app profile"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def test_expanded_reservation_is_discovered_and_old_subregion_still_works(boot):
    root, dt = boot
    (dt / "reserved-memory/sysone@60000000/reg").write_bytes(struct.pack(">QQ",0x60000000,256 << 20))
    (root / "proc/iomem").write_text("60000000-6fffffff : reserved\n")
    assert runtime.discover_memory(root) == (0x60000000,256 << 20)
    for size in (64 << 20,256 << 20):
        assert runtime.check_runtime(0xa0000000,(0x60000000,size),root)["memory_bytes"] == 256 << 20
    with pytest.raises(IOError, match="exceeds"):
        runtime.check_runtime(0xa0000000,(0x60000000,257 << 20),root)


def test_discovery_refuses_unmapped_high_ddr(boot):
    root, dt = boot
    node = dt / "reserved-memory/sysone@60000000"
    (node / "reg").write_bytes(struct.pack(">QQ",0x800000000,256 << 20))
    node.rename(node.parent / "sysone@800000000")
    with pytest.raises(IOError, match="low-DDR"):
        runtime.discover_memory(root)


def test_wide_app_requires_768_profile(boot):
    root,dt = boot
    pipeline_profile(root,dt,"sysone-v2-wide",max_hidden=384)
    with pytest.raises(IOError,match="768-wide"):
        runtime.check_runtime(0xa0000000,(0x60000000,64 << 20),root)


@pytest.mark.parametrize("updates", [{"pipelined_uram": 0}, {"activation_read_latency": 3}])
def test_memory_app_requires_matching_ram_pipeline(boot, updates):
    root, dt = boot
    pipeline_profile(root, dt, "sysone-v2-memory", **updates)
    with pytest.raises(IOError, match="pipelined UltraRAM"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def frontier_profile(root, dt, **updates):
    values = dict(max_hidden=1024, exp_table_in_bram=1, pipelined_uram=1,
                  activation_read_latency=4, stream_results=1, local_query_registers=1,
                  perf_counters=1, local_accumulator_controls=1, pipelined_dot=1,
                  registered_requests=1, timing_qualified=True,
                  routed_setup_slack_ns=0.4, routed_hold_slack_ns=0.01,
                  clock_requested_hz=150000000, clock_timing_max_hz=150000000)
    values.update(updates)
    pipeline_profile(root, dt, "sysone-v2-frontier", **values)
    (root / "sys/kernel/debug/clk/clk_summary").write_text(
        "pl0_ref 1 1 0 142857141\npl1_ref 1 1 0 142857141\n")


def test_frontier_uses_routed_clock_and_h1024_profile(boot):
    root, dt = boot
    frontier_profile(root, dt)
    assert runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)["clock_hz"] == 142857141

def test_dot7_accepts_only_its_shared_read_profile(boot):
    root,dt=boot
    frontier_profile(root,dt,candidate='dot7-large',local_accumulator_controls=3)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['clock_hz']==142857141
    frontier_profile(root,dt,candidate='dot7-large',local_accumulator_controls=1)
    with pytest.raises(IOError,match='H1024 frontier'):
        runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def capture_profile(root, dt, **updates):
    frontier_profile(root, dt, candidate='capture-large', local_accumulator_controls=3,
                     local_read_capture=1, activation_read_latency=5,
                     clock_requested_hz=200000000, clock_timing_max_hz=200000000)
    old = root/'lib/firmware/xilinx/sysone-v2-frontier/build.json'
    values=json.loads(old.read_text())
    values.update(app_name='sysone-v2-capture', **updates)
    new=root/'lib/firmware/xilinx/sysone-v2-capture/build.json'
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text(json.dumps(values))
    (dt/'fpga-region/firmware-name').write_bytes(b'sysone-v2-capture.bit.bin\0')
    (root/'sys/kernel/debug/clk/clk_summary').write_text(
        'pl0_ref 1 1 0 199999998\npl1_ref 1 1 0 199999998\n')


def test_capture_requires_separate_app_and_five_cycle_contract(boot):
    root,dt=boot
    capture_profile(root,dt)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['clock_hz']==199999998


@pytest.mark.parametrize('updates', [
    {'activation_read_latency':4}, {'local_read_capture':0},
    {'local_accumulator_controls':1}, {'candidate':'dot7-large'},
    {'timing_qualified':False}, {'routed_setup_slack_ns':0},
])
def test_capture_refuses_mismatched_contract_before_mmio(boot,updates):
    root,dt=boot
    capture_profile(root,dt,**updates)
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def test_old_frontier_cannot_claim_capture_stage(boot):
    root,dt=boot
    frontier_profile(root,dt,candidate='dot7-large',local_accumulator_controls=3,
                     local_read_capture=1)
    with pytest.raises(IOError,match='H1024 frontier'):
        runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def capture_flags_profile(root, dt, **updates):
    capture_profile(root,dt,candidate='capture-flags-large',registered_fifo_flags=1)
    old=root/'lib/firmware/xilinx/sysone-v2-capture/build.json'
    values=json.loads(old.read_text());values.update(updates)
    values['app_name']='sysone-v2-capture-flags'
    new=root/'lib/firmware/xilinx/sysone-v2-capture-flags/build.json'
    new.parent.mkdir(parents=True,exist_ok=True);new.write_text(json.dumps(values))
    (dt/'fpga-region/firmware-name').write_bytes(b'sysone-v2-capture-flags.bit.bin\0')


def test_grouped_capture_flags_runtime_profile(boot):
    root,dt=boot;capture_flags_profile(root,dt)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['clock_hz']==199999998


@pytest.mark.parametrize('updates', [
    {'registered_fifo_flags':0},{'candidate':'capture-large'},
    {'local_read_capture':0},{'activation_read_latency':4},
])
def test_grouped_flags_refuses_other_pipeline_profiles(boot,updates):
    root,dt=boot;capture_flags_profile(root,dt,**updates)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def test_fifo_flag_cannot_be_claimed_by_older_capture(boot):
    root,dt=boot;capture_profile(root,dt,registered_fifo_flags=1)
    with pytest.raises(IOError,match='H1024 frontier'):
        runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)

@pytest.mark.parametrize('candidate,controls',[(None,3),('dot5-large',3),('unknown',3)])
def test_shared_mode_cannot_be_claimed_by_other_candidates(boot,candidate,controls):
    root,dt=boot
    frontier_profile(root,dt,candidate=candidate,local_accumulator_controls=controls)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)

@pytest.mark.parametrize('hold',[0,float('inf'),float('nan'),True])
def test_frontier_requires_finite_positive_hold(boot,hold):
    root,dt=boot
    frontier_profile(root,dt,routed_hold_slack_ns=hold)
    with pytest.raises(IOError,match='routed timing'):
        runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


@pytest.mark.parametrize("updates,reason", [
    ({"timing_qualified": False}, "routed timing"),
    ({"routed_hold_slack_ns": -0.01}, "routed timing"),
    ({"max_hidden": 768}, "H1024 frontier"),
    ({"registered_requests": 0}, "H1024 frontier"),
])
def test_frontier_rejects_unqualified_profile(boot, updates, reason):
    root, dt = boot
    frontier_profile(root, dt, **updates)
    with pytest.raises(IOError, match=reason):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def test_frontier_refuses_overspeed_second_clock(boot):
    root, dt = boot
    frontier_profile(root, dt)
    (root / "sys/kernel/debug/clk/clk_summary").write_text(
        "pl0_ref 1 1 0 142857141\npl1_ref 1 1 0 166666666\n")
    with pytest.raises(IOError, match="PL1 clock"):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def pipeline_cuts_profile(root,dt,**updates):
    capture_flags_profile(root,dt)
    old=root/'lib/firmware/xilinx/sysone-v2-capture-flags/build.json'
    profile=json.loads(old.read_text())
    profile.update(app_name='sysone-v2-pipeline-cuts',candidate='pipeline-cuts-large',
                   probability_pipeline=1,pipelined_drain_select=1)
    profile.update(updates)
    path=root/'lib/firmware/xilinx/sysone-v2-pipeline-cuts/build.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(profile))
    (dt/'fpga-region/firmware-name').write_bytes(b'sysone-v2-pipeline-cuts.bit.bin\0')


def test_pipeline_cuts_runtime_profile(boot):
    root,dt=boot;pipeline_cuts_profile(root,dt)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['clock_hz']==199999998


@pytest.mark.parametrize('updates',[{'probability_pipeline':0},{'pipelined_drain_select':0},
    {'candidate':'capture-flags-large'},{'registered_fifo_flags':0},{'activation_read_latency':4},
    {'app_name':'sysone-v2-capture-flags'},{'routed_setup_slack_ns':0}])
def test_pipeline_cuts_refuses_stale_or_partial_profiles(boot,updates):
    root,dt=boot;pipeline_cuts_profile(root,dt,**updates)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def test_legacy_flags_cannot_claim_new_probability_stage(boot):
    root,dt=boot;capture_flags_profile(root,dt,probability_pipeline=1)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def operand_profile(root, dt, **updates):
    pipeline_cuts_profile(root, dt)
    old = root / 'lib/firmware/xilinx/sysone-v2-pipeline-cuts/build.json'
    profile = json.loads(old.read_text())
    profile.update(app_name='sysone-v2-operand-capture', candidate='operand-capture-large',
                   probability_input_capture=1, local_embed_controls=1, capability_word='0x53591fff')
    profile.update(updates)
    path = root / 'lib/firmware/xilinx/sysone-v2-operand-capture/build.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile))
    (dt / 'fpga-region/firmware-name').write_bytes(b'sysone-v2-operand-capture.bit.bin\0')


def test_operand_runtime_profile(boot):
    root, dt = boot
    operand_profile(root, dt)
    result = runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)
    assert result['clock_hz'] == 199999998
    assert result['expected_build'] == 0x20804004
    assert result['expected_capabilities'] == 0x53591fff


@pytest.mark.parametrize('updates', [
    {'probability_input_capture': 0}, {'local_embed_controls': 0},
    {'probability_pipeline': 0}, {'pipelined_drain_select': 0},
    {'candidate': 'pipeline-cuts-large'}, {'activation_read_latency': 4},
    {'capability_word': '0x535907ff'}, {'capability_word': '0x535917ff'},
    {'capability_word': '0x53591bff'}, {'capability_word': '0x53590301'},
    {'routed_hold_slack_ns': 0}, {'timing_qualified': False},
])
def test_operand_rejects_stale_partial_or_unqualified_profiles(boot, updates):
    root, dt = boot
    operand_profile(root, dt, **updates)
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


@pytest.mark.parametrize('flag', ['probability_input_capture', 'local_embed_controls'])
def test_older_profile_cannot_claim_operand_options(boot, flag):
    root, dt = boot
    pipeline_cuts_profile(root, dt, **{flag: 1})
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def source_row_profile(root, dt, **updates):
    operand_profile(root, dt)
    old = root / 'lib/firmware/xilinx/sysone-v2-operand-capture/build.json'
    profile = json.loads(old.read_text())
    profile.update(app_name='sysone-v2-source-row-bram', candidate='source-row-bram-large',
                   incremental_source_row=1, linear_accumulators_in_bram=1, capability_word='0x53597fff')
    profile.update(updates)
    path = root / 'lib/firmware/xilinx/sysone-v2-source-row-bram/build.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile))
    (dt / 'fpga-region/firmware-name').write_bytes(b'sysone-v2-source-row-bram.bit.bin\0')


def test_source_row_runtime_exact_profile(boot):
    root, dt = boot
    source_row_profile(root, dt)
    assert runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)['expected_capabilities'] == 0x53597fff


@pytest.mark.parametrize('updates', [
    {'incremental_source_row': 0}, {'linear_accumulators_in_bram': 0},
    {'capability_word': '0x53591fff'}, {'capability_word': '0x53595fff'},
    {'capability_word': '0x53596fff'}, {'candidate': 'operand-capture-large'},
    {'activation_read_latency': 4}, {'routed_hold_slack_ns': 0},
])
def test_source_row_runtime_rejects_partial_or_stale(boot, updates):
    root, dt = boot
    source_row_profile(root, dt, **updates)
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


@pytest.mark.parametrize('flag', ['incremental_source_row', 'linear_accumulators_in_bram'])
def test_operand_profile_cannot_claim_row_bram_options(boot, flag):
    root, dt = boot
    operand_profile(root, dt, **{flag: 1})
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def attention_distance_profile(root, dt, **updates):
    source_row_profile(root, dt)
    profile = json.loads((root / 'lib/firmware/xilinx/sysone-v2-source-row-bram/build.json').read_text())
    profile.update(app_name='sysone-v2-attention16-distance', candidate='attention16-distance-large',
                   capability_word='0x535affff', attention_lanes=16, fabric_score_distance=1,
                   numerical_cases=32, query_group_cases=4, partial_tile_cases=6,
                   nexys_default_cycles_unchanged=True,
                   encoder_cycle_change_vs_32query_range_percent=[0.0, 5.320035251540278])
    profile.update(updates)
    path = root / 'lib/firmware/xilinx/sysone-v2-attention16-distance/build.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile))
    (dt / 'fpga-region/firmware-name').write_bytes(b'sysone-v2-attention16-distance.bit.bin\0')


def test_attention_distance_runtime_exact_profile(boot):
    root, dt = boot
    attention_distance_profile(root, dt)
    assert runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)['expected_capabilities'] == 0x535affff


@pytest.mark.parametrize('updates', [
    {'attention_lanes': 32}, {'fabric_score_distance': 0},
    {'capability_word': '0x535a7fff'}, {'capability_word': '0x535abfff'},
    {'capability_word': '0x53597fff'}, {'candidate': 'source-row-bram-large'},
    {'query_group_cases': 0}, {'partial_tile_cases': 0}, {'numerical_cases': 36},
    {'nexys_default_cycles_unchanged': False},
    {'encoder_cycle_change_vs_32query_range_percent': None},
    {'encoder_cycle_change_vs_32query_range_percent': [0.0, float('nan')]},
    {'encoder_cycle_change_vs_32query_range_percent': [5.0, 0.0]},
    {'routed_hold_slack_ns': 0},
])
def test_attention_distance_refuses_incomplete_or_stale_profile(boot, updates):
    root, dt = boot
    attention_distance_profile(root, dt, **updates)
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


@pytest.mark.parametrize('updates', [{'attention_lanes': 16}, {'fabric_score_distance': 1}])
def test_older_source_row_app_cannot_claim_attention_distance(boot, updates):
    root, dt = boot
    source_row_profile(root, dt, **updates)
    with pytest.raises(IOError):
        runtime.check_runtime(0xa0000000, (0x60000000, 64 << 20), root)


def paired_window_profile(root,dt,**updates):
    attention_distance_profile(root,dt)
    profile=json.loads((root/'lib/firmware/xilinx/sysone-v2-attention16-distance/build.json').read_text())
    profile.update(app_name='sysone-v2-request-window-embed',candidate='request-window-embed-large',
                   capability_word='0x5363ffff',cached_request_window=1,dsp_embed_row_address=1,
                   rtl_sha256={f'rtl/v2/source{i}.sv':'0'*64 for i in range(23)})
    profile.update(updates)
    path=root/'lib/firmware/xilinx/sysone-v2-request-window-embed/build.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(profile))
    (dt/'fpga-region/firmware-name').write_bytes(b'sysone-v2-request-window-embed.bit.bin\0')


def test_paired_runtime_exact_profile(boot):
    root,dt=boot;paired_window_profile(root,dt)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['expected_capabilities']==0x5363ffff


@pytest.mark.parametrize('updates',[
    {'cached_request_window':0},{'dsp_embed_row_address':0},{'capability_word':'0x5361ffff'},
    {'capability_word':'0x5362ffff'},{'capability_word':'0x535affff'},{'rtl_sha256':{}},
    {'attention_lanes':32},{'routed_hold_slack_ns':0},{'query_group_cases':0},
    {'clock_requested_hz':125000000,'clock_timing_max_hz':125000000},
])
def test_paired_runtime_rejects_partial_and_fallback(boot,updates):
    root,dt=boot;paired_window_profile(root,dt,**updates)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


@pytest.mark.parametrize('flag',['cached_request_window','dsp_embed_row_address'])
def test_attention_profile_cannot_claim_paired_options(boot,flag):
    root,dt=boot;attention_distance_profile(root,dt,**{flag:1})
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def context_capture_profile(root,dt,**updates):
    paired_window_profile(root,dt)
    data=json.loads((root/'lib/firmware/xilinx/sysone-v2-request-window-embed/build.json').read_text())
    data.update(app_name='sysone-v2-attention-context-capture',candidate='attention-context-capture-large',capability_word='0x5377ffff',fabric_context_capture=1)
    data.update(updates)
    path=root/'lib/firmware/xilinx/sysone-v2-attention-context-capture/build.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))
    (dt/'fpga-region/firmware-name').write_bytes(b'sysone-v2-attention-context-capture.bit.bin\0')


def test_context_runtime_exact_profile(boot):
    root,dt=boot;context_capture_profile(root,dt)
    assert runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)['expected_capabilities']==0x5377ffff


@pytest.mark.parametrize('updates',[{'fabric_context_capture':0},{'capability_word':'0x5373ffff'},{'capability_word':'0x5375ffff'},{'capability_word':'0x5376ffff'},{'capability_word':'0x5363ffff'},{'rtl_sha256':{}},{'cached_request_window':0},{'dsp_embed_row_address':0},{'clock_requested_hz':125000000,'clock_timing_max_hz':125000000}])
def test_context_runtime_rejects_incomplete_and_stale(boot,updates):
    root,dt=boot;context_capture_profile(root,dt,**updates)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)


def test_paired_app_cannot_claim_fabric_context(boot):
    root,dt=boot;paired_window_profile(root,dt,fabric_context_capture=1)
    with pytest.raises(IOError):runtime.check_runtime(0xa0000000,(0x60000000,64<<20),root)
