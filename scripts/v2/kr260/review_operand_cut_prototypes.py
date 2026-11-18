"""Record isolated inference and admit completed experimental regressions.

This does not freeze a production candidate or authorize routing/deployment.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ooc(name, source_paths):
    folder = ROOT / 'build/v2' / name
    results = [json.loads((folder / f'result-{i}.json').read_text()) for i in (0, 1)]
    resources = []
    for i in (0, 1):
        report = (folder / f'utilization-{i}.rpt').read_text()
        row = {}
        for label in ('CLB LUTs*', 'CLB Registers', 'Block RAM Tile', 'DSPs'):
            match = re.search(r'\|\s*' + re.escape(label) + r'\s*\|\s*([\d.]+)', report)
            assert match, label
            row[label] = float(match[1])
        row['dsp_registers'] = (folder / f'dsp-{i}.txt').read_text().splitlines()
        resources.append(row)
    if name == 'probability-input-ooc':
        assert len(resources[0]['dsp_registers']) == len(resources[1]['dsp_registers']) == 32
        assert all('AREG=0 BREG=1 MREG=0 PREG=1' in line for line in resources[0]['dsp_registers'])
        assert all('AREG=1 BREG=2 MREG=0 PREG=1' in line for line in resources[1]['dsp_registers'])
        assert {k: v for k, v in resources[0].items() if k != 'dsp_registers'} == {k: v for k, v in resources[1].items() if k != 'dsp_registers'}
    evidence = {
        'updated_utc': datetime.now(timezone.utc).isoformat(),
        'complete': True,
        'target_period_ns': 3.333333,
        'results': results,
        'resources': resources,
        'estimated_slack_gain_ns': round(results[1]['estimated_setup_slack_ns'] - results[0]['estimated_setup_slack_ns'], 3),
        'source_sha256': {p: sha(ROOT / p) for p in source_paths},
        'report_sha256': {p.name: sha(p) for p in folder.glob('*.rpt')},
        'limitations': ['isolated synthesis estimates; no placement or route',
                        'experimental implementation; no production capability admission',
                        'no hardware qualification'],
    }
    (folder / 'summary.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


def review_regression(name):
    folder = ROOT / 'build/v2' / name
    completion = folder / 'completion-status.json'
    if not completion.exists():
        return {'state': 'running', 'directory': name}
    assert json.loads(completion.read_text()) == {'exit_code': 0, 'complete': True}
    tested_hashes = {name: digest for digest, name in
                    (line.split(maxsplit=1) for line in (folder / 'source-sha256.txt').read_text().splitlines())}
    sources = {
        'rtl/v2/encoder/attention_engine.sv': 'build/v2/probability-input-cut/engine-sources/attention_engine.sv',
        'rtl/v2/common/attention_probability_input.sv': 'build/v2/probability-input-cut/engine-sources/attention_probability_input.sv',
    }
    if name == 'rtl-input-embed-check':
        sources['rtl/v2/encoder/embed_engine.sv'] = 'build/v2/embed-controls/engine-sources/embed_engine.sv'
    for tested, source in sources.items():
        assert tested_hashes[tested] == sha(ROOT / source), f'Prototype changed under test: {source}'
    baseline = ROOT / 'build/v2/rtl-pipeline-cuts-check'
    pattern = r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)'
    counts = {'wide': 8, 'l12': 8, 'one-word': 5, 'boundary': 3, 'h1024': 8}
    checks = {}
    for profile, count in counts.items():
        log = folder / f'{profile}.log'
        actual = re.findall(pattern, log.read_text())
        expected = re.findall(pattern, (baseline / log.name).read_text())
        assert len(actual) == count and actual == expected, profile
        assert all(row[2] == '0' and row[4] == '0' for row in actual)
        checks[profile] = {'cases': count, 'exact_outputs_and_cycles': True,
                           'log_sha256': sha(log)}
    default_pattern = r'case (\d+):\s+(\d+) tokens, (\d+) mismatching words; clocks per instruction ([0-9 ]+); whole layer (\d+)'
    log = folder / 'nexys-default.log'
    actual = re.findall(default_pattern, log.read_text())
    assert len(actual) == 2 and actual == re.findall(default_pattern, (baseline / log.name).read_text())
    evidence = {'state': 'experimental_numerical_ready', 'numerical_cases': 32,
                'checks': checks, 'nexys_default_cases': 2,
                'nexys_default_outputs_and_cycles_unchanged': True,
                'snapshot_manifest_sha256': sha(folder / 'source-sha256.txt'),
                'production_capability_admitted': False, 'hardware_qualified': False}
    (folder / 'review.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


def review_partial():
    folder = ROOT / 'build/v2/probability-input-partial-check'
    assert json.loads((folder / 'completion-status.json').read_text()) == {'complete': True, 'exit_code': 0}
    pattern = r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)'
    baseline = re.findall(pattern, (folder / 'baseline.log').read_text())
    grouped = re.findall(pattern, (folder / 'grouped.log').read_text())
    assert len(grouped) == 6 and grouped == baseline
    assert all(row[2] == '0' and row[4] == '0' for row in grouped)
    assert '6 cases, 516 words compared' in (folder / 'grouped.log').read_text()
    evidence = {'complete': True, 'cases': 6, 'words': 516,
                'hidden': 48, 'ffn': 80, 'tile_out': 32,
                'outputs_and_cycles_unchanged': True,
                'log_sha256': {p.name: sha(p) for p in folder.glob('*.log')},
                'binary_inventory_sha256': {p.name: sha(p) for p in folder.glob('*.sha256')}}
    (folder / 'summary.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence


if __name__ == '__main__':
    for name, paths in (
        ('probability-input-ooc', ['scripts/v2/kr260/check_probability_input_ooc.tcl',
          'build/v2/probability-input-ooc/probability_bram_ooc.sv',
          'rtl/v2/common/attention_probability.sv',
          'build/v2/probability-input-cut/engine-sources/attention_probability_input.sv']),
        ('embed-controls-ooc', ['scripts/v2/kr260/check_embed_controls_ooc.tcl',
          'build/v2/embed-controls-ooc/embed_ooc.sv',
          'build/v2/embed-controls-ooc/embed_original.sv',
          'build/v2/embed-controls/engine-sources/embed_engine.sv']),
    ):
        result = ooc(name, paths)
        print(name, 'isolated slack gain', result['estimated_slack_gain_ns'])
    for name in ('rtl-probability-input-check', 'rtl-input-embed-check'):
        result = review_regression(name)
        print(name, result['state'])
    print('probability-input partial tiles:', review_partial()['cases'], 'exact cases')
