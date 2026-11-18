"""Separate unfair full-mechanism, longer-horizon identifiability reference.

This model is never loaded by the baseline experiment or its selectors.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import pickle
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import balanced_accuracy_score
from threadpoolctl import threadpool_limits
import simulator as sim
from diagnosis import extract
import study as s


def features(u, y):
    x, _ = extract(u, y)
    # Full trace support, not just a small summary: before/after and each probe.
    yy = y[:, :800].reshape(len(y), 80, 10, 3).mean(2)
    delta = np.diff(yy, axis=1)
    commands = u[:, :800].reshape(len(u), 80, 10, 2).mean(2)
    return np.c_[x, delta.reshape(len(y), -1), commands.reshape(len(y), -1)]


def make(config, reps):
    with threadpool_limits(limits=1):
        xs, ys, kinds, replicates = [], [], [], []
        for kind in sim.KINDS:
            for rep in range(reps):
                w = sim.world(config, rep, kind, duration=800)
                a = sim.run(w, kind, extended=True)
                u, y = sim.histories(a, end=800)
                xs.append(features(u, y)[0]); ys.append(int(kind not in s.KNOWN))
                kinds.append(kind); replicates.append(rep)
        return config, np.asarray(xs), np.asarray(ys), np.asarray(kinds), np.asarray(replicates)


def main(workers):
    s.verify_freeze()
    panels = {}
    for split in ['train', 'validation', 'test']:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            values = list(pool.map(make, s.CONFIGS[split], [10]*len(s.CONFIGS[split])))
        panels[split] = dict(x=np.concatenate([r[1] for r in values]), y=np.concatenate([r[2] for r in values]),
                             config=np.concatenate([np.full(len(r[2]), r[0]) for r in values]),
                             kind=np.concatenate([r[3] for r in values]), replicate=np.concatenate([r[4] for r in values]))
        print('oracle generated', split, len(panels[split]['y']), flush=True)
    train, valid, test = [panels[k] for k in ['train', 'validation', 'test']]
    choices = []
    for name in ['trees', 'svm']:
        model = ExtraTreesClassifier(n_estimators=256, max_features=.8, min_samples_leaf=1,
                                     random_state=s.SEED, n_jobs=1) if name == 'trees' else make_pipeline(
            StandardScaler(), SVC(C=10, class_weight='balanced', probability=True, random_state=s.SEED))
        model.fit(train['x'], train['y'])
        scores = model.predict_proba(valid['x'])[:, 1]
        trials = [(balanced_accuracy_score(valid['y'], scores >= t), t) for t in [.2, .3, .4, .5, .6, .7, .8]]
        accuracy, threshold = max(trials, key=lambda p:p[0])
        choices.append((accuracy, name, threshold, model))
    val_score, name, threshold, model = max(choices, key=lambda c:c[0])
    score = model.predict_proba(test['x'])[:, 1]; pred = score >= threshold
    correct_known = float(np.mean(~pred[test['y'] == 0])); correct_unknown = float(np.mean(pred[test['y'] == 1]))
    destination = s.OUT/'oracle'; destination.mkdir(exist_ok=True)
    np.savez_compressed(destination/'predictions.npz', **{k:v for k,v in test.items() if k != 'x'}, score=score, pred=pred)
    with (destination/'full_mechanism.pkl').open('wb') as f: pickle.dump(model, f)
    s.dump(destination/'result.json', dict(completed_utc=s.utc(), selected_model=name, threshold=threshold,
        validation_balanced_accuracy=float(val_score), known_acceptance=correct_known,
        unknown_rejection=correct_unknown, balanced_accuracy=float((correct_known+correct_unknown)/2),
        accuracy=float(np.mean(pred == test['y'])), passed_identifiability_gate=bool(np.mean(pred == test['y']) >= .9),
        extra_knowledge='Source training includes all final mechanism families; NEVER a fair policy comparator.',
        horizon_seconds=16, probe_seconds=8, case_count=len(pred), model_sha256=s.sha(destination/'full_mechanism.pkl')))
    s.verify_freeze()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--workers', type=int, default=4)
    with threadpool_limits(limits=1): main(parser.parse_args().workers)
