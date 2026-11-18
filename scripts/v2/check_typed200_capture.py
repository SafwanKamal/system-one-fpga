"""Check captured bytes offline; never reads/writes live target memory."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from sysone.v2.typed200_capture import ExpectedCapture, assess_capture


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--expected', type=Path, required=True)
    ap.add_argument('--shared', type=Path, required=True)
    ap.add_argument('--pl', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    # Read each input once: hashes refer to exactly the bytes assessed.
    paths = {'expected': args.expected, 'shared': args.shared}
    if args.pl is not None:
        paths['pl'] = args.pl
    raw = {k: p.read_bytes() for k, p in paths.items()}
    fields = json.loads(raw['expected'])
    fields['token_ids'] = tuple(fields['token_ids'])
    expected = ExpectedCapture(**fields)
    report = assess_capture(raw['shared'], expected, raw.get('pl'))
    report['input_sha256'] = {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print('PASS offline typed200 record consistency; no target/WCET certification')


if __name__ == '__main__':
    main()
