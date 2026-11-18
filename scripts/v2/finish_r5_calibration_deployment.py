"""Independently verify paired board results, export CSV and record promotion."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,importlib.util,json,math,tarfile,time
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/v2/typed200-linux-r5-calibrated-v1'
REPORT=ROOT/'docs/research/2026-10-17-typed200-r5-calibrated-results.md'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def same(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:same(a[k],b[k])
    elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
    else:assert a==b,(a,b)

def main():
    assert json.loads((BASE/'target/receipt.json').read_text())['passed']
    names={'hardware-validation.json','promotion.json','metadata.json','summary.json','requests.jsonl','progress.log','source/sysone_r5_smoke.ko'}
    with tarfile.open(BASE/'target/collect.stdout','r:gz') as archive:
        assert set(archive.getnames())==names
        for member in archive:
            assert member.isfile();dest=BASE/'hardware-results'/member.name;dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as out:
                source=archive.extractfile(member)
                while chunk:=source.read(1048576):out.write(chunk)
    result=BASE/'hardware-results';promotion=json.loads((result/'promotion.json').read_text())
    summary=json.loads((result/'summary.json').read_text());hardware=json.loads((result/'hardware-validation.json').read_text())
    assert summary['complete'] and summary['requests']==summary['successful']==6580 and summary['errors']==0
    assert hardware['passed'] and len(hardware['cases'])==350 and hardware['integer_logits']==191401
    suite=json.loads((BASE/'cases.json').read_text());wanted={r['ids_sha256'] for r in suite['cases']};assert len(wanted)==6580
    baseline={}
    for name in ['typed200-r5-heldout-eval-v1','typed200-r5-heldout-remaining-v1']:
        with (ROOT/'build/v2'/name/'requests.jsonl').open() as stream:
            for line in stream:
                row=json.loads(line)
                if row['ids_sha256'] in wanted:baseline[row['ids_sha256']]=row
    rows=[];paired={};seen=set();csvrows=[]
    with (result/'requests.jsonl').open() as stream:
        for case,line in zip(suite['cases'],stream,strict=True):
            row=json.loads(line);assert row['passed'] and row['id']==case['id'] and row['ids_sha256']==case['ids_sha256']
            assert row['ids_sha256'] not in seen;seen.add(row['ids_sha256'])
            assert row['r5_trace'].startswith('R5: INFERENCE PASS')
            fields=dict(s.split('=',1) for s in row['r5_cleanup_status'].split())
            assert all(fields[k]=='0' for k in ['pinned','reserved','lease_pending','mapped','may_run','loaded','quarantine','error','recovery_error'])
            before=baseline[row['ids_sha256']];d=paired.setdefault(row['dataset'],dict(requests=0,n=0,before_correct=0,after_correct=0,wrong_to_right=0,right_to_wrong=0))
            d['requests']+=1;d['n']+=row['scores']['classification_n'];d['before_correct']+=before['scores']['classification_correct'];d['after_correct']+=row['scores']['classification_correct']
            assert len(before['predictions'])==len(row['predictions'])
            for p,q in zip(before['predictions'],row['predictions']):
                assert p['head']==q['head'] and p['expected']==q['expected']
                if p['expected'] is not None:
                    d['wrong_to_right']+=not p['correct'] and q['correct'];d['right_to_wrong']+=p['correct'] and not q['correct']
            rows.append({k:v for k,v in row.items() if k not in ['predictions','r5_trace','r5_cleanup_status']})
            csvrows.append(dict(id=row['id'],dataset=row['dataset'],tokens=row['tokens'],classification_n=row['scores']['classification_n'],before_correct=before['scores']['classification_correct'],after_correct=row['scores']['classification_correct'],before_ms=before['latency_ms']['end_to_end'],after_ms=row['latency_ms']['end_to_end']))
    assert seen==wanted==set(baseline)
    spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts/v2/collect_r5_remaining.py');collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    same(summary,collector.metrics(rows,True));old=collector.metrics(list(baseline.values()),True)
    entries=[];table=[]
    for name,d in paired.items():
        d['before_accuracy']=d['before_correct']/d['n'];d['after_accuracy']=d['after_correct']/d['n']
        for k,v in promotion['paired'][name].items():assert d[k]==v,(name,k)
        d['before_p50_ms']=old['datasets'][name]['latency_ms']['end_to_end']['p50'];d['after_p50_ms']=summary['datasets'][name]['latency_ms']['end_to_end']['p50']
        d['before_p95_ms']=old['datasets'][name]['latency_ms']['end_to_end']['p95'];d['after_p95_ms']=summary['datasets'][name]['latency_ms']['end_to_end']['p95']
        entries.append(dict(dataset=name,**d))
        table.append(f"| {name} | {d['requests']:,} | {d['before_accuracy']:.2%} | {d['after_accuracy']:.2%} | {100*(d['after_accuracy']-d['before_accuracy']):+.2f} | {d['before_p50_ms']:.1f} / {d['after_p50_ms']:.1f} | {d['before_p95_ms']:.1f} / {d['after_p95_ms']:.1f} |")
    for filename,records in [('paired-requests.csv',csvrows),('paired-summary.csv',entries)]:
        with (BASE/filename).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    (BASE/'paired-comparison.json').write_text(json.dumps(dict(passed=True,accepted=promotion['accepted'],datasets=paired),indent=2)+'\n')
    health=(BASE/'target/health.stdout').read_text();assert health.startswith('6c80ec1a-e7ae-473f-b169-d54f129615d1\n12288\n0-3\n')
    assert promotion['current_elf_sha256'] in health and 'operating' in health and health.count('199999998')==2
    for _ in range(30):
        if '# Passive capture end' in (BASE/'uart.txt').read_text():break
        time.sleep(.1)
    assert '# Passive capture end' in (BASE/'uart.txt').read_text()
    disposition='**PROMOTED: the calibrated R5 classifier is deployed and sysone-infer uses it.**' if promotion['accepted'] else '**NOT PROMOTED: the previous R5 classifier was restored.**'
    REPORT.write_text('# R5 classifier calibration: paired hardware results\n\n'+disposition+'\n\n'
        'The original55,261-case remaining-set benchmark completed first with zero runtime errors. Its baseline artifacts are preserved. Then the R5 fixed image was replaced through the existing Linux PM/module path; PL and model weights were reused. Linux stayed running and JTAG stayed stopped.\n\n'
        '| Dataset | Paired requests | Baseline accuracy | Calibrated accuracy | Gain pp | Median ms before / after | p95 ms before / after |\n|---|---:|---:|---:|---:|---:|---:|\n'+'\n'.join(table)+'\n\n'
        '## Concrete change\n\n'
        'R5 now applies a calibrated CLINC rejection rule: a top softmax probability below0.36 selects the existing out-of-scope class. This also applies separately to Multi-CLINC segments. Scaled logits, probability normalization and the decision execute on R5; Linux still only tokenizes/transports/formats. Every integer logit and every other head is unchanged. This is a classifier calibration improvement; encoder and classifier weights were not retrained.\n\n'
        'The missing older0.48 rule improved OOS recall but lost3 correct examples on development. The new0.36 threshold maximizes total accuracy on the existing3,100-example development split under at most1 percentage point in-scope loss:2965/3100(95.65%) to2977/3100(96.03%); OOS recall52% to73%, in-scope accuracy97.1% to96.8%. Current held-out labels were not used to fit the threshold. Cached first3,000 dev probabilities were checked against fresh computations at5 positions; the missing100 were computed from the deployed integer image. The old failed candidate artifacts are preserved.\n\n'
        'Native C matched NumPy decisions on all3,100 development examples; exponential absolute error was at most2.23e-16 on20,004 grid/extreme inputs. Native heads matched191,401 integer logits on350 frozen requests; actual Cortex-R5F emulation exercised changed OOS rejection. Hardware then independently checked all350 requests and191,401 logits before the paired evaluation.\n\n'
        '## Paired evaluation and promotion\n\n'
        'The6580 inputs are exactly the CLINC and Multi-CLINC requests in the first700 plus the remaining55,261 baseline. The candidate evaluated each once, in a new deterministic shuffled order. Labels/inputs are identical within each comparison. CLINC counts one decision per request; Multi-CLINC counts retained segments. The promotion gate requires no accuracy regression in either dataset and a strictly positive combined gain; otherwise the prior fixed-image module is restored while idle. No threshold was refit after this test.\n\n'+summary['timing_scope']+' Sequential passes were at different times/cache states, so latency changes are observations rather than a controlled speedup claim.\n\n'
        '## Deployment and artifacts\n\n'
        f"Current R5 ELF SHA256: {promotion['current_elf_sha256']}. Same Linux boot, CPUs0-3 and199999998Hz PL clocks. All6580 R5 completions/resource releases verified. Model, PL, tokenizer and CLI client remain unchanged; R5 module stays loaded, R5 is idle between requests, dashboard stays stopped. This remains a current-boot CLI deployment.\n\n"
        'build/v2/typed200-linux-r5-calibrated-v1 contains paired-summary.csv, paired-requests.csv, paired-comparison.json, calibration-dev-fit.json, hardware-results/requests.jsonl, summary.json, metadata.json, hardware-validation.json, promotion.json, kernel module, native/emulator receipts, UART and target logs.\n')
    prior=json.loads((BASE/'prior-validation.json').read_text());anchor=json.loads((BASE/'preservation-before.json').read_text())
    preserved={**prior['preserved_sha256'],**prior['candidate_sha256'],anchor['anchor']:anchor['anchor_sha256']}
    for name,digest in preserved.items():assert sha(ROOT/name)==digest,name
    scripts=['prepare_r5_calibrated_candidate.py','build_r5_calibrated_candidate.py','check_r5_calibrated_heads.py','check_r5_calibrated_elf.py','check_r5_calibrated_elf_v2.py','check_r5_calibrated_policy.py','fit_r5_clinc_calibration.py','deploy_r5_calibration_target.py','stage_r5_calibration_deployment.py','finish_r5_calibration_deployment.py']
    # The read-only observer can finish after this controller. Its live stream is
    # explicitly unsealed; the authoritative target journal/receipt are closed.
    files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'watch' not in p.relative_to(BASE).parts]
    files += [p for p in (ROOT/'firmware/typed200_linux_r5_calibrated_inference').rglob('*') if p.is_file()]
    files += [ROOT/'scripts/v2'/name for name in scripts]+[REPORT]
    validation=dict(passed=True,observed_utc=datetime.now(timezone.utc).isoformat(),hardware_requests=6580,hardware_reference_requests=350,accepted=promotion['accepted'],current_elf_sha256=promotion['current_elf_sha256'],r5_inference=True,linux_running=True,jtag_used=False,model_weights_changed=False,decision_rule_changed=True,preserved_sha256=preserved,candidate_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files},handoff_mutable_unsealed=True,live_watch_unsealed=True)
    (ROOT/'docs/research/2026-10-17-typed200-r5-calibrated-results-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    handoff=ROOT/'HANDOFF.md';text=handoff.read_text(encoding='utf-8');at=text.index('CURRENT2026-10-17')
    block='CURRENT2026-10-17 R5 CALIBRATED CLASSIFIER HARDWARE TRIAL COMPLETE:\nRead docs/research/2026-10-17-typed200-r5-calibrated-results.md first.\n'+f"Accepted={promotion['accepted']}; current ELF {promotion['current_elf_sha256']}.\nBaseline55261 complete, zero errors; candidate350 reference+6580 paired requests\ncomplete, zero errors. Tau0.36 fit only ondev. Paired dataset results in\nbuild/v2/typed200-linux-r5-calibrated-v1/paired-summary.csv. Linux sameboot,\nJTAG stopped, PL/model/CLI unchanged, onlyfixed R5 image/module changed if\naccepted. Model weights unchanged, classifier calibration improved. UART closed.\nApp/model/module stay loaded; R5 idle, all resources released. Dashboard stays\nstopped. Do NOT restore stock or unloadmodule as routine cleanup. No pending\nboard job or required physical action. Earlier runner states below historical.\n\n"
    handoff.write_text(text[:at]+block+text[at:],encoding='utf-8')
    print(disposition);print('\n'.join(table));print('PASS paired hardware results verified, exported and sealed',flush=True)

if __name__=='__main__':main()
