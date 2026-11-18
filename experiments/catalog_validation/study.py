"""Frozen simple-baseline screen for diagnostic probe selection."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import pickle
import time

import numpy as np
from scipy.special import softmax
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from diagnosis import Observation, extract, select
import simulator as sim

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORK = ROOT/'build/research/catalog_validation'
DATA = WORK/'panel_v1'
OUT = ROOT/'results/research/catalog_validation/pilot_v1'
SEED = 20261117
CONFIGS = dict(train=list(range(1100, 1112)), validation=list(range(2100, 2108)), test=list(range(3100, 3120)))
KNOWN = sim.KINDS[:4]
DECODERS = ['physics', 'forest_fit', 'forest_knn']


def utc(): return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def load(path): return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def source_hashes():
    names = ['simulator.py', 'diagnosis.py', 'study.py', 'oracle.py', 'PROTOCOL.md', 'RUN_SPEC.md']
    return {name: sha(HERE/name) for name in names}


def config_data(split, config):
    if split == 'test': assert (OUT/'freeze.json').exists()
    path = DATA/split/f'{config}.npz'
    assert not path.exists(), 'Fresh runs only; never silently reuse/overwrite a generated panel.'
    kinds = KNOWN + (['quantized', 'held'] if split == 'validation' else sim.KINDS[4:] if split == 'test' else [])
    rows = []; fields = {k: [] for k in ['x8', 'x9', 'x10', 's8', 's9', 's10', 'prefix_pose', 'prefix_u',
                                       'suffix_pose', 'suffix_u', 'requested', 'violations', 'clips', 'effort', 'disruption',
                                       'violations8', 'violations9', 'clips8', 'clips9', 'effort9', 'disruption9']}
    start = time.perf_counter()
    for kind in kinds:
        repeats = 6 if kind in ['quantized', 'held'] else 10
        for rep in range(repeats):
            w = sim.world(config, rep, kind)
            all_paths = sim.run(w, kind)
            natural = sim.run(w, kind, natural=True)
            assert np.array_equal(all_paths['prefix']['pose'], natural['prefix']['pose'])
            data = dict(prefix=all_paths['prefix'])
            for key in ['pose', 'commands', 'requested', 'violations', 'clips', 'effort', 'disruption',
                        'violations8', 'violations9', 'clips8', 'clips9', 'effort9', 'disruption9']:
                data[key] = np.concatenate([all_paths[key], natural[key]], axis=0)
            u, y = sim.histories(data)
            x8, s8 = extract(u[:1, :400], y[:1, :401])
            first = np.r_[np.arange(9)*9, 81]
            x9, s9 = extract(u[first, :450], y[first, :451])
            x10, s10 = extract(u, y)
            for key, value in [('x8', x8[0]), ('s8', s8[0]), ('x9', x9), ('s9', s9), ('x10', x10), ('s10', s10),
                               ('prefix_pose', data['prefix']['pose']), ('prefix_u', data['prefix']['commands']),
                               ('suffix_pose', data['pose']), ('suffix_u', data['commands']), ('requested', data['requested']),
                               ('violations', data['violations']), ('clips', data['clips']), ('effort', data['effort']),
                               ('disruption', data['disruption'])] + [(k, data[k]) for k in [
                               'violations8', 'violations9', 'clips8', 'clips9', 'effort9', 'disruption9']]: fields[key].append(value)
            rows.append(dict(config=config, replicate=rep, kind=kind, label=KNOWN.index(kind) if kind in KNOWN else -1,
                             severity=w.severity, axis=w.axis, noise_rho=w.rho))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{k: np.asarray(v) for k, v in fields.items()})
    dump(path.with_suffix('.json'), rows)
    print('generated', split, config, len(rows), round(time.perf_counter()-start, 1), 's', flush=True)
    return str(path)


def prepare(workers):
    assert not (OUT/'freeze.json').exists()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(limited_config_data, split, c) for split in ['train', 'validation'] for c in CONFIGS[split]]
        for future in as_completed(futures): future.result()
    dump(OUT/'development_complete.json', dict(completed_utc=utc(), config_split=CONFIGS, source_hashes=source_hashes()))


def limited_config_data(split, config):
    with threadpool_limits(limits=1): return config_data(split, config)


def read_panel(split, stage):
    xx, ss, yy, meta = [], [], [], []
    for config in CONFIGS[split]:
        path = DATA/split/f'{config}.npz'
        with np.load(path) as d:
            x, score = d[f'x{stage}'], d[f's{stage}']
        rows = load(path.with_suffix('.json')); labels = np.array([r['label'] for r in rows])
        if stage > 8:
            count = x.shape[1]; labels = np.repeat(labels, count)
            x = x.reshape(-1, x.shape[-1]); score = score.reshape(-1, 4)
            meta.extend([{**r, 'branch': b} for r in rows for b in range(count)])
        else: meta.extend([{**r, 'branch': 0} for r in rows])
        xx.append(x); ss.append(score); yy.extend(labels)
    return np.concatenate(xx), np.concatenate(ss), np.asarray(yy), meta


def raw_predictions(model, x, scores):
    proba = model['forest'].predict_proba(x); rf = np.argmax(proba, axis=1)
    nearest = model['knn'].kneighbors(model['scaler'].transform(x), return_distance=True)[0].mean(1)
    physical = np.argmin(scores, axis=1)
    physical = np.where(scores[:, 0]-np.min(scores[:, 1:], axis=1) <= model['healthy_margin'], 0, physical)
    return dict(physics=(physical, np.min(scores, axis=1), softmax(-scores, axis=1)),
                forest_fit=(rf, np.min(scores, axis=1), proba), forest_knn=(rf, nearest, proba))


def decisions(raw, thresholds):
    pred, score, _ = raw
    return np.where(score > np.asarray(thresholds)[pred], -1, pred)


def metrics(y, prediction):
    y = np.asarray(y); p = np.asarray(prediction)
    known = y > 0; healthy = y == 0; unknown = y == -1
    recall = float(np.mean([np.mean(p[y == c] == c) for c in [1, 2, 3]])) if known.any() else None
    return dict(unknown_rejection=float(np.mean(p[unknown] == -1)) if unknown.any() else None,
                known_macro_recall=recall, healthy_false_alarm=float(np.mean(p[healthy] != 0)) if healthy.any() else None,
                known_abstention=float(np.mean(p[y >= 0] == -1)) if (y >= 0).any() else None,
                feasible=bool(recall is not None and recall >= .9 and np.mean(p[healthy] != 0) <= .05))


def fit():
    assert not (OUT/'freeze.json').exists()
    selections = {}; model_hashes = {}
    for stage in [8, 9, 10]:
        x, _, y, _ = read_panel('train', stage)
        rng = np.random.default_rng(SEED+stage)
        take = np.concatenate([rng.choice(np.flatnonzero(y == c), min(3000, int((y == c).sum())), replace=False) for c in range(4)])
        forest = ExtraTreesClassifier(n_estimators=128, min_samples_leaf=2, max_features=.8,
                                       random_state=SEED+stage, n_jobs=1).fit(x[take], y[take])
        scaler = StandardScaler().fit(x[take])
        scaler.scale_ = np.maximum(scaler.scale_, .02)
        small = np.concatenate([rng.choice(np.flatnonzero(y == c), min(600, int((y == c).sum())), replace=False) for c in range(4)])
        knn = NearestNeighbors(n_neighbors=5, algorithm='brute', n_jobs=1).fit(scaler.transform(x[small]))
        vx, vs, vy, meta = read_panel('validation', stage)
        margin = float(np.quantile(vs[vy == 0, 0]-np.min(vs[vy == 0, 1:], axis=1), .975))
        model = dict(forest=forest, scaler=scaler, knn=knn, thresholds={}, healthy_margin=margin)
        raw = raw_predictions(model, vx, vs)
        info = {}
        for decoder in DECODERS:
            prediction, novelty, _ = raw[decoder]
            trials = []
            for q in [.9, .95, .975, .99, .995, 1.0]:
                thresholds = [float(np.quantile(novelty[vy == c], q)) for c in range(4)]
                p = decisions(raw[decoder], thresholds); m = metrics(vy, p)
                trials.append(dict(quantile=q, thresholds=thresholds, metrics=m))
            feasible = [t for t in trials if t['metrics']['feasible']]
            best = max(feasible, key=lambda t:t['metrics']['unknown_rejection']) if feasible else max(
                trials, key=lambda t:t['metrics']['known_macro_recall']-t['metrics']['healthy_false_alarm'])
            model['thresholds'][decoder] = best['thresholds']
            chosen = decisions(raw[decoder], best['thresholds'])
            if stage == 8:
                by_branch = [dict(branch=0, metrics=metrics(vy, chosen))]
            else:
                branches = np.array([r['branch'] for r in meta])
                by_branch = [dict(branch=int(b), metrics=metrics(vy[branches == b], chosen[branches == b])) for b in np.unique(branches)]
            eligible = [r for r in by_branch if r['metrics']['feasible']]
            fixed = max(eligible, key=lambda r:r['metrics']['unknown_rejection']) if eligible else max(
                by_branch, key=lambda r:r['metrics']['known_macro_recall']-r['metrics']['healthy_false_alarm'])
            # Optimize actual fixed probes separately from the natural wait option.
            probe_rows = [r for r in by_branch if stage == 8 or r['branch'] < (9 if stage == 9 else 81)]
            eligible_probe = [r for r in probe_rows if r['metrics']['feasible']]
            probe = max(eligible_probe, key=lambda r:r['metrics']['unknown_rejection']) if eligible_probe else max(
                probe_rows, key=lambda r:r['metrics']['known_macro_recall']-r['metrics']['healthy_false_alarm'])
            info[decoder] = dict(calibration=best, calibration_trials=trials, best_branch=fixed, optimized_probe=probe, branches=by_branch)
        if stage == 8:
            scale = np.maximum(np.median(x[y == 0, :3], axis=0)*np.array([.02, .02, .03]), [.008, .008, .012])
            np.save(WORK/'forecast_scale.npy', scale)
        path = WORK/f'decoder_{stage}.pkl'
        with path.open('wb') as f: pickle.dump(model, f)
        model_hashes[path.name] = sha(path); selections[str(stage)] = info
        print('fit stage', stage, {d:info[d]['optimized_probe'] for d in DECODERS}, flush=True)
    dump(OUT/'selection.json', selections)
    dump(OUT/'fit_receipt.json', dict(fitted_utc=utc(), model_hashes=model_hashes,
                                     scale_sha256=sha(WORK/'forecast_scale.npy'), unknown_families_used_for_fit=[],
                                     proxy_unknowns=['quantized', 'held'], test_configurations_used=0))


def freeze():
    assert not (OUT/'freeze.json').exists()
    assert not (DATA/'test').exists(), 'Test panel must not exist before freeze.'
    fit_receipt = load(OUT/'fit_receipt.json')
    dump(OUT/'freeze.json', dict(frozen_utc=utc(), source_hashes=source_hashes(), config_split=CONFIGS,
                                final_unknowns=sim.KINDS[4:], fit_receipt_sha256=sha(OUT/'fit_receipt.json'),
                                selection_sha256=sha(OUT/'selection.json'), model_hashes=fit_receipt['model_hashes']))
    dump(OUT/'environment.json', dict(recorded_utc=utc(), packages=sorted(
        f'{d.metadata["Name"]}=={d.version}' for d in distributions())))


def verify_freeze():
    frozen = load(OUT/'freeze.json')
    assert source_hashes() == frozen['source_hashes']
    assert sha(OUT/'fit_receipt.json') == frozen['fit_receipt_sha256']
    assert sha(OUT/'selection.json') == frozen['selection_sha256']
    for name, digest in frozen['model_hashes'].items(): assert sha(WORK/name) == digest


def chosen_paths(d, rows, scale):
    n = len(rows); paths = {name:[] for name in ['eig', 'overlap', 'random0', 'random1', 'random2']}
    timings = {name:[] for name in paths}
    for i, row in enumerate(rows):
        prefix_u, prefix_y = d['prefix_u'][i], d['prefix_pose'][i]
        for method in ['eig', 'overlap']:
            a, t1 = select(Observation(prefix_u, prefix_y), method, scale)
            index = a*9
            u = np.concatenate([prefix_u, d['suffix_u'][i, index, :50]])
            y = np.concatenate([prefix_y, d['suffix_pose'][i, index, :50]])
            b, t2 = select(Observation(u, y), method, scale)
            paths[method].append(a*9+b); timings[method].append(t1+t2)
        for seed in range(3):
            rng = np.random.default_rng(np.random.SeedSequence([row['config'], row['replicate'], seed, SEED]))
            name = f'random{seed}'; paths[name].append(int(rng.integers(0, 81))); timings[name].append(0.)
    return {k:np.asarray(v) for k,v in paths.items()}, timings


def evaluate_config(config):
    with threadpool_limits(limits=1): return _evaluate_config(config)


def _evaluate_config(config):
    verify_freeze()
    path = Path(config_data('test', config))
    rows = load(path.with_suffix('.json')); y = np.array([r['label'] for r in rows])
    with np.load(path) as file: d = {k:file[k] for k in file.files}
    selections = load(OUT/'selection.json')
    model = {}
    for stage in [8, 9, 10]:
        with (WORK/f'decoder_{stage}.pkl').open('rb') as f: model[stage] = pickle.load(f)
    paths, timings = chosen_paths(d, rows, np.load(WORK/'forecast_scale.npy'))
    outputs = []; all_arrays = {}
    for decoder in DECODERS:
        raw = {}; pred = {}; prob = {}; novel = {}
        for stage in [8, 9, 10]:
            x = d[f'x{stage}']; scores = d[f's{stage}']
            shape = x.shape[:-1]
            result = raw_predictions(model[stage], x.reshape(-1, x.shape[-1]), scores.reshape(-1, 4))[decoder]
            raw[stage] = result
            pred[stage] = decisions(result, model[stage]['thresholds'][decoder]).reshape(shape)
            prob[stage] = result[2].reshape(*shape, 4)
            novel[stage] = result[1].reshape(shape)
        index = np.arange(len(rows))
        fixed2 = selections['10'][decoder]['optimized_probe']['branch']
        fixed1 = selections['9'][decoder]['optimized_probe']['branch']
        # Also include a classical fixed persistent-excitation reversal, unoptimized.
        selectors = dict(fixed=np.full(len(rows), fixed2), persistent=np.full(len(rows), 7*9+6), **paths)
        # The per-episode oracle uses ground truth; never supplied to a selector.
        oracle = np.array([np.flatnonzero(pred[10][i] == target)[0] if np.any(pred[10][i] == target)
                           else 81 for i,target in enumerate(y)])
        selectors['action_oracle'] = oracle
        variants = {'passive8': (pred[8], prob[8], novel[8], np.full(len(rows), -1), 8.),
                    'passive10': (pred[10][:, 81], prob[10][:, 81], novel[10][:, 81], np.full(len(rows), 81), 10.),
                    'fixed1': (pred[9][:, fixed1], prob[9][:, fixed1], novel[9][:, fixed1], np.full(len(rows), fixed1*9), 9.)}
        for selector, branch in selectors.items():
            variants[selector] = (pred[10][index, branch], prob[10][index, branch], novel[10][index, branch], branch, 10.)
        # Hindsight best universal fixed probe is only a descriptive upper bound.
        fixed_metrics = [metrics(y, pred[10][:, j]) for j in range(81)]
        all_arrays[f'{decoder}_all_decisions'] = pred[10]
        for selector, (prediction, probability, novelty, branch, end) in variants.items():
            m = metrics(y, prediction)
            chosen = np.maximum(branch, 0)
            effort = d['effort'][index, chosen].copy(); disruption = d['disruption'][index, chosen].copy()
            violation = d['violations'][index, chosen].copy(); clips = d['clips'][index, chosen].copy()
            if selector == 'passive8':
                effort[:] = 0; disruption[:] = 0
                violation = d['violations8'][:, 0]; clips = d['clips8'][:, 0]
            elif selector == 'fixed1':
                effort = d['effort9'][index, chosen]; disruption = d['disruption9'][index, chosen]
                violation = d['violations9'][index, chosen]; clips = d['clips9'][index, chosen]
            name = f'{decoder}__{selector}'
            all_arrays[name+'_prediction'] = prediction; all_arrays[name+'_proba'] = probability
            all_arrays[name+'_novelty'] = novelty; all_arrays[name+'_branch'] = branch
            outputs.append(dict(config=config, decoder=decoder, selector=selector, metrics=m, end_seconds=end,
                                mean_effort=float(effort.mean()), mean_disruption=float(disruption.mean()),
                                violations=int(violation.sum()), clipped_steps=int(clips.sum()),
                                selection_seconds=float(np.mean(timings.get(selector, [0.])))))
        dump(OUT/'per_config'/f'{config}_{decoder}_fixed_curves.json', fixed_metrics)
    all_arrays.update(y=y, config=np.full(len(y), config), kind=np.array([r['kind'] for r in rows]))
    p = OUT/'predictions'/f'{config}.npz'; p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **all_arrays)
    dump(OUT/'per_config'/f'{config}.json', outputs)
    print('evaluated', config, flush=True)
    return config


def evaluate(workers):
    verify_freeze(); start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate_config, c) for c in CONFIGS['test']]
        for f in as_completed(futures): f.result()
    verify_freeze()
    dump(OUT/'evaluation_complete.json', dict(completed_utc=utc(), wall_seconds=time.perf_counter()-start,
                                             test_configurations=len(CONFIGS['test']), freeze_sha256=sha(OUT/'freeze.json')))


def summarize():
    verify_freeze(); records = []
    for c in CONFIGS['test']: records.extend(load(OUT/'per_config'/f'{c}.json'))
    summary = []
    for decoder in DECODERS:
        for selector in sorted({r['selector'] for r in records}):
            group = [r for r in records if r['decoder'] == decoder and r['selector'] == selector]
            m = {key: float(np.mean([r['metrics'][key] for r in group])) for key in [
                'unknown_rejection', 'known_macro_recall', 'healthy_false_alarm', 'known_abstention']}
            m['feasible'] = m['known_macro_recall'] >= .9 and m['healthy_false_alarm'] <= .05
            row = dict(decoder=decoder, selector=selector, metrics=m, per_config=group)
            summary.append(row)
            print(decoder, selector, {k:round(v, 4) if isinstance(v,float) else v for k,v in m.items()}, flush=True)
    dump(OUT/'summary.json', summary)
    dump(OUT/'results.json', records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--stage', required=True,
        choices=['prepare', 'fit', 'freeze', 'evaluate', 'summarize'])
    parser.add_argument('--workers', type=int, default=4); args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.stage == 'prepare': prepare(args.workers)
        elif args.stage == 'fit': fit()
        elif args.stage == 'freeze': freeze()
        elif args.stage == 'evaluate': evaluate(args.workers)
        else: summarize()
