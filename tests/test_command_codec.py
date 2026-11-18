import pytest
from sysone.v2.command_codec import FIELDS, encode, decode, allowed_values, constrained_fields
from scripts.v2.prepare_command_comparison import make_pilot


def test_all_generated_plans_roundtrip_and_splits_are_disjoint():
    splits = make_pilot()
    ids = []
    for rows in splits.values():
        for row in rows:
            assert decode(encode(row['gold'])) == row['gold']
            fields=encode(row['gold'])
            partial={}
            for key in sorted(FIELDS):
                assert fields[key] in allowed_values(partial,key)
                partial[key]=fields[key]
            ids.append(row['id'])
    assert len(ids) == len(set(ids)) == 1599


def test_unused_payload_is_not_discarded():
    fields = encode({'outcome':'Clarify','reason':'missing_asset'})
    fields['api1'] = 'stop_asset'
    with pytest.raises(ValueError):
        decode(fields)


def test_arbitrary_logits_decode_to_a_checked_record():
    import random
    rng=random.Random(2)
    for _ in range(100):
        scores={k:[rng.random() for _ in v] for k,v in FIELDS.items()}
        assert encode(decode(constrained_fields(scores)))==constrained_fields(scores)
