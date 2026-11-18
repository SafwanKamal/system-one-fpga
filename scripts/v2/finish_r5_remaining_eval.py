"""Validate the remaining-set journal and export dataset summaries and comparisons."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,importlib.util,json,math,tarfile,time
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/v2/typed200-r5-heldout-remaining-v1'
OLD=ROOT/'build/v2/typed200-r5-heldout-eval-v1'
REPORT=ROOT/'docs/research/2026-10-17-typed200-r5-remaining-results.md'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def same(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        for key in a:same(a[key],b[key])
    elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(a,b)
    else:assert a==b,(a,b)

def main():
    assert json.loads((BASE/'target/receipt.json').read_text())['passed']
    expected={'metadata.json','summary.json','requests.jsonl','progress.log'}
    with tarfile.open(BASE/'target/collect.stdout','r:gz') as archive:
        assert set(archive.getnames())==expected
        for member in archive:
            assert member.isfile() and member.name in expected
            with (BASE/member.name).open('xb') as out:
                source=archive.extractfile(member)
                while chunk:=source.read(1048576):out.write(chunk)
    suite=json.loads((BASE/'cases.json').read_text())
    summary=json.loads((BASE/'summary.json').read_text())
    prior_ids={c['ids_sha256'] for c in json.loads((OLD/'cases.json').read_text())['cases']}
    assert summary['complete'] and summary['errors']==0
    assert summary['requests']==summary['successful']==len(suite['cases'])
    spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts/v2/collect_r5_remaining.py')
    collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    compact=[];seen=set()
    columns=['id','dataset','tokens','head_jobs','classification_n','classification_correct','unscored_classification','slot_tokens','slot_tokens_correct','slot_tp','slot_fp','slot_fn','end_to_end_ms','service_ms','ingress_ms','pl_encoder_ms','pl_request_ms']
    with (BASE/'requests.csv').open('x',newline='') as stream,(BASE/'requests.jsonl').open() as journal:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for case,line in zip(suite['cases'],journal,strict=True):
            row=json.loads(line)
            assert row['passed'] and row['id']==case['id'] and row['ids_sha256']==case['ids_sha256']
            assert row['ids_sha256'] not in prior_ids and row['ids_sha256'] not in seen
            seen.add(row['ids_sha256'])
            assert row['r5_trace'].startswith('R5: INFERENCE PASS')
            status=dict(s.split('=',1) for s in row['r5_cleanup_status'].split())
            assert all(status[k]=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','error','recovery_error'])
            decisions=[p for p in row['predictions'] if not p['head'].startswith('slots.') and p['expected'] is not None]
            assert len(decisions)==row['scores']['classification_n']
            assert sum(p['label']==p['expected'] for p in decisions)==row['scores']['classification_correct']
            assert all(math.isfinite(v) and v>=0 for v in row['latency_ms'].values())
            compact.append({k:v for k,v in row.items() if k not in ['predictions','r5_trace','r5_cleanup_status']})
            writer.writerow({**{k:row[k] for k in columns[:4]},**{k:row['scores'][k] for k in columns[4:12]},**{k:row['latency_ms'][k.removesuffix('_ms')] for k in columns[12:]}})
    same(summary,collector.metrics(compact,True))
    old_summary=json.loads((OLD/'summary.json').read_text())
    combined=[{k:v for k,v in json.loads(line).items() if k not in ['predictions','r5_trace','r5_cleanup_status']} for line in (OLD/'requests.jsonl').read_text().splitlines()]+compact
    (BASE/'combined-summary.json').write_text(json.dumps(collector.metrics(combined,True),indent=2)+'\n')
    entries=[];table=[];comparison=[]
    for name,d in summary['datasets'].items():
        latency=d['latency_ms']['end_to_end'];previous=old_summary['datasets'][name]
        entry=dict(dataset=name,requests=d['requests'],classification_correct=d['classification_correct'],classification_n=d['classification_n'],classification_accuracy=d['classification_accuracy'],unscored_classification=d['unscored_classification'],slot_span_f1=d['slot_span_f1'],slot_token_accuracy=d['slot_token_accuracy'],request_mean_ms=latency['mean'],request_p50_ms=latency['p50'],request_p95_ms=latency['p95'],request_p99_ms=latency['p99'],encoder_p50_ms=d['latency_ms']['pl_encoder']['p50'])
        entries.append(entry)
        f1=f"{d['slot_span_f1']:.3f}" if d['slot_span_f1'] is not None else '-'
        table.append(f"| {name} | {d['requests']:,} | {d['classification_accuracy']:.1%} ({d['classification_correct']}/{d['classification_n']}) | {f1} | {latency['p50']:.1f} | {latency['p95']:.1f} |")
        comparison.append(f"| {name} | {previous['classification_accuracy']:.1%} | {d['classification_accuracy']:.1%} | {100*(d['classification_accuracy']-previous['classification_accuracy']):+.2f} | {previous['latency_ms']['end_to_end']['p50']:.1f} | {latency['p50']:.1f} |")
    with (BASE/'summary.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(entries[0]));writer.writeheader();writer.writerows(entries)
    health=(BASE/'target/health.stdout').read_text()
    assert health.startswith('6c80ec1a-e7ae-473f-b169-d54f129615d1\n12288\n0-3\n')
    assert 'operating' in health and '199999998' in health
    for key in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','error','recovery_error']:
        assert key+'=0' in health
    for _ in range(20):
        if '# Passive capture end' in (BASE/'uart.txt').read_text():break
        time.sleep(.1)
    assert '# Passive capture end' in (BASE/'uart.txt').read_text()
    REPORT.write_text('# Remaining held-out R5 accuracy and latency\n\n'
        f"Completed **{len(compact):,}/{len(suite['cases']):,} new requests with zero runtime errors**. The previous700 were excluded by encoded-input hash, including duplicate copies of those inputs. R5 controlled PL inference and computed classifier/slot heads, Linux stayed running, and JTAG stayed stopped. Model, PL, firmware, tokenizer and deployed client were unchanged.\n\n"
        '| Dataset | Requests | Classification accuracy | Slot span F1 | Request p50 ms | Request p95 ms |\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join(table)+'\n\n'
        '## What improved compared with previous runs\n\n'
        'Earlier350-case reference runs established numerical correctness against a frozen implementation. The first700 fresh cases added ground-truth accuracy and on-board latency. This run exhausts the remaining eligible existing test inputs, making each dataset estimate substantially less dependent on a100-example sample and checking sustained runtime stability. Journals retain predictions, gold labels, hashes, timings and R5 cleanup evidence. Collection now streams detailed records, keeps only compact statistics in memory, checkpoints every250 requests, transfers an archive, and runs under a bounded independent systemd job. These are evaluation/collection improvements; no model accuracy or inference speed optimization was applied.\n\n'
        '| Dataset | First100 accuracy | Remaining accuracy | Difference pp | First100 p50 ms | Remaining p50 ms |\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join(comparison)+'\n\n'
        'Differences above compare disjoint examples, not before/after model versions. They do not demonstrate an optimization gain. The combined-summary.json pools this run and the original700 with exact percentile recomputation. SGD unknown intents remain outside the classification denominator; counts are in summary.csv. Multi-CLINC accuracy counts retained segment decisions. Slot F1 uses existing BIO entity spans and labels over retained words after128-token truncation.\n\n'
        '## Coverage and timing\n\n'
        'All eligible remaining examples from the seven existing test groups were selected with seed20261018 and randomized execution order. As in the first batch, encoded train/dev overlap, previous350 reference inputs/text segments, duplicate selected inputs and unsupported request shapes were excluded; selection.json records every exclusion category by dataset. This is coverage of the filtered test pools, not every raw test row. No labels were used for selection or tuning.\n\n'+summary['timing_scope']+' Single sequential long-lived process; no cold CLI/network timing or isolated R5-head timer.\n\n'
        '## Artifacts and final state\n\n'
        'build/v2/typed200-r5-heldout-remaining-v1 contains cases.json, selection.json, requests.jsonl, requests.csv, summary.json, summary.csv, combined-summary.json, metadata.json, UART and target execution logs. Same Linux boot and200MHz PL clocks checked after completion; all per-request R5 resource releases checked. App/model and R5 module stay deployed; dashboard stays stopped. No auto-reboot or recurring job.\n')
    anchor=json.loads((BASE/'preservation-before.json').read_text())
    prior=json.loads((BASE/'prior-validation.json').read_text())
    preserved={**prior['preserved_sha256'],**prior['candidate_sha256'],anchor['anchor']:anchor['anchor_sha256']}
    for name,digest in preserved.items():assert sha(ROOT/name)==digest,name
    scripts=['prepare_r5_remaining_eval.py','collect_r5_remaining.py','stage_r5_remaining_eval.py','run_r5_remaining_ssh.py','finish_r5_remaining_eval.py']
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[ROOT/'scripts/v2'/n for n in scripts]+[REPORT]
    seal={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    validation=dict(passed=True,observed_utc=datetime.now(timezone.utc).isoformat(),hardware_requests=len(compact),runtime_errors=0,r5_inference=True,linux_running=True,jtag_used=False,model_changed=False,previous700_excluded=True,preserved_sha256=preserved,candidate_sha256=seal,handoff_mutable_unsealed=True)
    (ROOT/'docs/research/2026-10-17-typed200-r5-remaining-results-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    handoff=ROOT/'HANDOFF.md';text=handoff.read_text(encoding='utf-8')
    marker='CURRENT2026-10-17 REMAINING HELD-OUT RUN COMPLETE:\nRead docs/research/2026-10-17-typed200-r5-remaining-results.md first.\n'+f"All{len(compact)} new requests completed, zero runtime errors. Prior700 excluded.\nR5 controls inference/heads; Linux running; JTAG stopped. No model/PL/client\nchanges. Dataset accuracy/latency in summary.csv; combined700+remaining in\ncombined-summary.json. Same boot/200MHz PL; all R5 resources released.\nModule/app/model stay deployed, dashboard stays stopped. UART closed.\nNo recurring collection or pending board action. Preserve newly sealed files.\n\n"
    at=text.index('CURRENT2026-10-17');handoff.write_text(text[:at]+marker+text[at:],encoding='utf-8')
    print('\n'.join(table));print(f'PASS {len(compact)} remaining requests; CSV/report/combined summaries saved and sealed',flush=True)

if __name__=='__main__':main()
