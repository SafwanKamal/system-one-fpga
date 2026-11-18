import pytest
pytest.importorskip('torch')
pytest.importorskip('transformers')
from sysone.v2.general_tool_encoder import KINDS,label_value,scalar_from_span,ToolEncoder,job_text


class Encoding(dict):
    def sequence_ids(self):
        return [None,0,None,1,1,None]


def test_extraction_labels_point_to_query_not_schema():
    encoding=Encoding(offset_mapping=[(0,0),(0,2),(0,0),(0,2),(3,5),(0,0)])
    assert label_value(10,'10 20',encoding)==(KINDS.index('span'),3,3)
    assert label_value('missing','10 20',encoding)[0]==KINDS.index('unrepresentable')
    assert label_value(True,'10 20',encoding)[0]==KINDS.index('true')


def test_span_conversion_never_executes_expressions():
    assert scalar_from_span('-1.5',{'type':'number'})==-1.5
    with pytest.raises(ValueError):
        scalar_from_span('1+2',{'type':'integer'})
    with pytest.raises(ValueError):
        scalar_from_span('__import__("os")',{'type':'array'})


def test_count_head_covers_shared_four_call_language(monkeypatch):
    from types import SimpleNamespace
    from torch import nn
    from sysone.v2 import general_tool_encoder as module
    class StubEncoder(nn.Module):
        config=SimpleNamespace(hidden_size=2)
    monkeypatch.setattr(module.AutoModel,'from_pretrained',lambda *a,**kw:StubEncoder())
    model=ToolEncoder('unused',max_calls_per_tool=4)
    assert model.count.out_features==6 # 0,1,2,3,4 plus overflow
    assert '0, 1, 2, 3, 4' in job_text({'name':'f','description':'f','parameters':{}})
