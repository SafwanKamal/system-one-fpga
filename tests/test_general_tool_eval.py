from pathlib import Path
import pytest
from sysone.v2.general_tool_eval import BFCLPythonChecker


def test_pinned_parallel_checker_requires_all_calls_but_not_call_order():
    root=Path(__file__).resolve().parents[1]/'build/v2/general-tool-comparison-v0/bfcl-python-checker'
    if not root.exists():
        pytest.skip('Stage pinned upstream BFCL Python checker first')
    checker=BFCLPythonChecker(root)
    def tool(name):
        return dict(name=name,parameters=dict(type='dict',properties={'x':{'type':'integer'}},required=['x']))
    case=dict(category='parallel',tools=[tool('a'),tool('b')])
    gold=[{'a':{'x':[1]}},{'b':{'x':[2]}}]
    calls=[dict(name='b',arguments={'x':2}),dict(name='a',arguments={'x':1})]
    assert checker.score(case,calls,gold)['valid']
    assert not checker.score(case,[calls[0],calls[0]],gold)['valid']
    assert not checker.score(case,calls[:1],gold)['valid']
