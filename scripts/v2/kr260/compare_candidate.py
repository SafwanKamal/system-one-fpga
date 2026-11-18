"""Compare two fully verified KR260 runs on the same frozen model and suite."""
import argparse
import json
from pathlib import Path

import numpy as np


def compare(baseline, candidate):
    for report in (baseline, candidate):
        rows = report['cases']
        if (report.get('complete') is not True or report.get('backend') != 'kr260'
                or not rows or len({r['id'] for r in rows}) != len(rows)
                or report.get('verification') != {'exact': len(rows), 'total': len(rows)}
                or any(r.get('bit_exact') is not True for r in rows)):
            raise ValueError('Every unique case must complete and pass the integer reference')
        if not report.get('clock_hz') or report['clock_hz'] <= 0:
            raise ValueError('Positive live clock required')
        for row in rows:
            if not 0 < row['encoder_clocks'] <= row['request_clocks'] < 2**32:
                raise ValueError('Invalid board timing counters')
    for key in ('image_sha256', 'suite_sha256'):
        if not baseline.get(key) or baseline[key] != candidate.get(key):
            raise ValueError(f'Different or unfrozen {key}')
    left, right = ({r['id']: r for r in report['cases']}
                   for report in (baseline, candidate))
    if left.keys() != right.keys() or baseline['stats'] != candidate['stats']:
        raise ValueError('Cases or accuracy counts differ')
    for identifier, row in left.items():
        for field in ('dataset', 'tokens', 'ids_sha256', 'hidden_sha256', 'predictions'):
            if row[field] != right[identifier][field]:
                raise ValueError(f'Numerical disagreement at {identifier}: {field}')
    summaries = {}
    for label, report in (('baseline', baseline), ('candidate', candidate)):
        encoder = np.array([r['encoder_clocks'] for r in report['cases']]) * 1000 / report['clock_hz']
        request = np.array([r['request_clocks'] for r in report['cases']]) * 1000 / report['clock_hz']
        summaries[label] = {'clock_hz': report['clock_hz'],
                            'encoder_mean_ms': float(encoder.mean()),
                            'encoder_p95_ms': float(np.percentile(encoder, 95)),
                            'encoder_max_ms': float(encoder.max()),
                            'request_mean_ms': float(request.mean()),
                            'request_max_ms': float(request.max())}
    return {'cases': len(left), 'image_sha256': baseline['image_sha256'],
            'suite_sha256': baseline['suite_sha256'],
            'outputs_predictions_and_accuracy_identical': True, **summaries,
            'observed_encoder_speedup': summaries['baseline']['encoder_mean_ms'] /
                                        summaries['candidate']['encoder_mean_ms'],
            'hard_timing_guarantee': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = compare(*(json.loads(p.read_text()) for p in (args.baseline, args.candidate)))
    text = json.dumps(result, indent=2) + '\n'
    args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
