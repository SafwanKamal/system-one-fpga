"""Oracle tie-break sensitivity. Exploratory, never a deployable selector."""
from concurrent.futures import ProcessPoolExecutor
import pickle
import numpy as np
from threadpoolctl import threadpool_limits
import simulator as sim
from diagnosis import extract
import study as s


def choices(pred, margin, prob, labels):
    answer = []
    for i, target in enumerate(labels):
        if target == -1: answer.append(int(np.argmax(margin[i])))
        else:
            good = pred[i] == target
            answer.append(int(np.argmax(np.where(good, prob[i, :, target], -1))) if good.any() else 81)
    return np.asarray(answer)


def config(config):
    with threadpool_limits(limits=1):
        with (s.WORK/'decoder_10.pkl').open('rb') as f: model = pickle.load(f)
        with np.load(s.DATA/'test'/f'{config}.npz') as d:
            x = d['x10']; score = d['s10'].min(2)
        with np.load(s.OUT/'predictions'/f'{config}.npz') as d:
            labels = d['y']; base_pred = d['forest_fit_all_decisions']
        probability = model['forest'].predict_proba(x.reshape(-1,x.shape[-1])).reshape(len(x),82,4)
        threshold = np.array(model['thresholds']['forest_fit'])
        margin = score/threshold[probability.argmax(2)]
        index = np.arange(len(labels)); original_choice = choices(base_pred, margin, probability, labels)
        chosen_fixed = s.load(s.OUT/'selection.json')['10']['forest_fit']['optimized_probe']['branch']
        metadata = s.load(s.DATA/'test'/f'{config}.json'); results = []; arrays = {}
        history = [(base_pred, margin, probability)]
        for draw in [1, 2]:
            features, scores = [], []
            for row in metadata:
                w = sim.world(config, row['replicate'], row['kind'])
                rng = np.random.default_rng(np.random.SeedSequence([config,row['replicate'],draw,772]))
                innovation = rng.normal(size=(100,3))*w.sigma
                for t in range(401,501): w.noise[t] = w.rho*w.noise[t-1]+np.sqrt(1-w.rho*w.rho)*innovation[t-401]
                a = sim.run(w,row['kind']); natural = sim.run(w,row['kind'],natural=True)
                for key in ['pose','commands']: a[key] = np.concatenate([a[key],natural[key]])
                u, y = sim.histories(a); xx, ss = extract(u,y); features.append(xx); scores.append(ss.min(1))
            x = np.asarray(features); score = np.asarray(scores)
            prob = model['forest'].predict_proba(x.reshape(-1,x.shape[-1])).reshape(len(x),82,4)
            raw = prob.argmax(2); mm = score/threshold[raw]; pred = np.where(mm > 1, -1, raw)
            history.append((pred,mm,prob))
            policies = dict(fixed=np.full(len(labels),chosen_fixed), margin_transfer=original_choice)
            if draw == 2:
                # Uses labels and two earlier noise realizations, NOT current noise.
                previous_good = ((history[0][0] == labels[:,None]).astype(float)+
                                 (history[1][0] == labels[:,None]).astype(float))
                tie = np.where(labels[:,None] == -1,
                    np.log(np.maximum(history[0][1],1e-8))+np.log(np.maximum(history[1][1],1e-8)),
                    history[0][2].max(2)+history[1][2].max(2))
                trained = np.argmax(previous_good+.001*np.clip(tie,-20,20),axis=1)
                policies['two_noise_trained_oracle'] = trained
            for name, branch in policies.items():
                pp = pred[index,branch]; arrays[f'{draw}_{name}'] = pp
                results.append(dict(config=config,draw=draw,selector=name,metrics=s.metrics(labels,pp)))
        np.savez_compressed(s.OUT/'supplement'/f'margin_{config}.npz', **arrays)
        print('margin sensitivity',config,flush=True)
        return results


if __name__ == '__main__':
    s.verify_freeze()
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = [row for batch in pool.map(config,s.CONFIGS['test']) for row in batch]
    s.dump(s.OUT/'supplement/margin_sensitivity.json',dict(completed_utc=s.utc(),
        source_sha256=s.sha(__file__),exploratory=True,results=results))
    s.verify_freeze()
