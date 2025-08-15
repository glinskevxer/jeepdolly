import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import (
    KINDS,
    PERMIT,
    RIG,
    STRUCTURE,
    SerialKind,
    code,
    is_code,
    serial,
)


def test_code_upper_cases_what_it_is_given():
    assert code("vance") == "VANCE"


def test_code_trims_the_ends():
    assert code("  vance  ") == "VANCE"


def test_code_collapses_inner_space_to_a_dash():
    assert code("vance heavy haul") == "VANCE-HEAVY-HAUL"


def test_code_collapses_a_run_of_space():
    assert code("vance   haul") == "VANCE-HAUL"


def test_code_takes_underscores_as_dashes():
    assert code("vance_haul") == "VANCE-HAUL"


def test_code_keeps_the_digits_it_is_given():
    assert code("rig12") == "RIG12"


def test_code_may_start_with_a_digit():
    assert code("3s2") == "3S2"


def test_code_strips_leading_and_trailing_dashes():
    assert code("-vance-") == "VANCE"


def test_code_refuses_one_character():
    with pytest.raises(BadValueError):
        code("v")


def test_code_refuses_seventeen_characters():
    with pytest.raises(BadValueError):
        code("A" * 17)


def test_code_takes_sixteen_characters():
    assert code("A" * 16) == "A" * 16


def test_code_refuses_a_punctuation_mark():
    with pytest.raises(BadValueError):
        code("vance!")


def test_code_refuses_an_empty_string():
    with pytest.raises(BadValueError):
        code("")


def test_code_refuses_a_number():
    with pytest.raises(BadValueError):
        code(12)  # type: ignore[arg-type]


def test_code_of_its_own_output_is_the_same():
    once = code("vance heavy haul")
    assert code(once) == once


def test_is_code_agrees_with_code():
    assert is_code("vance")
    assert not is_code("v")
    assert not is_code(12)


def test_serial_kind_pads_to_its_width():
    assert PERMIT.format(123) == "P-000123"


def test_serial_kind_pads_a_wide_number_no_further():
    assert PERMIT.format(1234567) == "P-1234567"


def test_serial_kind_refuses_zero():
    with pytest.raises(BadValueError):
        PERMIT.format(0)


def test_serial_kind_refuses_a_bool():
    with pytest.raises(BadValueError):
        PERMIT.format(True)


def test_serial_kind_reads_its_own_output():
    assert PERMIT.number(PERMIT.format(4210)) == 4210


def test_serial_kind_refuses_another_prefix():
    with pytest.raises(BadValueError):
        PERMIT.number(RIG.format(12))


def test_serial_kind_refuses_a_bad_prefix():
    with pytest.raises(BadValueError):
        SerialKind("permit", 6)


def test_serial_kind_refuses_a_narrow_width():
    with pytest.raises(BadValueError):
        SerialKind("P", 2)


def test_serial_kind_refuses_a_wide_width():
    with pytest.raises(BadValueError):
        SerialKind("P", 10)


def test_serial_upper_cases_what_it_is_given():
    assert serial("p-000123") == "P-000123"


def test_serial_trims_the_space_around_it():
    assert serial("  P-000123 ") == "P-000123"


def test_serial_refuses_no_dash():
    with pytest.raises(BadValueError):
        serial("P000123")


def test_serial_refuses_two_digits():
    with pytest.raises(BadValueError):
        serial("P-12")


def test_serial_refuses_all_zeroes():
    with pytest.raises(BadValueError):
        serial("P-000000")


def test_serial_refuses_a_number():
    with pytest.raises(BadValueError):
        serial(123)  # type: ignore[arg-type]


def test_structure_prefix_is_three_letters():
    assert STRUCTURE.format(7) == "STR-00007"


def test_kinds_names_every_kind_once():
    assert set(KINDS) == {"permit", "rig", "structure"}
    assert len({k.prefix for k in KINDS.values()}) == 3
