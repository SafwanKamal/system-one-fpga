import pytest
from sysone.v2.functiongemma_profile import validate_prompt_ids


def test_supported_model_extent_and_real_multimodal_added_token_boundary():
    assert validate_prompt_ids([0,262143])
    for bad in [262144,262145,-1,True,1.5]:
        with pytest.raises(ValueError,match='token ID'):validate_prompt_ids([bad])


def test_reserved_generation_work_is_in_context_budget():
    assert validate_prompt_ids([1]*1792)
    with pytest.raises(ValueError,match='context'):validate_prompt_ids([1]*1793)
    with pytest.raises(ValueError,match='context'):validate_prompt_ids([])
