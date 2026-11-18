import pytest
from sysone.v2.general_schema_annotations import annotation_schema, adapt_tool
from sysone.v2.general_tools import validate_calls


def test_optional_is_not_nullable_or_a_string_expression():
    tool = adapt_tool({'name':'f', 'parameters': {
        'label': {'type':'str, optional'},
        'matrix': {'type':'List[List[int]]'}}})
    validate_calls([{'name':'f','arguments':{'label':'a','matrix':[[1,2]]}}], [tool])
    validate_calls([{'name':'f','arguments':{}}], [tool])
    for value in (None, 4):
        with pytest.raises(ValueError):
            validate_calls([{'name':'f','arguments':{'label':value}}], [tool])
    for value in ('[[1,2]]', [[True]]):
        with pytest.raises(ValueError):
            validate_calls([{'name':'f','arguments':{'matrix':value}}], [tool])


def test_unknown_and_positional_types_do_not_become_any():
    for text in ['Callable[[float], float]', 'set', 'Tuple[int, str]',
                 'List[Tuple[float, float]]', '__import__("os").system("false")']:
        assert annotation_schema(text) is None
    assert annotation_schema('str, default="a"') == {'type':'string'}
