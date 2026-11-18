import pytest
from sysone.v2.v8_benchmark_protocol_v2 import parse_enum_record


def test_eos_delimits_complete_record_without_inventing_values():
    assert parse_enum_record('0 A 4',terminal=True)==('ok','A',4)
    assert parse_enum_record('0 A 42',terminal=True)==('ok','A',42)
    assert parse_enum_record('0 A 4\n')==('ok','A',4)


def test_partial_number_is_not_mistaken_for_end_of_record():
    with pytest.raises(ValueError):parse_enum_record('0 A 4')
    with pytest.raises(ValueError):parse_enum_record('0 A -',terminal=True)


@pytest.mark.parametrize('text',['3 A 4','0 C 4','0 A 4 extra','0 A 04','0 A true','0 A 1.0','0 A 4\nextra'])
def test_eos_does_not_excuse_bad_fields_or_extra_payload(text):
    with pytest.raises(ValueError):parse_enum_record(text,terminal=True)
