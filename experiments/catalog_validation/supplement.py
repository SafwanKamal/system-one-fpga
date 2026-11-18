"""Post-result conservative baseline audit, NOT part of frozen primary study.

Recent and worst-window residual alarms use existing features only. Their
thresholds/probes are selected on source validation, sealed before reading the
final panel in this script. The noise-transfer check tests future-noise optimism
of the original oracle, without training a new selector.
"""
from concurrent.futures import ProcessPoolExecutor
import argparse
import copy
import pickle
import time
import numpy as np
from threadpoolctl import threadpool_limits
import study as s
import simulator as sim
from diagnosis import extract


def residual_score(x, whole, rule):
    recent = (x[:, 12:24].reshape(-1, 4, 3)**2).mean(2)
    return (recent if rule == 'recent' else np.maximum(recent, whole)).min(1)


def supplemental():
    s.verify_freeze()
    dest = s.OUT/'supplement'; dest.mkdir(exist_ok=True)
    vx, vs, vy, meta = s.read_panel('validation', 10)
    with (s.WORK/'decoder_10.pkl').open('rb') as f: model = pickle.load(f)
    prediction = model['forest'].predict(vx)
    branches = np.array([r['branch'] for r in meta]); fitted = {}
    for rule in ['recent', 'worst_window']:
        score = residual_score(vx, vs, rule); trials = []
        for q in [.9, .95, .975, .99, .995, 1.]:
            thresholds = np.array([np.quantile(score[vy == c], q) for c in range(4)])
            p = np.where(score > thresholds[prediction], -1, prediction)
            trials.append(dict(q=q, thresholds=thresholds.tolist(), metrics=s.metrics(vy, p)))
        feasible = [r for r in trials if r['metrics']['feasible']]
        fit = max(feasible, key=lambda r:r['metrics']['unknown_rejection']) if feasible else max(
            trials, key=lambda r:r['metrics']['known_macro_recall']-r['metrics']['healthy_false_alarm'])
        thresholds = np.array(fit['thresholds']); p = np.where(score > thresholds[prediction], -1, prediction)
        curves = [dict(branch=b, metrics=s.metrics(vy[branches == b], p[branches == b])) for b in range(81)]
        valid = [r for r in curves if r['metrics']['feasible']]
        probe = max(valid, key=lambda r:r['metrics']['unknown_rejection']) if valid else max(
            curves, key=lambda r:r['metrics']['known_macro_recall']-r['metrics']['healthy_false_alarm'])
        fitted[rule] = dict(calibration=fit, fixed_probe=probe, trials=trials)
    s.dump(dest/'source_only_freeze.json', dict(frozen_utc=s.utc(), source_sha256=s.sha(__file__),
        primary_freeze_sha256=s.sha(s.OUT/'freeze.json'), source_validation_only=True,
        status='Post-result baseline audit. Not preregistered with the primary experiment.', models=fitted))
    rows = []; arrays = {}
    for rule, fit in fitted.items():
        for c in s.CONFIGS['test']:
            with np.load(s.DATA/'test'/f'{c}.npz') as d:
                x = d['x10']; whole = d['s10']; shape = x.shape[:2]
                pred = model['forest'].predict(x.reshape(-1, x.shape[-1])).reshape(shape)
                score = residual_score(x.reshape(-1,x.shape[-1]), whole.reshape(-1,4), rule).reshape(shape)
            truth = np.load(s.OUT/'predictions'/f'{c}.npz')
            y = truth['y']; p = np.where(score > np.array(fit['calibration']['thresholds'])[pred], -1, pred)
            selectors = dict(fixed=np.full(len(y), fit['fixed_probe']['branch']), passive10=np.full(len(y), 81),
                             persistent=np.full(len(y), 7*9+6),
                             eig=truth['forest_fit__eig_branch'], overlap=truth['forest_fit__overlap_branch'])
            selectors['action_oracle'] = np.array([np.flatnonzero(p[i] == target)[0] if np.any(p[i] == target)
                                                  else 81 for i,target in enumerate(y)])
            for name, branch in selectors.items():
                selected = p[np.arange(len(y)), branch]
                arrays[f'{rule}_{c}_{name}'] = selected
                rows.append(dict(rule=rule, config=c, selector=name, metrics=s.metrics(y, selected)))
    np.savez_compressed(dest/'predictions.npz', **arrays)
    s.dump(dest/'results.json', rows)
    for rule in fitted:
        for selector in ['passive10', 'fixed', 'persistent', 'eig', 'overlap', 'action_oracle']:
            rr = [r['metrics'] for r in rows if r['rule'] == rule and r['selector'] == selector]
            print(rule, selector, {k:round(float(np.mean([r[k] for r in rr])),4) for k in [
                'unknown_rejection','known_macro_recall','healthy_false_alarm']}, flush=True)


