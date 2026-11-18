"""Partial checkpoints must restore only the declared model adaptation."""
from types import SimpleNamespace
import pytest
torch = pytest.importorskip('torch')
pytest.importorskip('transformers')
from torch import nn
from sysone.v2 import general_clean_inference as inference


class TinyEncoder(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.encoder = nn.Module()
        self.encoder.encoder = nn.Module()
        self.encoder.encoder.layer = nn.ModuleList([nn.Linear(2,2) for _ in range(3)])
        self.count = nn.Linear(2,6)
        self.kind = nn.Linear(2,9)
        self.span = nn.Linear(2,2)


def test_partial_restore_preserves_official_frozen_backbone(monkeypatch, tmp_path):
    monkeypatch.setattr(inference, 'ToolEncoder', TinyEncoder)
    monkeypatch.setattr(inference.AutoTokenizer, 'from_pretrained', lambda *a,**k:SimpleNamespace())
    torch.manual_seed(2026101702)
    original = TinyEncoder()
    adapted = {n:torch.full_like(v,7) for n,v in original.state_dict().items()
               if not n.startswith('encoder.encoder.layer.0.')}
    checkpoint = tmp_path/'partial.pt'
    torch.save(dict(trainable_state=adapted, manifest=dict(family='encoder',arguments=dict(model='official'))), checkpoint)
    loaded = inference.CleanInference('encoder','official',checkpoint)
    for name,value in loaded.model.state_dict().items():
        torch.testing.assert_close(value, adapted[name] if name in adapted else original.state_dict()[name])
    assert not any(p.requires_grad for p in loaded.model.parameters())
    # A checkpoint that silently adds an early block is not the same adaptation.
    adapted['encoder.encoder.layer.0.weight'] = original.encoder.encoder.layer[0].weight
    torch.save(dict(trainable_state=adapted, manifest=dict(family='encoder',arguments=dict(model='official'))), checkpoint)
    with pytest.raises(ValueError,match='key set'):
        inference.CleanInference('encoder','official',checkpoint)


def test_unknown_family_rejected_before_loading_models():
    with pytest.raises(ValueError,match='unknown family'):
        inference.CleanInference('other','unavailable')
