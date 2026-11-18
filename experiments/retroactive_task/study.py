"""Raw-signal archives with tasks revealed only after archive commitment.

All collection-time transformations are ordinary baselines. See PROTOCOL.md.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import lzma
from pathlib import Path
import pickle
import struct
import sys
import time
import zipfile

import numpy as np
from scipy import fft, signal
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "build/research/retroactive_task"
OUT = ROOT / "results/research/retroactive_task/pilot_v1"
TRAIN = [101, 102, 103, 104]
TEST = [105, 106, 107, 108]
SUBJECTS = TRAIN + TEST
TASKS = {5: "running", 6: "cycling", 12: "ascending_stairs"}
T, C, HZ = 512, 18, 100
COLS = [4, 5, 6, 10, 11, 12, 21, 22, 23, 27, 28, 29, 38, 39, 40, 44, 45, 46]
BUDGETS = [1024, 2048, 4096, 8192]
SEED = 20261116
HEADER = struct.Struct("<4sBBHHHdfII")
DATA_SHA = "6c2282b5b52775cd0588d450d10a315260c94fa3228b9fe453f48c47fda106f4"


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf8")


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def fill(x):
    x = np.asarray(x, np.float32).copy()
    for c in range(x.shape[1]):
        good = np.isfinite(x[:, c])
        if not good.all():
            x[:, c] = np.interp(np.arange(len(x)), np.flatnonzero(good), x[good, c]) if good.any() else 0
    return x


def stats_features(x):
    """Broad fixed feature bank, specified before any future labels are revealed."""
    missing = np.mean(~np.isfinite(x), axis=0)
    x = fill(x)
    centered = x - x.mean(0)
    power = np.abs(fft.rfft(centered, axis=0)) ** 2 / len(x) ** 2
    frequency = fft.rfftfreq(len(x), 1 / HZ)
    total = np.maximum(power.sum(0), 1e-12)
    distribution = power / total
    features = [x.mean(0), x.std(0), x.min(0), x.max(0), np.sqrt(np.mean(x*x, 0)),
                np.mean(np.abs(np.diff(x, axis=0)), 0),
                np.mean(np.diff(np.signbit(centered), axis=0), 0),
                *np.quantile(x, [.1, .5, .9], axis=0),
                frequency[np.argmax(power[1:], axis=0) + 1],
                -np.sum(distribution * np.log(np.maximum(distribution, 1e-12)), axis=0), missing]
    bounds = [0, .5, 1, 2, 4, 8, 16, 32, 50.01]
    features += [np.log1p(power[(frequency >= a) & (frequency < b)].sum(0)) for a, b in zip(bounds[:-1], bounds[1:])]
    return np.concatenate(features).astype(np.float32)


def rich_features(x):
    # Newly computed after label reveal for waveform archives. Phase-preserving
    # coefficients are not available to feature-only archives.
    return np.concatenate([stats_features(x), fft.dct(fill(x), axis=0, norm="ortho")[:64].ravel()]).astype(np.float32)


def custodian_labels(labels, timing):
    majority, purity = [], []
    for row in labels:
        values, counts = np.unique(row, return_counts=True)
        k = np.argmax(counts)
        majority.append(int(values[k])); purity.append(float(counts[k] / T))
    majority = np.asarray(majority, np.int16)
    purity = np.asarray(purity)
    eligible = (purity >= .95) & (majority != 0) & timing
    # Even a minority future-category sample excludes a collection-training window.
    known = eligible & ~np.isin(labels, list(TASKS)).any(1)
    return majority, purity, eligible, known


def prepare():
    """Data custodian: signals and future labels are written to separate files."""
    OUT.mkdir(parents=True, exist_ok=True)
    archive = WORK / "data/PAMAP2_Dataset.zip"
    assert sha(archive) == DATA_SHA
    z = zipfile.ZipFile(archive)
    inventory, known_x, known_y, known_subject = [], [], [], []
    for subject in SUBJECTS:
        member = f"PAMAP2_Dataset/Protocol/subject{subject}.dat"
        a = np.loadtxt(z.open(member), usecols=[0, 1, *COLS], dtype=np.float64)
        original_rows = len(a)
        n = len(a) // T
        a = a[:n*T]
        timestamps = a[:, 0].reshape(n, T)
        labels = a[:, 1].astype(np.int16).reshape(n, T)
        x = a[:, 2:].astype(np.float32).reshape(n, T, C)
        timing = np.max(np.abs(np.diff(timestamps, axis=1) - 1/HZ), axis=1) < 1e-5
        majority, purity, eligible, known = custodian_labels(labels, timing)
        signal_path = WORK / "signals" / f"s{subject}.npz"
        vault_path = WORK / "vault" / f"s{subject}.npz"
        signal_path.parent.mkdir(exist_ok=True)
        vault_path.parent.mkdir(exist_ok=True)
        np.savez_compressed(signal_path, x=x, start=timestamps[:, 0])
        np.savez_compressed(vault_path, y=majority, eligible=eligible, purity=purity, timing=timing)
        if subject in TRAIN:
            fx = np.stack([stats_features(window) for window in x[known]])
            known_x.append(fx); known_y.append(majority[known]); known_subject.append(np.full(len(fx), subject))
        inventory.append(dict(subject=subject, windows=n, source_rows=original_rows, unused_tail_rows=original_rows-len(a),
                              eligible_post_reveal=int(eligible.sum()), timing_invalid=int((~timing).sum()),
                              ambiguous_or_transition=int((~eligible).sum()), missing_fraction=float(np.mean(~np.isfinite(x))),
                              known_training=int(known.sum()) if subject in TRAIN else 0,
                              source_member_sha256=hashlib.sha256(z.read(member)).hexdigest()))
        print("prepared",subject,n,"windows",flush=True)
    np.savez_compressed(WORK / "known_training.npz", x=np.concatenate(known_x), y=np.concatenate(known_y), subject=np.concatenate(known_subject))
    dump(OUT / "inventory.json", inventory)
    dump(OUT / "source.json", dict(url="https://archive.ics.uci.edu/ml/machine-learning-databases/00231/PAMAP2_Dataset.zip",
                                   sha256=DATA_SHA, subjects=SUBJECTS, train=TRAIN, test=TEST,
                                   channels=COLS, window_samples=T, sample_rate=HZ,
                                   custodian_only_future_categories=TASKS, created_utc=utc()))


def fit_collection():
    from sklearn.decomposition import PCA
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.preprocessing import StandardScaler
    data = np.load(WORK / "known_training.npz")
    assert not np.isin(data["y"], list(TASKS)).any()
    models = WORK / "collection_models"
    models.mkdir(exist_ok=True)
    scaler = StandardScaler().fit(data["x"])
    x = scaler.transform(data["x"])
    pca = PCA(n_components=64, svd_solver="full").fit(x)
    for k in [16, 32, 64]:
        np.savez(models / f"pca{k}.npz", mean=scaler.mean_.astype(np.float32), scale=scaler.scale_.astype(np.float32),
                 pca_mean=pca.mean_.astype(np.float32), components=pca.components_[:k].astype(np.float32))
    classifier = ExtraTreesClassifier(n_estimators=96, min_samples_leaf=4, max_depth=16,
                                      max_features=.7, n_jobs=2, random_state=SEED).fit(data["x"], data["y"])
    with (models / "known_classifier.pkl").open("wb") as f:
        pickle.dump(classifier, f)
    # Scales define task-blind normalized reconstruction error, not an encoder
    # clipping range. Unseen signal amplitudes are encoded per-window.
    scales = np.maximum(np.median(data["x"][:,C:2*C], axis=0), .01).astype(np.float32)
    np.save(models / "scales.npy", scales)
    shared = {f"pca{k}": (models/f"pca{k}.npz").stat().st_size for k in [16,32,64]}
    shared.update(known_scores=(models/"known_classifier.pkl").stat().st_size,
                  statistics=0, raw32=0, lossless_zlib=0, lossless_lzma=0)
    for budget in BUDGETS:
        for family in ["downsample", "dct", "generic"]:
            shared[f"{family}_{budget}"] = (models/"scales.npy").stat().st_size
    dump(OUT / "collection_fit.json", dict(training_windows=len(x), known_classes=classifier.classes_.tolist(),
                                            future_categories_in_fit=0, feature_dimension=data["x"].shape[1],
                                            shared_bytes=shared, model_hashes={p.name:sha(p) for p in models.iterdir()},
                                            fitted_utc=utc()))


def xor_bytes(x):
    u = np.ascontiguousarray(x, dtype="<f4").view("<u4")
    d = u ^ np.vstack([np.zeros((1, C),np.uint32), u[:-1]])
    return d.T.copy().view(np.uint8).reshape(C, len(x), 4).transpose(2,0,1).tobytes()


def unxor_bytes(b, n):
    d = np.frombuffer(b,np.uint8).reshape(4,C,n).transpose(1,2,0).copy().view("<u4").reshape(C,n).T
    return np.bitwise_xor.accumulate(d,axis=0).astype("<u4").view("<f4")


def scalar_encode(a, bits):
    if bits == 16:
        return np.clip(a,-65504,65504).astype("<f2").tobytes()
    lo = a.min(0).astype(np.float32)
    scale = ((a.max(0)-lo)/((1<<bits)-1)).astype(np.float32)
    q = np.floor((a-lo)/np.where(scale>0,scale,1)+.5).clip(0,(1<<bits)-1).astype(np.uint8).ravel()
    if bits == 4:
        if len(q)%2:q=np.r_[q,np.uint8(0)]
        payload=(q[::2] | (q[1::2]<<4)).tobytes()
    else:payload=q.tobytes()
    return lo.astype("<f4").tobytes()+scale.astype("<f4").tobytes()+payload


def scalar_decode(b, n, bits):
    if bits == 16:return np.frombuffer(b,"<f2").astype(np.float32).reshape(n,C)
    lo=np.frombuffer(b[:C*4],"<f4");scale=np.frombuffer(b[C*4:C*8],"<f4")
    q=np.frombuffer(b[C*8:],np.uint8)
    if bits==4:q=np.column_stack([q&15,q>>4]).ravel()
    return lo+q[:n*C].reshape(n,C).astype(np.float32)*scale


def frame(kind, bits, keep, start, mask, payload):
    return HEADER.pack(b"RTA1",kind,bits,T,C,keep,float(start),1/HZ,len(mask),len(payload))+mask+payload


def waveform_frame(x, start, kind, bits=32, keep=T, lossless=None):
    mask=np.packbits(~np.isfinite(x),bitorder="little").tobytes()
    import zlib
    mask=zlib.compress(mask,9)
    a=fill(x)
    if kind==0:body=a.astype("<f4").tobytes()
    elif kind in [1,2]:
        compressor=(lambda b:zlib.compress(b,9)) if kind==1 else (lambda b:lzma.compress(b,preset=3))
        options=[bytes([0])+compressor(a.astype("<f4").tobytes()), bytes([1])+compressor(xor_bytes(a))]
        body=min(options,key=len)
    elif kind==3:
        small=signal.resample_poly(a,1,T//keep,axis=0) if keep<T else a
        body=zlib.compress(scalar_encode(small,bits),6)
    elif kind==4:
        coefficients=fft.dct(a,axis=0,norm="ortho")[:keep]
        body=zlib.compress(scalar_encode(coefficients,bits),6)
    else:raise ValueError(kind)
    return frame(kind,bits,keep,start,mask,body)


def decode_frame(b):
    import zlib
    magic,kind,bits,n,c,keep,start,dt,msize,psize=HEADER.unpack_from(b)
    assert magic==b"RTA1" and n==T and c==C
    assert len(b)==HEADER.size+msize+psize
    payload=b[HEADER.size+msize:]
    if kind>=5:
        return np.frombuffer(payload,"<f2").astype(np.float32),start
    if kind==0:x=np.frombuffer(payload,"<f4").copy().reshape(T,C)
    elif kind in [1,2]:
        decoded=zlib.decompress(payload[1:]) if kind==1 else lzma.decompress(payload[1:])
        x=np.frombuffer(decoded,"<f4").copy().reshape(T,C) if payload[0]==0 else unxor_bytes(decoded,T)
    elif kind==3:
        small=scalar_decode(zlib.decompress(payload),keep,bits)
        x=signal.resample_poly(small,T//keep,1,axis=0)[:T] if keep<T else small
    elif kind==4:
        coefficients=np.zeros((T,C),np.float32)
        coefficients[:keep]=scalar_decode(zlib.decompress(payload),keep,bits)
        x=fft.idct(coefficients,axis=0,norm="ortho")
    else:raise ValueError(kind)
    mask=np.unpackbits(np.frombuffer(zlib.decompress(b[HEADER.size:HEADER.size+msize]),np.uint8),bitorder="little")[:T*C].reshape(T,C)
    x=np.asarray(x,np.float32).copy();x[mask.astype(bool)]=np.nan
    return x,start


def candidates(x,start,scales):
    reference=fill(x)
    output={"downsample":[],"dct":[]}
    for keep in [T,T//2,T//4,T//8,T//16,T//32]:
        for bits in [4,8,16]:
            b=waveform_frame(x,start,3,bits,keep)
            if len(b)+4<=max(BUDGETS):
                restored,_=decode_frame(b)
                loss=float(np.mean(((fill(restored)-reference)/scales)**2))
                output["downsample"].append((loss,b))
    for keep in [4,8,16,32,64,128,256]:
        for bits in [4,8,16]:
            b=waveform_frame(x,start,4,bits,keep)
            if len(b)+4<=max(BUDGETS):
                restored,_=decode_frame(b)
                loss=float(np.mean(((fill(restored)-reference)/scales)**2))
                output["dct"].append((loss,b))
    output["generic"]=output["downsample"]+output["dct"]
    return output


def collection_worker(subject):
    """Signal-only API. This function never opens the label vault."""
    with threadpool_limits(limits=1):
        return _collection_worker(subject)


def _collection_worker(subject):
    data=np.load(WORK/"signals"/f"s{subject}.npz")
    models=WORK/"collection_models"
    scales=np.load(models/"scales.npy")
    pcas={k:dict(np.load(models/f"pca{k}.npz")) for k in [16,32,64]}
    with (models/"known_classifier.pkl").open("rb") as f:classifier=pickle.load(f)
    classifier.n_jobs=1
    views=["raw32","lossless_zlib","lossless_lzma","statistics","pca16","pca32","pca64","known_scores"]
    views += [f"{family}_{budget}" for family in ["downsample","dct","generic"] for budget in BUDGETS]
    paths={v:OUT/"archives"/v/f"s{subject}.bin" for v in views}
    for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True)
    files={v:p.open("wb") for v,p in paths.items()}
    for f in files.values():f.write(b"RTAHIST1")
    profile={v:dict(windows=0,max_frame_bytes=0,mse_sum=0.0,configurations={}) for v in views}
    begin=time.perf_counter()
    try:
        for i,(x,start) in enumerate(zip(data["x"],data["start"])):
            fx=stats_features(x)
            representations={"raw32":waveform_frame(x,start,0),
                             "lossless_zlib":waveform_frame(x,start,1),
                             "lossless_lzma":waveform_frame(x,start,2),
                             "statistics":frame(5,16,len(fx),start,b"",fx.astype("<f2").tobytes())}
            for k,m in pcas.items():
                embedding=((fx-m["mean"])/m["scale"]-m["pca_mean"])@m["components"].T
                representations[f"pca{k}"]=frame(6,16,k,start,b"",embedding.astype("<f2").tobytes())
            posteriors=classifier.predict_proba(fx[None])[0]
            representations["known_scores"]=frame(7,16,len(posteriors),start,b"",posteriors.astype("<f2").tobytes())
            options=candidates(x,start,scales)
            losses={}
            for family,items in options.items():
                for budget in BUDGETS:
                    feasible=[item for item in items if len(item[1])+4<=budget]
                    if not feasible:raise ValueError((subject,i,family,budget,"no feasible frame"))
                    loss,b=min(feasible,key=lambda item:(item[0],len(item[1])))
                    view=f"{family}_{budget}"
                    representations[view]=b;losses[view]=loss
            for view,b in representations.items():
                files[view].write(struct.pack("<I",len(b))+b)
                row=profile[view];row["windows"]+=1;row["max_frame_bytes"]=max(row["max_frame_bytes"],len(b)+4)
                row["mse_sum"]+=losses.get(view,0)
                _,kind,bits,_,_,keep,*_=HEADER.unpack_from(b)
                key=f"{kind}:{bits}:{keep}";row["configurations"][key]=row["configurations"].get(key,0)+1
            if i%100==0:print("collect",subject,i,"/",len(data["x"]),flush=True)
    finally:
        for f in files.values():f.close()
    for view,path in paths.items():
        profile[view].update(bytes=path.stat().st_size,sha256=sha(path),mean_normalized_mse=profile[view]["mse_sum"]/profile[view]["windows"])
    dump(OUT/"collection"/f"s{subject}.json",dict(subject=subject,profiles=profile,wall_seconds=time.perf_counter()-begin))
    return subject


def collect(workers):
    assert not (OUT/"label_reveal.json").exists(),"Cannot alter archives after reveal; use a new revision."
    begin=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(collection_worker,s):s for s in SUBJECTS}
        for f in as_completed(jobs):print("sealed subject",f.result(),flush=True)
    inventory=[]
    for path in sorted((OUT/"archives").glob("*/*.bin")):
        inventory.append(dict(path=str(path.relative_to(OUT)),bytes=path.stat().st_size,sha256=sha(path)))
    dump(OUT/"archive_commit.json",dict(committed_utc=utc(),archives=inventory,archive_count=len(inventory),
                                        collection_wall_seconds=time.perf_counter()-begin,
                                        labels_revealed=False,code_sha256=sha(__file__)))


def iter_archive(path):
    with Path(path).open("rb") as f:
        assert f.read(8)==b"RTAHIST1"
        while True:
            size=f.read(4)
            if not size:break
            assert len(size)==4
            b=f.read(struct.unpack("<I",size)[0])
            yield b


def verify_commit():
    commit=load(OUT/"archive_commit.json")
    for r in commit["archives"]:
        p=OUT/r["path"]
        assert p.stat().st_size==r["bytes"] and sha(p)==r["sha256"],r["path"]
    return commit


def reveal():
    commit=verify_commit()
    assert not (OUT/"label_reveal.json").exists()
    # The learning stage is gated on this receipt; it does not modify archives.
    dump(OUT/"label_reveal.json",dict(revealed_utc=utc(),archive_commit_sha256=sha(OUT/"archive_commit.json"),
                                      archive_committed_utc=commit["committed_utc"],future_categories=TASKS,
                                      verified_archives=len(commit["archives"]),training_subjects=TRAIN,test_subjects=TEST))


def decode_features(view,subject):
    path=OUT/"archives"/view/f"s{subject}.bin"
    a,b,starts=[],[],[]
    for frame_bytes in iter_archive(path):
        x,start=decode_frame(frame_bytes);starts.append(start)
        if x.ndim==1:a.append(x)
        else:a.append(stats_features(x));b.append(rich_features(x))
    arrays={"stats":np.stack(a)}
    if b:arrays["rich"]=np.stack(b)
    return arrays,np.asarray(starts)


def score_model(model, x):
    if hasattr(model,"predict_proba"):return model.predict_proba(x)[:,1]
    return model.decision_function(x)


def model_spec(name,seed):
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    if name=="trees":return ExtraTreesClassifier(n_estimators=64,min_samples_leaf=2,max_features=.7,
                                                  n_jobs=1,random_state=seed,class_weight="balanced")
    return make_pipeline(StandardScaler(),SVC(C=10,kernel="rbf",class_weight="balanced"))


def evaluate_worker(view):
    with threadpool_limits(limits=1):return _evaluate_worker(view)


def _evaluate_worker(view):
    from sklearn.metrics import f1_score,balanced_accuracy_score,precision_score,recall_score,average_precision_score
    assert (OUT/"label_reveal.json").exists()
    xdata,ydata,subjectdata={},[],[]
    offsets={}
    for s in SUBJECTS:
        arrays,starts=decode_features(view,s)
        # This is the FIRST downstream-learning access to future labels.
        labels=np.load(WORK/"vault"/f"s{s}.npz")
        eligible=labels["eligible"]
        assert len(starts)==len(eligible)
        for feature,x in arrays.items():xdata.setdefault(feature,[]).append(x[eligible])
        ydata.append(labels["y"][eligible]);subjectdata.append(np.full(int(eligible.sum()),s))
        offsets[s]=int(eligible.sum())
    xdata={k:np.concatenate(v) for k,v in xdata.items()}
    labels=np.concatenate(ydata);people=np.concatenate(subjectdata)
    training=np.isin(people,TRAIN);testing=np.isin(people,TEST)
    result=[]
    for task,name in TASKS.items():
        y=(labels==task).astype(int)
        trials=[]
        for feature,x in xdata.items():
            for learner in ["trees","svm"]:
                oof=np.zeros(int(training.sum()))
                tx=x[training];ty=y[training];ts=people[training]
                for held in TRAIN:
                    fit=ts!=held;valid=~fit
                    model=model_spec(learner,SEED+task+held)
                    model.fit(tx[fit],ty[fit]);oof[valid]=score_model(model,tx[valid])
                thresholds=[.3,.5,.7] if learner=="trees" else [-.5,0,.5]
                for threshold in thresholds:
                    scores=[f1_score(ty[ts==s],oof[ts==s]>=threshold,zero_division=0) for s in TRAIN]
                    trials.append(dict(feature=feature,learner=learner,threshold=threshold,cv_f1=float(np.mean(scores))))
        best=max(trials,key=lambda r:r["cv_f1"])
        x=xdata[best["feature"]]
        model=model_spec(best["learner"],SEED+task)
        model.fit(x[training],y[training]);scores=score_model(model,x[testing]);pred=scores>=best["threshold"]
        test_y=y[testing];test_subjects=people[testing]
        per_person=[]
        for s in TEST:
            take=test_subjects==s;yy=test_y[take];pp=pred[take];ss=scores[take]
            valid=bool(yy.any() and (~yy.astype(bool)).any())
            per_person.append(dict(subject=s,n=int(take.sum()),positive_n=int(yy.sum()),eligible=valid,
                                   f1=float(f1_score(yy,pp,zero_division=0)),
                                   balanced_accuracy=float(balanced_accuracy_score(yy,pp)),
                                   precision=float(precision_score(yy,pp,zero_division=0)),
                                   recall=float(recall_score(yy,pp,zero_division=0)),
                                   ap=float(average_precision_score(yy,ss)) if yy.any() else None))
        valid=[r for r in per_person if r["eligible"]]
        macro={k:float(np.mean([r[k] for r in valid])) for k in ["f1","balanced_accuracy","precision","recall","ap"]}
        result.append(dict(view=view,task=task,task_name=name,selected=best,cv_trials=trials,
                           per_person=per_person,macro=macro,test_people=len(valid)))
        path=OUT/"predictions"/f"{view}_{task}.npz";path.parent.mkdir(exist_ok=True)
        np.savez_compressed(path,y=test_y,score=scores,pred=pred,subject=test_subjects)
        print("evaluated",view,name,round(macro["f1"],4),flush=True)
    dump(OUT/"evaluations"/f"{view}.json",result)
    return view


def evaluate(workers):
    verify_commit()
    views=sorted(p.name for p in (OUT/"archives").iterdir() if p.is_dir())
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(evaluate_worker,v):v for v in views}
        for f in as_completed(jobs):print("finished evaluation",f.result(),flush=True)
    verify_commit()
    results=[]
    for v in views:results.extend(load(OUT/"evaluations"/f"{v}.json"))
    dump(OUT/"results.json",results)
    dump(OUT/"evaluation_complete.json",dict(completed_utc=utc(),views=len(views),tasks=len(TASKS),
                                             unchanged_archive_commit_sha256=sha(OUT/"archive_commit.json"),
                                             code_sha256=sha(__file__)))


def summarize():
    results=load(OUT/"results.json");fit=load(OUT/"collection_fit.json")
    commit=verify_commit();storage={}
    for r in commit["archives"]:
        view=Path(r["path"]).parts[1]
        storage[view]=storage.get(view,0)+r["bytes"]
    raw_bytes=storage["raw32"]
    table=[]
    for view,encoded in storage.items():
        shared=fit["shared_bytes"].get(view,0)
        row=dict(view=view,payload_bytes=encoded,shared_bytes=shared,total_bytes=encoded+shared,
                 total_ratio=raw_bytes/(encoded+shared))
        row["tasks"]={str(task):next(r for r in results if r["view"]==view and r["task"]==task)["macro"] for task in TASKS}
        table.append(row)
    dump(OUT/"storage_quality.json",table)
    rng=np.random.default_rng(SEED)
    comparisons=[]
    for r in results:
        oracle=next(v for v in results if v["view"]=="raw32" and v["task"]==r["task"])
        delta=np.array([a["f1"]-b["f1"] for a,b in zip(r["per_person"],oracle["per_person"]) if a["eligible"] and b["eligible"]])
        boots=delta[rng.integers(0,len(delta),(10000,len(delta)))].mean(1)
        comparisons.append(dict(view=r["view"],task=r["task"],delta_f1=float(delta.mean()),
                                ci95=np.quantile(boots,[.025,.975]).tolist(),participant_deltas=delta.tolist(),
                                raw_task_learnable=oracle["macro"]["f1"]>=.85 and oracle["macro"]["balanced_accuracy"]>=.85 and oracle["test_people"]>=3))
    dump(OUT/"paired_oracle.json",comparisons)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout="constrained")
    colors={"generic":"tab:blue","downsample":"tab:orange","dct":"tab:green"}
    for ax,(task,name) in zip(axes,TASKS.items()):
        for family in colors:
            points=sorted([r for r in table if r["view"].startswith(family+"_")],key=lambda r:r["total_ratio"])
            ax.plot([r["total_ratio"] for r in points],[r["tasks"][str(task)]["f1"] for r in points],"o-",label=family,color=colors[family])
        for view,marker in [("statistics","s"),("pca64","^"),("known_scores","x")]:
            r=next(r for r in table if r["view"]==view)
            ax.scatter(r["total_ratio"],r["tasks"][str(task)]["f1"],marker=marker,s=55,label=view)
        oracle=next(r for r in results if r["view"]=="raw32" and r["task"]==task)
        ax.axhline(oracle["macro"]["f1"],ls="--",color="black",label="raw oracle")
        ax.set(xscale="log",xlabel="Storage compression incl. shared parameters",ylabel="Unseen-person F1",title=name.replace("_"," "),ylim=(0,1.04))
        ax.grid(alpha=.2)
    axes[-1].legend(fontsize=7)
    fig.suptitle("Tasks revealed after archiving; four unseen test people")
    fig.savefig(OUT/"frontier.png",dpi=180);plt.close(fig)
    for r in sorted(table,key=lambda r:r["total_ratio"]):
        print(r["view"],round(r["total_ratio"],1),{k:round(v["f1"],4) for k,v in r["tasks"].items()})


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--stage",choices=["prepare","fit","collect","reveal","evaluate","summarize"],required=True)
    parser.add_argument("--workers",type=int,default=4);args=parser.parse_args()
    with threadpool_limits(limits=1):
        if args.stage=="prepare":prepare()
        elif args.stage=="fit":fit_collection()
        elif args.stage=="collect":collect(args.workers)
        elif args.stage=="reveal":reveal()
        elif args.stage=="evaluate":evaluate(args.workers)
        else:summarize()
