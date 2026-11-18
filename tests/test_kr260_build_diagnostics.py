"""Build diagnostics must not mistake a completed bitstream for timing closure."""
import json
import pytest

from scripts.v2.kr260.analyze_build import analyze


def test_partial_log_does_not_report_completion_or_routing_time(tmp_path):
    result = analyze(tmp_path)
    assert not result["bitstream_completed"]
    assert result["critical_setup_path"] is None
    assert "route_design" not in result["stages"]
    assert result["route_share_of_reported_stages"] is None

def test_failed_placement_runtime_does_not_imply_success(tmp_path):
    run=tmp_path/'sysone_v2_kr260.runs/impl_1'
    run.mkdir(parents=True)
    (run/'runme.log').write_text('place_design failed\nplace_design: Time (s): cpu = 00:37:20 ; elapsed = 00:29:03\n')
    result=analyze(tmp_path)
    assert result['implementation_failed']
    assert result['stage_outcomes']['place_design']=='failed'
    assert result['stages']['place_design']['wall_seconds']==1743
    assert not result['bitstream_completed']


@pytest.mark.parametrize("spacing", [" ", "  "])
def test_timing_failure_is_preserved_after_bitstream_completion(tmp_path, spacing):
    run = tmp_path / "sysone_v2_kr260.runs/impl_1"
    run.mkdir(parents=True)
    (run / "runme.log").write_text(
        "place_design: Time (s): cpu = 00:42:08 ; elapsed = 00:20:49\n"
        "route_design: Time (s): cpu = 12:12:27 ; elapsed = 05:10:48 . Memory (MB): peak = 6998.539\n"
        "Estimated Global/Short routing congestion is level 6\nBitgen Completed Successfully\n")
    (tmp_path / "timing.rpt").write_text(
        "Slack (VIOLATED) : -4.477ns\nSource: word_reg/C\nDestination: query_reg/CE\n"
        f"Data Path Delay: 12.841ns{spacing}(logic 0.578ns (4.501%){spacing}route 12.263ns (95.499%))\n")
    (tmp_path / "utilization.rpt").write_text("| CLB LUTs* | 93,725 | 0 |\n")
    result = analyze(tmp_path)
    assert result["bitstream_completed"]
    assert result["stages"]["route_design"]["wall_seconds"] == 18648
    assert result["critical_setup_path"]["slack_ns"] == -4.477
    assert result["critical_setup_path"]["route_percent"] == 95.499
    assert result["max_congestion_level"] == 6
    assert result["resources"]["CLB LUTs"] == 93725
    assert json.loads((tmp_path / "build-diagnostics.json").read_text()) == result
