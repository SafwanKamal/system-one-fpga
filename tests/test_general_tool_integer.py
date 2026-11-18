import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
import numpy as np
import torch
from sysone.v2.general_tool_integer import fold_type_vocabulary,bank_ids


def test_pair_type_embedding_fold_and_uint16_bound():
    words=torch.tensor([[1.,2.],[3.,4.],[5.,6.]])
    types=torch.tensor([[7.,8.],[9.,10.]])
    folded=fold_type_vocabulary(words,types)
    ids=np.array([0,2]);segments=np.array([0,1])
    actual=folded[bank_ids(ids,segments,len(words))]+types[0]
    expected=words[ids]+types[segments]
    torch.testing.assert_close(actual,expected)
    with pytest.raises(ValueError):
        bank_ids(ids,[0,2],len(words))
    with pytest.raises(ValueError):
        fold_type_vocabulary(torch.zeros(32769,2),types)
