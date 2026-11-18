import json
import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
from sysone.v2.general_clean_partitions import partition_checked_records


def test_audit_excludes_selection_components_and_prior_prefix(tmp_path):
    train=[dict(id='train',query='train',split_component='train')]
    dev=[dict(id=f'dev{i}',query=f'query{i}',split_component=f'group{i//2}') for i in range(500)]
    for name,rows in [('train',train),('dev',dev)]:
        (tmp_path/f'{name}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    _,selection,audit=partition_checked_records(tmp_path,1)
    assert len(selection)==20 and len(audit)==72
    assert not {r['split_component'] for r in selection}&{r['split_component'] for r in audit}
    assert not {r['id'] for r in selection}&{r['id'] for r in audit}
    with pytest.raises(ValueError,match='not enough'):
        partition_checked_records(tmp_path,1,audit_offset=499)