def noise_config(config):
    with threadpool_limits(limits=1):
        with np.load(s.OUT/'predictions'/f'{config}.npz') as f: original = {k:f[k] for k in f.files}
        meta = s.load((s.DATA/'test'/f'{config}.json'))
        selection = s.load(s.OUT/'selection.json')['10']
        with (s.WORK/'decoder_10.pkl').open('rb') as f: model = pickle.load(f)
        records = []; arrays = {}; start = time.perf_counter()
        for draw in [1, 2]:
            all_x, all_scores = [], []
            for row in meta:
                w = sim.world(config, row['replicate'], row['kind'])
                rng = np.random.default_rng(np.random.SeedSequence([config, row['replicate'], draw, 772]))
                innovations = rng.normal(size=(100, 3))*w.sigma
                for step in range(401, 501):
                    w.noise[step] = w.rho*w.noise[step-1]+np.sqrt(1-w.rho*w.rho)*innovations[step-401]
                data = sim.run(w, row['kind'])
                natural = sim.run(w, row['kind'], natural=True)
                for key in ['pose','commands']: data[key] = np.concatenate([data[key], natural[key]])
                u, y = sim.histories(data); x, score = extract(u, y)
                all_x.append(x); all_scores.append(score)
            x = np.asarray(all_x); scores = np.asarray(all_scores)
            raw = s.raw_predictions(model, x.reshape(-1,x.shape[-1]), scores.reshape(-1,4))['forest_fit']
            p = s.decisions(raw, model['thresholds']['forest_fit']).reshape(x.shape[:2])
            yy = original['y']; index = np.arange(len(yy))
            oracle = np.array([np.flatnonzero(p[i] == target)[0] if np.any(p[i] == target)
                               else 81 for i,target in enumerate(yy)])
            choices = dict(fixed=np.full(len(yy), selection['forest_fit']['optimized_probe']['branch']),
                           transferred_oracle=original['forest_fit__action_oracle_branch'],
                           new_noise_oracle=oracle)
            for name, branch in choices.items():
                prediction = p[index, branch]
                arrays[f'{draw}_{name}'] = prediction
                records.append(dict(config=config, draw=draw, selector=name, metrics=s.metrics(yy, prediction)))
        np.savez_compressed(s.OUT/'supplement'/f'noise_{config}.npz', **arrays)
        print('noise transfer', config, round(time.perf_counter()-start, 1), 's', flush=True)
        return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--noise', action='store_true')
    parser.add_argument('--workers', type=int, default=4); args = parser.parse_args()
    with threadpool_limits(limits=1):
        if not args.noise: supplemental()
        else:
            s.verify_freeze()
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                results = [r for batch in pool.map(noise_config, s.CONFIGS['test']) for r in batch]
            s.dump(s.OUT/'supplement/noise_transfer.json', dict(completed_utc=s.utc(),
                source_sha256=s.sha(__file__), exploratory=True, results=results))
            s.verify_freeze()
