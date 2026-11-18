import inspect
import json
import pickle
from pathlib import Path

import numpy as np
import pytest

import study


@pytest.mark.parametrize("kind",[0,1,2])
def test_lossless_frames_preserve_signals_and_missingness(kind):
    x=np.random.default_rng(1).normal(size=(study.T,study.C)).astype(np.float32)
    x[3:12,4]=np.nan;x[:,7]=np.nan
    original=x.copy()
    b=study.waveform_frame(x,123.5,kind)
    restored,start=study.decode_frame(b)
    assert start==123.5
    assert np.array_equal(x,restored,equal_nan=True)
    assert np.array_equal(x,original,equal_nan=True)


@pytest.mark.parametrize("bits",[4,8,16])
def test_scalar_quantization_error_and_constant_channels(bits):
    a=np.random.default_rng(2).normal(size=(64,study.C)).astype(np.float32);a[:,1]=5
    restored=study.scalar_decode(study.scalar_encode(a,bits),len(a),bits)
    if bits<16:
        bound=(a.max(0)-a.min(0))/(2*((1<<bits)-1))+2e-6
        assert np.all(np.max(np.abs(a-restored),axis=0)<=bound)
    else:assert np.max(np.abs(a-restored))<.002
    assert np.all(restored[:,1]==5)


def test_future_samples_never_enter_known_training_even_as_minorities():
    labels=np.ones((4,study.T),np.int16)
    labels[0,0]=5;labels[1,:]=6;labels[2,20:]=12
    majority,purity,eligible,known=study.custodian_labels(labels,np.ones(4,bool))
    assert eligible[0]  # still a 99.8%-pure known label, so purity alone is unsafe
    assert known.tolist()==[False,False,False,True]


def test_codec_selection_never_receives_labels_and_respects_caps():
    t=np.arange(study.T)/study.HZ
    x=np.tile(np.sin(2*np.pi*2*t)[:,None],(1,study.C)).astype(np.float32)
    options=study.candidates(x,0,np.ones(study.C))
    assert list(inspect.signature(study.candidates).parameters)==['x','start','scales']
    for family,items in options.items():
        for cap in study.BUDGETS:
            valid=[(m,b) for m,b in items if len(b)+4<=cap]
            assert valid
            mse,b=min(valid,key=lambda item:item[0])
            decoded,_=study.decode_frame(b)
            assert decoded.shape==x.shape
            assert np.isfinite(mse)


def test_feature_archives_cannot_recover_a_hidden_raw_backing_array():
    features=np.arange(378,dtype=np.float32)
    b=study.frame(5,16,len(features),0,b'',features.astype('<f2').tobytes())
    x,start=study.decode_frame(b)
    assert x.ndim==1 and np.array_equal(x,features)
    assert len(b)==study.HEADER.size+2*len(features)


def test_archive_reader_and_commit_detect_tampering(monkeypatch,tmp_path):
    monkeypatch.setattr(study,'OUT',tmp_path)
    f=tmp_path/'test.bin';f.write_bytes(b'RTAHIST1')
    study.dump(tmp_path/'archive_commit.json',{'committed_utc':'before','archives':[{'path':'test.bin','bytes':8,'sha256':study.sha(f)}]})
    study.verify_commit()
    f.write_bytes(b'RTAHIST2')
    with pytest.raises(AssertionError):study.verify_commit()


def test_learning_requires_a_label_reveal_receipt(monkeypatch,tmp_path):
    monkeypatch.setattr(study,'OUT',tmp_path)
    with pytest.raises(AssertionError):study._evaluate_worker('raw32')


def test_signal_features_are_finite_on_missing_and_constant_data():
    x=np.zeros((study.T,study.C),np.float32);x[:,0]=np.nan
    features=study.stats_features(x)
    assert features.shape==(378,)
    assert np.isfinite(features).all()
