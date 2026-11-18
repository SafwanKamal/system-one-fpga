"""Gate and freeze the optional activation capture before full synthesis."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    flags = '--flags' in sys.argv
    tested = ROOT / ('build/v2/rtl-capture-flags-check' if flags else 'build/v2/rtl-capture-check')
    assert json.loads((tested / 'completion-status.json').read_text()) == {'exit_code': 0, 'complete': True}
    expected = {
        'wide': ('build/v2/rtl-wide-check/vectors', [1, 2, 3, 4, 5, 12, 64, 128]),
        'l12': ('simulation/v2/vectors/kr260', [1, 2, 3, 4, 5, 12, 64, 128]),
        'one-word': ('build/v2/rtl-batch3-check/one-word-vectors', [1, 2, 3, 31, 33]),
        'boundary': ('build/v2/rtl-batch-check/boundary-vectors', [1, 2, 3]),
        'h1024': ('build/v2/kr260-dot7-h1024-eight-vectors', [1, 2, 3, 4, 5, 12, 64, 128]),
    }
    checks = {}
    for name, (directory, lengths) in expected.items():
        path = tested / f'{name}.log'
        log = path.read_text()
        rows = re.findall(r'case (\d+):\s+(\d+) tokens, status (\d+), stopped at (\d+), (\d+) mismatching words; clocks: encoder (\d+), request (\d+)', log)
        assert [int(r[0]) for r in rows] == list(range(len(lengths))), name
        assert [int(r[1]) for r in rows] == lengths, name
        assert all(int(r[2]) == 0 and int(r[4]) == 0 and 0 < int(r[5]) <= int(r[6]) for r in rows), name
        assert ('FEATURES 535901ff' if flags else 'FEATURES 5359017f') in log and 'BUILD register 20804004' in log, name
        vectors = ROOT / directory
        words = 0
        for i, n in enumerate(lengths):
            dimensions = (vectors / f'case_{i}.txt').read_text().splitlines()[0].split()
            assert int(dimensions[0]) == n
            words += (n * int(dimensions[1]) + 15) // 16
        assert f'PASS: KR260 block bit-exact, {len(lengths)} cases, {words} words compared' in log, name
        counters = re.findall(r'profile case (\d+) counter (\d+) = (\d+)', log)
        assert len(counters) == len(lengths)*10 and len({(c, p) for c, p, v in counters}) == len(counters), name
        checks[name] = {'log_sha256': sha(path), 'tokens': lengths, 'words': words,
                        'encoder_clocks': [int(r[5]) for r in rows],
                        'request_clocks': [int(r[6]) for r in rows],
                        'vectors_sha256': {p.name: sha(p) for p in vectors.iterdir() if p.is_file()}}
    assert 'PASS: encoder layer bit-exact, 2 cases, 39216 words compared' in (tested/'nexys-default.log').read_text()
    assert 'PASS: result streamer 96 chunks, latency 3/4/5, prolonged/random backpressure' in (ROOT/'build/v2/result-streamer-capture/result.log').read_text()
    assert 'PASS: seven memories, 240000 reference comparisons' in (ROOT/'build/v2/activation-capture-memory/result.log').read_text()
    ooc_dir = ROOT / 'build/v2/activation-capture-ooc'
    assert json.loads((ooc_dir/'completion-status.json').read_text())['state'] == 'complete'
    ooc = json.loads((ooc_dir/'result.json').read_text())
    assert [r['capture'] for r in ooc] == [0, 1]
    assert all(r['uram'] == 36 for r in ooc) and ooc[1]['local_capture_ff'] == 896
    sources = list(json.loads((ROOT/'build/v2/kr260-opt-dot7-large/regression.json').read_text())['rtl_sha256'])
    sources.append('rtl/v2/common/activation_read_capture.sv')
    if flags:
        sources.append('rtl/v2/common/sync_fifo_registered_flags.sv')
        probe=ROOT/'build/v2/axi-length-flags-probe'
        assert json.loads((probe/'completion-status.json').read_text())['state']=='complete'
        proof=json.loads((probe/'result.json').read_text())
        assert [r['pointer_to_request_ready_paths'] for r in proof]==[1,0]
        assert sha(ROOT/'rtl/v2/common/sync_fifo_registered_flags.sv')==sha(probe/'sources/sync_fifo_registered_flags.sv')
        assert 'PASS: registered FIFO flags depth4/8/64, 300153 comparisons' in (ROOT/'build/v2/sync-fifo-flags/result.log').read_text()
        assert json.loads((ROOT/'build/v2/relative-retire-axi-flags/summary.json').read_text())['scenarios']==26
    digests = dict((name, digest) for digest, name in (line.split(maxsplit=1) for line in (tested/'source-sha256.txt').read_text().splitlines()))
    for name in sources:
        assert sha(ROOT/name) == digests[name], f'Untested source edit: {name}'
    for name in ('encoder/activation_buffer.sv', 'common/activation_read_capture.sv'):
        assert sha(ROOT/'rtl/v2'/name) == sha(ooc_dir/'rtl-snapshot'/Path(name).name)
    output = ROOT / ('build/v2/kr260-opt-capture-flags-large' if flags else 'build/v2/kr260-opt-capture-large')
    if output.exists():
        raise ValueError('Preserve existing candidate rather than overwrite')
    for name in sources:
        target = output/'rtl-snapshot'/Path(name).relative_to('rtl/v2')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    evidence = {'candidate': 'capture-flags-large' if flags else 'capture-large', 'target_mhz': 200, 'read_latency': 5,
                'profile': {'max_hidden': 1024, 'mac_input_registers': 1, 'exp_table_in_bram': 1,
                            'local_read_capture': 1, 'local_accumulator_controls': 3,
                            'pipelined_uram': 1, 'pipelined_dot': 1, 'stream_results': 1,
                            'local_query_registers': 1, 'perf_counters': 1},
                'checks': checks, 'numerical_cases': sum(len(v[1]) for v in expected.values()),
                'rtl_sha256': {name: digests[name] for name in sources},
                'focused_ooc': ooc, 'hardware_qualified': False, 'routed': False}
    if flags:
        evidence['profile']['registered_fifo_flags']=1
        previous=json.loads((ROOT/'build/v2/kr260-opt-capture-large/regression.json').read_text())
        assert all(evidence['checks'][k]['encoder_clocks']==previous['checks'][k]['encoder_clocks'] for k in evidence['checks']), 'FIFO flags unexpectedly changed encoder cycles'
        evidence['encoder_cycles_unchanged_vs_capture']=True
    (output/'regression.json').write_text(json.dumps(evidence, indent=2)+'\n')
    (output/'completion-status.json').write_text(json.dumps({'state': 'numerical_ready', 'updated_utc': datetime.now(timezone.utc).isoformat()}, indent=2)+'\n')
    print('PASS: 32 KR260 cases, Nexys defaults, latency5 streaming and memory tests; RTL sources frozen')


if __name__ == '__main__':
    main()
