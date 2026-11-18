import inspect
import numpy as np
import pytest

from pilot import (D, CHUNK, METHODS, Memory, Timeline, answer, decode, floats,
                   quantize, queries, read_block, read_timeline, value_block)


def test_codec_and_missingness():
    rng = np.random.default_rng(2)
    q = rng.integers(0, 256, size=(131, D), dtype=np.uint8)
    q[5, 1] = 127  # The threshold tie must go into the positive bin.
    for bits in [1, 2, 4, 8]:
        x = read_block(value_block(q, bits), len(q), bits)
        assert np.array_equal(np.isnan(x), q == 255)
        valid = q != 255
        if bits == 8:
            assert np.array_equal(quantize(x), q)
        assert np.nanmax(np.abs(x - floats(q))) <= .5 / ((1 << bits) - 1) + 1e-6
        assert np.array_equal(x[valid] >= .5, floats(q)[valid] >= .5)


def test_timeline_preserves_irregular_gaps_and_epoch_precision():
    t = np.array([1440000001, 1440000062, 1440000122, 1440080123], np.uint32)
    tl = Timeline()
    tl.add(t[:2])
    tl.add(t[2:])
    assert np.array_equal(read_timeline(tl.serialize(), tl.start), t)


def test_independent_query_oracle():
    t = np.array([0, 60, 120, 180, 900, 960], np.uint32)
    x = np.zeros((6, D))
    x[:, 0] = [1, 1, 0, 1, 1, 0]
    x[:, 1] = [0, 1, 1, 0, 0, 1]
    q = dict(op="duration", d=0, e=1, a=0, b=6, threshold=.5)
    assert answer(x, t, q) == 4
    assert answer(x, t, dict(q, op="episodes")) == 3  # gap breaks continuity
    assert answer(x, t, dict(q, op="co_duration")) == 1
    assert answer(x, t, dict(q, op="co_episodes")) == 1
    assert answer(x, t, dict(q, op="follow")) == 2  # never bridge the 12-minute gap
    assert answer(x, t, dict(q, op="episodes", a=1)) == 2
    assert answer(x, t, dict(q, op="co_episodes", a=2)) == 0


@pytest.mark.parametrize("method", METHODS)
def test_every_archive_roundtrips_within_budget_and_no_query_inputs(method):
    rng = np.random.default_rng(3)
    q = rng.integers(0, 256, size=(789, D), dtype=np.uint8)
    t = (1440000000 + np.arange(len(q)) * 60).astype(np.uint32)
    mem = Memory(method, 2048, seed=17)
    for a in range(0, len(q), CHUNK):
        mem.ingest(t[a:a + CHUNK], q[a:a + CHUNK])
        b = mem.serialize()
        assert len(b) <= 2048
        rt, x, _ = decode(b, np.full(D, .2))
        assert np.array_equal(rt, t[:len(rt)])
        assert x.shape == (len(rt), D)
    if method == "hybrid_bundle":
        ids = {r[1] for r in mem.entries}
        assert all((i ^ 1) in ids for i in ids)
    assert list(inspect.signature(Memory.ingest).parameters) == ["self", "t", "q"]


def test_full_event_table_preserves_all_half_threshold_queries():
    rng = np.random.default_rng(5)
    q = rng.integers(0, 256, size=(900, D), dtype=np.uint8)
    t = (1440000000 + np.arange(len(q)) * 60).astype(np.uint32)
    mem = Memory("event1", 16384)
    for a in range(0, len(q), CHUNK):
        mem.ingest(t[a:a + CHUNK], q[a:a + CHUNK])
    rt, x, covered = decode(mem.serialize(), np.full(D, .2))
    assert covered.all()
    for query in queries(len(q), 17):
        if query["threshold"] == .5:
            assert answer(x, rt, query) == answer(floats(q), t, query)


def test_prefix_is_unaffected_by_future_data_or_future_queries():
    rng = np.random.default_rng(7)
    prefix = rng.integers(0, 255, size=(128, D), dtype=np.uint8)
    t = (1440000000 + np.arange(128) * 60).astype(np.uint32)
    a, b = Memory("hybrid_bundle", 8192, 3), Memory("hybrid_bundle", 8192, 3)
    a.ingest(t, prefix)
    queries(10000, 1)
    b.ingest(t, prefix)
    assert a.serialize() == b.serialize()


def test_equal_marginals_different_relationships_need_no_fancy_memory():
    t = (1440000000 + np.arange(6) * 60).astype(np.uint32)
    x = np.zeros((6, D), dtype=np.uint8)
    y = x.copy()
    x[1, 0] = y[1, 0] = 254
    x[3, 1] = y[0, 1] = 254
    assert np.array_equal(x.mean(0), y.mean(0))
    query = dict(op="follow", d=0, e=1, a=0, b=6, threshold=.5)
    observed = []
    for data in [x, y]:
        mem = Memory("event1", 2048)
        mem.ingest(t, data)
        restored_t, restored, _ = decode(mem.serialize(), np.full(D, .2))
        observed.append(answer(restored, restored_t, query))
    assert observed == [1, 0]


def test_timeline_fits_but_a_single_mean_record_does_not():
    from pilot import HEADER, INGEST_STATE_BYTES
    t = (1440000000 + np.arange(128) * 60).astype(np.uint32)
    tl = Timeline()
    tl.add(t)
    budget = HEADER.size + INGEST_STATE_BYTES + 2 + tl.size + 31
    mem = Memory("dyadic", budget)
    mem.ingest(t, np.zeros((len(t), D), np.uint8))
    assert not mem.segments
    assert len(mem.serialize()) <= budget


def test_reused_parallel_worker_resets_seed_instead_of_accumulating(monkeypatch, tmp_path):
    import pilot
    import run_parallel
    seen = []
    monkeypatch.setattr(pilot, "OUT", pilot.OUT)
    monkeypatch.setattr(pilot, "SEED", run_parallel.BASE_SEED)
    monkeypatch.setattr(pilot, "select", pilot.select)
    monkeypatch.setattr(pilot, "run", lambda stage: seen.append(pilot.SEED))
    for index in [5, 7]:
        run_parallel.worker("validation", "subject", index, None, {}, {"validation": ["subject"]}, str(tmp_path / str(index)))
    assert seen == [run_parallel.BASE_SEED + 5, run_parallel.BASE_SEED + 7]
