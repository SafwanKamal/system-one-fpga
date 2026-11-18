"""Prepare and compare local software baselines. No board imports or access."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
from sysone.v2.maintenance.schema import canonical, encode, parse, validate, VERSION
from sysone.v2.maintenance.dataset import pilot, public_input, prompt, score, manifest, STRATA
from sysone.v2.maintenance.baselines import features, flatten, unflatten, rules


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r, allow_nan=False)+'\n' for r in rows), encoding='utf-8')


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def check_sources(work):
    for name, digest in json.loads((work/'source-sha256.json').read_text()).items():
        if sha(ROOT/name) != digest or sha(work/'snapshot'/name) != digest:
            raise RuntimeError('Source changed since preparation: '+name)
    for name, digest in json.loads((work/'data-sha256.json').read_text()).items():
        if sha(work/name) != digest:
            raise RuntimeError('Frozen data changed: '+name)


def prepare(work):
    work.mkdir(parents=True, exist_ok=False)
    data = pilot()
    files = []
    for split, rows in data.items():
        name = split+'.jsonl'
        write_rows(work/name, rows)
        files.append(name)
        for row in rows:
            if canonical(parse(encode(row['gold']), row['catalog'])) != canonical(row['gold']):
                raise RuntimeError('Codec target does not round trip')
            if unflatten(flatten(row['gold'], row['catalog']), row['catalog']) != row['gold']:
                raise RuntimeError('Encoder target does not round trip')
    dump(work/'manifest.json', manifest(data))
    files.append('manifest.json')
    sources = [Path(__file__)] + sorted((ROOT/'src/sysone/v2/maintenance').glob('*.py'))
    sources += [ROOT/'src/sysone/v2/qwen_tokenizer_v1.py', ROOT/'src/sysone/v2/v8_benchmark.py',
                ROOT/'tests/test_maintenance_pilot.py']
    hashes = {}
    for p in sources:
        name = p.relative_to(ROOT).as_posix()
        dst = work/'snapshot'/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
        hashes[name] = sha(p)
    dump(work/'source-sha256.json', hashes)
    dump(work/'data-sha256.json', {name: sha(work/name) for name in files})
    from sysone.v2.qwen_tokenizer_v1 import Vocabulary
    from transformers import AutoTokenizer
    package = ROOT/'build/v2/qwen-fpga-decoder-v8/deployment'
    vocab = Vocabulary(package)
    tok = AutoTokenizer.from_pretrained(str(ROOT/'models/all-MiniLM-L12-v2'), local_files_only=True)
    audit = []
    try:
        for split, rows in data.items():
            for row in rows:
                text = prompt(row)
                ids = vocab.encode_text(text)
                gold_ids = vocab.encode_text(encode(row['gold']))
                encoder_ids = tok(features(public_input(row)), truncation=False)['input_ids']
                audit.append(dict(id=row['id'], split=split, stratum=row['stratum'],
                    qwen_input_tokens=len(ids), qwen_gold_output_tokens=len(gold_ids),
                    qwen_deployable_reserve96=len(ids)+96 <= 256,
                    qwen_gold_fits256=len(ids)+len(gold_ids)+1 <= 256,
                    qwen_reference_fits=len(ids) <= 1024 and len(gold_ids)+1 <= 256,
                    encoder_input_tokens=len(encoder_ids), encoder_fits128=len(encoder_ids) <= 128,
                    encoder_fits256=len(encoder_ids) <= 256, prompt=text, prompt_ids=ids))
    finally:
        vocab.close()
    write_rows(work/'token-audit.jsonl', audit)
    summary = {}
    for split in data:
        rs = [r for r in audit if r['split'] == split]
        summary[split] = dict(count=len(rs),
            qwen_input_min=min(r['qwen_input_tokens'] for r in rs),
            qwen_input_max=max(r['qwen_input_tokens'] for r in rs),
            qwen_gold_output_max=max(r['qwen_gold_output_tokens'] for r in rs),
            encoder_input_max=max(r['encoder_input_tokens'] for r in rs),
            eligible={k: sum(r[k] for r in rs) for k in (
                'qwen_deployable_reserve96', 'qwen_gold_fits256', 'qwen_reference_fits',
                'encoder_fits128', 'encoder_fits256')})
    dump(work/'token-audit-summary.json', summary)
    frozen = json.loads((work/'data-sha256.json').read_text())
    for name in ('token-audit.jsonl', 'token-audit-summary.json'):
        frozen[name] = sha(work/name)
    dump(work/'data-sha256.json', frozen)
    dump(work/'preflight.json', dict(board_access=False, development_only=True,
        corpus_generated=True, schema_roundtrips=True, encoder_target_roundtrips=True,
        prior_evidence_modified=False, energy_measured=False))
    print(json.dumps(summary), flush=True)


def verdict(case, raw, seconds, **extra):
    result = dict(id=case['id'], stratum=case['stratum'], seconds=seconds,
                  raw_output=raw, valid=False, correct=False, accepted=False,
                  actionable=case['gold']['outcome'] == 'plan', **extra)
    try:
        ast = parse(raw, case['catalog'])
        result.update(valid=True, ast=ast, **score(case, ast))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    return result


def summary(rows):
    n = len(rows)
    accepted = sum(r['accepted'] for r in rows)
    correct_accepted = sum(r['correct'] and r['accepted'] for r in rows)
    return dict(count=n, valid=sum(r['valid'] for r in rows), correct=sum(r['correct'] for r in rows),
        accepted=accepted, correct_accepted=correct_accepted,
        incorrect_accepted=accepted-correct_accepted,
        actionable_total=sum(r['actionable'] for r in rows),
        strata={s: dict(count=sum(r['stratum'] == s for r in rows),
                       correct=sum(r['stratum'] == s and r['correct'] for r in rows)) for s in STRATA},
        inference_seconds=sum(r['seconds'] for r in rows),
        energy_joules=None, board_access=False, generalization_claim=False)


def finish(out, config):
    rows = read_rows(out/'audit-predictions.jsonl')
    dump(out/'summary.json', dict(summary(rows), config=config))
    dump(out/'seal.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'seal.json'})
    print(json.dumps(dict(backend=out.name, **summary(rows))), flush=True)


def run_classical(work):
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    train = read_rows(work/'train.jsonl')
    audit = read_rows(work/'audit.jsonl')
    out = work/'rules'
    out.mkdir(exist_ok=False)
    rows = []
    for case in audit:
        tick = time.perf_counter()
        ast = rules(public_input(case))
        raw = encode(ast)
        rows.append(verdict(case, raw, time.perf_counter()-tick))
    write_rows(out/'audit-predictions.jsonl', rows)
    finish(out, dict(method='hand-authored parser frozen before audit; pilot vocabulary only'))
    out = work/'tfidf'
    out.mkdir(exist_ok=False)
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2,5), min_df=2, sublinear_tf=True)
    tick = time.perf_counter()
    x = vectorizer.fit_transform([features(public_input(c)) for c in train])
    labels = [flatten(c['gold'], c['catalog']) for c in train]
    heads = {}
    for key in labels[0]:
        y = [r[key] for r in labels]
        heads[key] = y[0] if len(set(y)) == 1 else LogisticRegression(C=10, max_iter=500, random_state=0).fit(x, y)
    training_seconds = time.perf_counter()-tick
    rows = []
    for case in audit:
        tick = time.perf_counter()
        vec = vectorizer.transform([features(public_input(case))])
        values = {k: h if type(h) is str else str(h.predict(vec)[0]) for k,h in heads.items()}
        try:
            raw = encode(unflatten(values, case['catalog']))
            error = None
        except (ValueError, TypeError, IndexError, KeyError) as exc:
            raw, error = json.dumps(values), str(exc)
        rows.append(verdict(case, raw, time.perf_counter()-tick, decode_error=error, predicted_fields=values))
    write_rows(out/'audit-predictions.jsonl', rows)
    import pickle
    (out/'model.pkl').write_bytes(pickle.dumps((vectorizer, heads)))
    finish(out, dict(method='factorized categorical structured heads', training_seconds=training_seconds,
                     C=10, seed=0, training_records=len(train), test_selected=False))


def run_encoder(work, epochs, threads):
    import numpy as np
    import torch
    from torch import nn
    from transformers import AutoModel, AutoTokenizer
    torch.set_num_threads(threads)
    torch.manual_seed(0)
    out = work/'minilm'
    out.mkdir(exist_ok=False)
    train, tuning, audit = [read_rows(work/(s+'.jsonl')) for s in ('train','tuning','audit')]
    model_path = ROOT/'models/all-MiniLM-L12-v2'
    tok = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    base = AutoModel.from_pretrained(str(model_path), local_files_only=True)
    base.requires_grad_(False)
    for layer in base.encoder.layer[-2:]:
        layer.requires_grad_(True)
    targets = [flatten(c['gold'], c['catalog']) for c in train]
    classes = {k: sorted({r[k] for r in targets}) for k in targets[0]}
    names = list(classes)
    heads = nn.ModuleList([nn.Linear(base.config.hidden_size, len(classes[k])) for k in names])
    weights = []
    for k in names:
        counts = Counter(r[k] for r in targets)
        weights.append(torch.tensor([1/(counts[v]**0.5) for v in classes[k]], dtype=torch.float))
    def batch(cases):
        return tok([features(public_input(c)) for c in cases], padding=True, truncation=False, return_tensors='pt')
    def forward(cases):
        b = batch(cases)
        if b['input_ids'].shape[1] > 256:
            raise RuntimeError('Encoder input exceeds declared reference budget; no silent truncation')
        hidden = base(**b).last_hidden_state
        mask = b['attention_mask'].unsqueeze(-1)
        pooled = (hidden*mask).sum(1)/mask.sum(1)
        return [h(pooled) for h in heads]
    def predict(cases):
        base.eval();heads.eval()
        with torch.inference_mode():
            logits = forward(cases)
        return [{k: classes[k][int(logits[i][j].argmax())] for i,k in enumerate(names)} for j in range(len(cases))]
    def evaluate(cases):
        records = []
        for start in range(0,len(cases),16):
            group = cases[start:start+16]
            tick = time.perf_counter()
            vs = predict(group)
            seconds = (time.perf_counter()-tick)/len(group)
            for case, values in zip(group,vs):
                try:
                    raw, error = encode(unflatten(values,case['catalog'])), None
                except (ValueError,TypeError,IndexError,KeyError) as exc:
                    raw,error=json.dumps(values),str(exc)
                records.append(verdict(case, raw, seconds, predicted_fields=values, decode_error=error))
        return records
    optimizer = torch.optim.AdamW([dict(params=[p for p in base.parameters() if p.requires_grad], lr=3e-5),
                                   dict(params=heads.parameters(), lr=0.001)])
    best, selected, history = -1, None, []
    tick = time.perf_counter()
    for epoch in range(epochs):
        base.train();heads.train()
        order = np.random.default_rng(epoch).permutation(len(train))
        total = 0.
        for start in range(0,len(order),16):
            indices = order[start:start+16]
            logits = forward([train[int(i)] for i in indices])
            loss = sum(nn.functional.cross_entropy(l, torch.tensor([classes[k].index(targets[int(j)][k]) for j in indices]), weight=w)
                       for k,l,w in zip(names,logits,weights))/len(names)
            optimizer.zero_grad();loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in base.parameters() if p.requires_grad]+list(heads.parameters()),1.)
            optimizer.step();total+=float(loss.detach())
        tune = evaluate(tuning)
        correct = sum(r['correct'] for r in tune)
        history.append(dict(epoch=epoch+1,loss=total,tuning_correct=correct,tuning_total=len(tuning)))
        dump(out/'training-history.json',history)
        if correct > best:
            best=correct;selected=epoch+1
            torch.save(dict(base=base.state_dict(),heads=heads.state_dict(),classes=classes,epoch=selected),out/'checkpoint.pt')
        print(json.dumps(history[-1]),flush=True)
    saved=torch.load(out/'checkpoint.pt',map_location='cpu',weights_only=True)
    base.load_state_dict(saved['base']);heads.load_state_dict(saved['heads'])
    write_rows(out/'audit-predictions.jsonl', evaluate(audit))
    dump(out/'classes.json',classes)
    finish(out,dict(model=str(model_path),model_sha256=sha(model_path/'model.safetensors'),
        training_records=len(train),epochs=epochs,selected_epoch=selected,selection='tuning_only',
        seed=0,last_trainable_layers=2,threads=threads,training_seconds=time.perf_counter()-tick,
        reference_only=True,latency='batched16 local CPU observations; not matched deployment speed'))


def http(base, path, data=None):
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(base+path, data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def run_qwen(work, threads):
    out=work/'qwen'
    out.mkdir(exist_ok=False)
    model=ROOT/'models/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q8_0.gguf'
    binary=ROOT/'build/v2/generation/windows/llama-server.exe'
    if sha(model)!='9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031':
        raise RuntimeError('Pinned Qwen model differs')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    log=(out/'server.log').open('wb')
    cmd=[str(binary),'-m',str(model),'--host','127.0.0.1','--port',str(port),'-c','2048',
         '-np','1','-ngl','0','-t',str(threads),'-tb',str(threads),'--no-warmup']
    dump(out/'command.json',cmd)
    process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
    tick=time.monotonic()
    try:
        while True:
            if process.poll() is not None:raise RuntimeError('Server exited; inspect server.log')
            try:
                if http(base,'/health').get('status')=='ok':break
            except (urllib.error.URLError,TimeoutError):pass
            if time.monotonic()-tick>180:raise RuntimeError('Server startup timeout')
            time.sleep(0.5)
        load_seconds=time.monotonic()-tick
        jobs={r['id']:r for r in read_rows(work/'token-audit.jsonl') if r['split']=='audit'}
        audit=read_rows(work/'audit.jsonl')
        for index,case in enumerate(audit):
            job=jobs[case['id']]
            if not job['qwen_reference_fits']:
                row=verdict(case,'',0,capacity_failure=True)
            else:
                actual=http(base,'/tokenize',dict(content=job['prompt'],add_special=False))['tokens']
                if actual!=job['prompt_ids']:raise RuntimeError('Server tokenizer differs from pinned host IDs')
                request=dict(prompt=actual,n_predict=256,temperature=0,seed=0,repeat_penalty=1,
                             cache_prompt=False,stream=False)
                tick=time.perf_counter()
                response=http(base,'/completion',request)
                seconds=time.perf_counter()-tick
                dump(out/(case['id']+'.response.json'),response)
                raw=response['content']
                row=verdict(case,raw,seconds,actual_prompt_ids=actual,
                    prompt_tokens_reported=response.get('tokens_evaluated'),
                    generated_tokens=response.get('tokens_predicted'),
                    stop_type=response.get('stop_type'),truncated=response.get('truncated'),
                    deployment_eligible=job['qwen_deployable_reserve96'])
            with (out/'audit-predictions.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n');stream.flush()
            dump(out/'status.json',dict(completed=index+1,total=len(audit),board_access=False))
            print(json.dumps(dict(backend='qwen',completed=index+1,correct=row['correct'])),flush=True)
        finish(out,dict(model_sha256=sha(model),server_sha256=sha(binary),threads=threads,
            resident_model=True,startup_seconds=load_seconds,prefix_cache=False,greedy=True,
            task_training=False,context_allocated=2048,benchmark_input_cap=1024,output_cap=256,
            actual_ids_checked=True,prompt_sent_as_ids=True,matched_edge_speed_claim=False))
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()


def report(work):
    result={}
    for name in ('rules','tfidf','minilm','qwen'):
        p=work/name/'summary.json'
        if p.exists():result[name]=json.loads(p.read_text())
    dump(work/'comparison.json',dict(results=result,development_only=True,energy_measured=False,
        board_access=False,limitations=['One seed, small authored-template development audit, no family winner.',
            'Rules cover authored vocabulary; supervised encoders adapted, Qwen is task-unadapted.',
            'Different tokenizers/arithmetic and batched encoder timing; no matched speed or energy claim.']))
    lines=['# Maintenance pilot software results','',
           'Development-only, authored templates; no human-reviewed test, energy or FPGA run.','',
           '| Baseline | Correct | Valid | Correct accepted / accepted |',
           '|---|---:|---:|---:|']
    for name,r in result.items():
        lines.append(f'| {name} | {r["correct"]}/{r["count"]} | {r["valid"]}/{r["count"]} | {r["correct_accepted"]}/{r["accepted"]} |')
    lines+=['','See comparison.json, per-baseline raw audit predictions, source snapshots and token-audit-summary.json.',
            'Rules are scoped to authored vocabulary. MiniLM/TF-IDF are trained; Qwen is task-unadapted.',
            'No family superiority, rare-error, edge latency, power, or deployability claim follows.']
    (work/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=['prepare','classical','encoder','qwen','report'])
    ap.add_argument('--out',type=Path,default=ROOT/'build/v2/maintenance-pilot-v1')
    ap.add_argument('--epochs',type=int,default=3)
    ap.add_argument('--threads',type=int,default=4)
    args=ap.parse_args()
    if args.phase=='prepare':prepare(args.out);return
    check_sources(args.out)
    if args.phase=='classical':run_classical(args.out)
    elif args.phase=='encoder':run_encoder(args.out,args.epochs,args.threads)
    elif args.phase=='qwen':run_qwen(args.out,args.threads)
    else:report(args.out)
    check_sources(args.out)


if __name__=='__main__':main()
