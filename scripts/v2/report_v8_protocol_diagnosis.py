"""Summarize preserved v1 traces without rewriting their scores or state."""
import json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from sysone.v2.v8_benchmark_protocol_v2 import parse_enum_record


def main():
    out=ROOT/'build/v2/v8-diagnosis-v1'
    rows=[json.loads(l) for l in (out/'board/requests.jsonl').read_text().splitlines()]
    cpu=json.loads((out/'cpu-results.json').read_text())
    matches=[]
    for case in cpu:
        if not case['id'].startswith('original-'):continue
        _,context,wire=case['id'].split('-')
        row=next(r for r in rows if r['id']==f'development-00-{context}-{wire}-step-01')
        text=case['stdout'].replace('\r\n','\n').strip().removesuffix(' [end of text]')
        matches.append(dict(context=context,wire=wire,cpu_text=text,fpga_text=row['generated_text'],
                            text_equal=text==row['generated_text']))
    eos=[]
    for row in rows:
        if row['wire']!='E':continue
        parsed=None
        try:parsed=parse_enum_record(row['generated_text'],terminal=bool(row['eos_positions']))
        except ValueError:pass
        eos.append(dict(id=row['id'],valid=parsed is not None,
                        matches_expected=list(parsed)==row['expected'] if parsed else False))
    report=dict(recorded_requests=len(rows),suite_counts=dict(Counter(r['suite'] for r in rows)),
        original_format_valid=sum(r['format_valid'] for r in rows),
        enum_eos_diagnostic=dict(total=len(eos),valid=sum(x['valid'] for x in eos),
                                  matches_expected=sum(x['matches_expected'] for x in eos)),
        first_step_cpu_fpga_comparisons=matches,
        cpu_controls=[dict(id=c['id'],stdout=c['stdout']) for c in cpu if not c['id'].startswith('original-')],
        conclusions=['v1 newline-only enum framing rejects complete EOS-terminated records',
            'JSON arm often outputs field-labeled prose rather than arrays',
            'Enum responses often repeat the example value 12',
            'All six first-step outputs reproduced in pinned Q8 CPU generation',
            'EOS repair does not restore arithmetic/reference correctness',
            'Post-hoc parsing cannot repair the recorded rolling chain state'],
        limitations=['CPU arithmetic differs from v8 activation quantization; this is not full numerical parity',
            'Further FPGA diagnostic controls were not run: an upload preparation failed before inference',
            'No held-out quality or throughput results were produced'],
        sweep_disposition='Interrupted after freezing benchmark processes and confirming FPGA idle; no automatic restart')
    (out/'diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('recorded_requests','original_format_valid','enum_eos_diagnostic')},indent=2))
    print('CPU first-step text matches:',sum(x['text_equal'] for x in matches),'/',len(matches))


if __name__=='__main__':main()
