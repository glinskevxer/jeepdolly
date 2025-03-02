import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.length import (
    MAX_INCHES,
    NO_LENGTH,
    feet,
    feet_inches,
    format_length,
    inches,
    parse_length,
    to_feet,
)


def test_inches_keeps_the_number():
    assert int(inches(162)) == 162


def test_inches_allows_zero():
    assert int(inches(0)) == 0


def test_inches_allows_the_ceiling():
    assert int(inches(MAX_INCHES)) == MAX_INCHES


def test_inches_refuses_negative():
    with pytest.raises(BadValueError):
        inches(-1)


def test_inches_refuses_above_the_ceiling():
    with pytest.raises(BadValueError):
        inches(MAX_INCHES + 1)


def test_inches_refuses_a_float():
    with pytest.raises(BadValueError):
        inches(162.0)  # type: ignore[arg-type]


def test_inches_refuses_a_bool():
    with pytest.raises(BadValueError):
        inches(True)


def test_feet_multiplies_by_twelve():
    assert int(feet(13)) == 156


def test_feet_refuses_a_float():
    with pytest.raises(BadValueError):
        feet(13.5)  # type: ignore[arg-type]


def test_feet_inches_adds_the_parts():
    assert int(feet_inches(13, 6)) == 162


def test_feet_inches_takes_zero_inches():
    assert int(feet_inches(13, 0)) == 156


def test_feet_inches_refuses_twelve_inches():
    with pytest.raises(BadValueError):
        feet_inches(13, 12)


def test_feet_inches_refuses_negative_inches():
    with pytest.raises(BadValueError):
        feet_inches(13, -1)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("13'6\"", 162),
        ("13' 6", 162),
        ("13 ft 6 in", 162),
        ("13'", 156),
        ("13ft", 156),
        ("162", 162),
        ("  13'6\"  ", 162),
        ("13FT6IN", 162),
    ],
)
def test_parse_length_reads_the_forms(text, want):
    assert int(parse_length(text)) == want


def test_parse_length_refuses_empty():
    with pytest.raises(BadValueError):
        parse_length("")


def test_parse_length_refuses_words():
    with pytest.raises(BadValueError):
        parse_length("thirteen six")


def test_parse_length_refuses_twelve_inches():
    with pytest.raises(BadValueError):
        parse_length("13'12\"")


def test_parse_length_refuses_a_number():
    with pytest.raises(BadValueError):
        parse_length(162)  # type: ignore[arg-type]


def test_format_length_drops_zero_inches():
    assert format_length(feet(13)) == "13'"


def test_format_length_keeps_inches():
    assert format_length(feet_inches(13, 6)) == "13'6\""


def test_format_round_trips_through_parse():
    for value in (0, 1, 11, 12, 100, 162, MAX_INCHES):
        assert int(parse_length(format_length(inches(value)))) == value


def test_to_feet_is_a_float():
    assert to_feet(feet_inches(13, 6)) == pytest.approx(13.5)


def test_no_length_is_zero():
    assert int(NO_LENGTH) == 0
