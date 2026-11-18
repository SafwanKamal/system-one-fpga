"""Check the collected journal, export CSV, and seal the first held-out batch."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,importlib.util,json,math
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-r5-heldout-eval-v1'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    assert json.loads((BASE/'target/receipt.json').read_text())['passed']
    contents=json.loads((BASE/'target/collect.stdout').read_text())
    for name in ['metadata.json','summary.json','requests.jsonl']:
        path=BASE/name;assert not path.exists();path.write_text(contents[name])
    rows=[json.loads(line) for line in contents['requests.jsonl'].splitlines()]
    summary=json.loads(contents['summary.json']);metadata=json.loads(contents['metadata.json']);suite=json.loads((BASE/'cases.json').read_text())
    assert summary['complete'] and summary['requests']==summary['successful']==len(rows)==700 and summary['errors']==0
    assert [r['id'] for r in rows]==[r['id'] for r in suite['cases']]
    assert len({r['ids_sha256'] for r in rows})==700
    for row,case in zip(rows,suite['cases']):
        assert row['passed'] and row['ids_sha256']==case['ids_sha256']
        assert row['r5_trace'].startswith('R5: INFERENCE PASS')
        status=dict(s.split('=',1) for s in row['r5_cleanup_status'].split())
        assert all(status[k]=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','error','recovery_error'])
        decisions=[p for p in row['predictions'] if not p['head'].startswith('slots.') and p['expected'] is not None]
        assert len(decisions)==row['scores']['classification_n']
        assert sum(p['label']==p['expected'] for p in decisions)==row['scores']['classification_correct']
        assert all(math.isfinite(v) and v>=0 for v in row['latency_ms'].values())
    spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts/v2/collect_r5_heldout.py');collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    recomputed=collector.metrics(rows,True)
    def same(a,b):
        if isinstance(a,dict):assert set(a)==set(b);[same(a[k],b[k]) for k in a]
        elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
        else:assert a==b,(a,b)
    same(summary,recomputed)
    columns=['id','dataset','tokens','head_jobs','classification_n','classification_correct','slot_tokens','slot_tokens_correct','slot_tp','slot_fp','slot_fn','end_to_end_ms','service_ms','ingress_ms','pl_encoder_ms','pl_request_ms']
    with (BASE/'requests.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=columns);w.writeheader()
        for r in rows:w.writerow({**{k:r[k] for k in columns[:4]},**{k:r['scores'][k] for k in columns[4:11]},**{k:r['latency_ms'][k.removesuffix('_ms')] for k in columns[11:]}})
    summary_rows=[];table=[]
    for name,d in summary['datasets'].items():
        latency=d['latency_ms'];accuracy=d['classification_accuracy'];f1=d['slot_span_f1']
        summary_rows.append(dict(dataset=name,requests=d['requests'],classification_correct=d['classification_correct'],classification_n=d['classification_n'],classification_accuracy=accuracy,slot_span_f1=f1,slot_token_accuracy=d['slot_token_accuracy'],request_p50_ms=latency['end_to_end']['p50'],request_p95_ms=latency['end_to_end']['p95'],encoder_p50_ms=latency['pl_encoder']['p50']))
        acc=f"{accuracy:.1%} ({d['classification_correct']}/{d['classification_n']})" if accuracy is not None else 'n/a'
        table.append(f"| {name} | {acc} | {f'{f1:.3f}' if f1 is not None else '-'} | {latency['end_to_end']['p50']:.1f} | {latency['end_to_end']['p95']:.1f} |")
    with (BASE/'summary.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(summary_rows[0]));w.writeheader();w.writerows(summary_rows)
    all_latency=summary['latency_ms'];unscored={n:d['unscored_classification'] for n,d in summary['datasets'].items() if d['unscored_classification']}
    report=ROOT/'docs/research/2026-10-17-typed200-r5-heldout-results.md';assert not report.exists()
    report.write_text('# Fresh held-out R5 accuracy and latency results\n\n'
        'First batch: **700/700 requests completed, zero runtime errors**,100 fresh test cases per dataset group. R5 controlled PL and computed classifier/slot heads; Linux stayed running and JTAG stayed stopped. The PL app, model, R5 firmware and deployed client were unchanged.\n\n'
        '| Dataset | Label accuracy | Slot span F1 | Request p50 ms | Request p95 ms |\n|---|---:|---:|---:|---:|\n'+'\n'.join(table)+'\n\n'
        f"Overall observed on-board request latency: p50 **{all_latency['end_to_end']['p50']:.1f}ms**, p95 **{all_latency['end_to_end']['p95']:.1f}ms**, p99 **{all_latency['end_to_end']['p99']:.1f}ms**. PL encoder alone: p50 **{all_latency['pl_encoder']['p50']:.2f}ms**, p95 **{all_latency['pl_encoder']['p95']:.2f}ms**.\n\n"
        '## Sample and scoring\n\n'
        'Seed20261017 selected100 per dataset from the existing test splits, then randomized execution order. Exact encoded inputs from training/development and the previous350-case reference suite were excluded, as were previous-reference text segments and duplicate selected inputs. Label tables matched the model. These are fresh examples relative to that reference run, from existing benchmark test sets; no retraining, threshold fitting or new dataset sourcing occurred. Selection and complete input/ground-truth data are saved in selection.json and cases.json.\n\n'
        'Accuracy is measured against dataset ground truth, not against another implementation. Multi-CLINC counts each retained segment decision, so its denominator exceeds100. Slot F1 is micro-averaged BIO entity-span F1 over retained words after128-token truncation, using the existing dataset-loader label policy. '
        f'Unknown/unscored intent counts: {json.dumps(unscored)}. These are excluded from the accuracy denominator. Each dataset has100 requests; percentages are sample estimates.\n\n'
        '## Latency scope\n\n'+summary['timing_scope']+' Values are from a single sequential pass through a long-lived board process, with the tokenizer cache evolving normally. They are not cold CLI process-launch or network response measurements. Every request still prepares/starts R5 and confirms stop/resource release, as in the deployed client. Request timing includes that overhead. No hard real-time bound is inferred.\n\n'
        '## Data and final state\n\n'
        'Local build/v2/typed200-r5-heldout-eval-v1 contains requests.jsonl (predictions, gold labels, logit hashes, timings and R5 completion/cleanup for every request), requests.csv, summary.json, summary.csv, metadata.json and selection.json. Remote collection stage is /var/lib/sysone/r5-evaluation/fresh-test-v1.\n\n'
        f"Boot remained {metadata['boot_id']}; PL clock was{metadata['clock_hz']}Hz. All700 R5 completions and resource releases were checked. The app/model and R5 module remain deployed and sysone-infer remains ready. UART was closed after collection. The finite first batch has finished; no recurring collection job was installed.\n\n"
        'The companion validation JSON records preserved prior files and hashes for this batch. HANDOFF.md remains mutable.\n')
    assert '# Passive capture end' in (BASE/'uart.txt').read_text()
    prior=json.loads((BASE/'prior-validation.json').read_text());anchor=json.loads((BASE/'preservation-before.json').read_text())
    preserved={**prior['preserved_sha256'],**prior['candidate_sha256']};preserved[anchor['anchor']]=anchor['anchor_sha256']
    assert json.loads((BASE/'preservation-after.json').read_text())==dict(passed=True,files=len(preserved))
    scripts=['prepare_r5_heldout_eval.py','collect_r5_heldout.py','stage_r5_heldout_eval.py','finish_r5_heldout_eval.py']
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[ROOT/'scripts/v2'/n for n in scripts]+[report]
    candidates={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
    validation=ROOT/'docs/research/2026-10-17-typed200-r5-heldout-results-validation.json';assert not validation.exists()
    validation.write_text(json.dumps(dict(passed=True,observed_utc=datetime.now(timezone.utc).isoformat(),preserved_unique_files=len(preserved),preserved_sha256=preserved,candidate_files=len(candidates),candidate_sha256=candidates,hardware_requests=700,runtime_errors=0,fresh_test_examples=True,r5_inference=True,linux_running=True,jtag_used=False,model_changed=False,handoff_mutable_unsealed=True),indent=2)+'\n')
    print('\n'.join(table));print(f'PASS700 fresh board requests; summaries/CSV/evidence saved, {len(candidates)} new files sealed')

if __name__=='__main__':main()
