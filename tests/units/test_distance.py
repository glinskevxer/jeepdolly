from decimal import Decimal

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.distance import (
    MAX_HUNDREDTHS,
    NO_DISTANCE,
    add_distance,
    format_distance,
    hundredths,
    miles,
    parse_distance,
    to_miles,
    total_distance,
    whole_miles,
)


def test_hundredths_keeps_the_number():
    assert int(hundredths(1234)) == 1234


def test_hundredths_allows_a_distance_of_zero():
    assert int(hundredths(0)) == 0


def test_hundredths_allows_the_ceiling():
    assert int(hundredths(MAX_HUNDREDTHS)) == MAX_HUNDREDTHS


def test_hundredths_refuses_above_the_ceiling():
    with pytest.raises(BadValueError):
        hundredths(MAX_HUNDREDTHS + 1)


def test_hundredths_refuses_a_negative_distance():
    with pytest.raises(BadValueError):
        hundredths(-1)


def test_hundredths_refuses_a_float():
    with pytest.raises(BadValueError):
        hundredths(12.34)  # type: ignore[arg-type]


def test_hundredths_refuses_a_bool():
    with pytest.raises(BadValueError):
        hundredths(True)


def test_no_distance_is_zero():
    assert int(NO_DISTANCE) == 0


def test_miles_from_an_int():
    assert int(miles(12)) == 1200


def test_miles_from_a_string():
    assert int(miles("12.34")) == 1234


def test_miles_from_a_decimal():
    assert int(miles(Decimal("0.05"))) == 5


def test_miles_refuses_a_third_decimal():
    with pytest.raises(BadValueError):
        miles("12.345")


def test_miles_refuses_a_bool():
    with pytest.raises(BadValueError):
        miles(True)


def test_miles_refuses_a_word_instead_of_a_number():
    with pytest.raises(BadValueError):
        miles("far")


def test_miles_refuses_an_infinite_figure():
    with pytest.raises(BadValueError):
        miles(float("inf"))


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("12", 1200),
        ("12.3", 1230),
        ("12.34", 1234),
        ("12.34 mi", 1234),
        ("12 miles", 1200),
        ("  12.34  ", 1234),
        ("0", 0),
    ],
)
def test_parse_distance_reads_the_forms(text, want):
    assert int(parse_distance(text)) == want


def test_parse_distance_refuses_three_decimals():
    with pytest.raises(BadValueError):
        parse_distance("12.345")


def test_parse_distance_refuses_empty():
    with pytest.raises(BadValueError):
        parse_distance("")


def test_parse_distance_refuses_a_number():
    with pytest.raises(BadValueError):
        parse_distance(12)  # type: ignore[arg-type]


def test_format_distance_always_shows_two_decimals():
    assert format_distance(miles(12)) == "12.00 mi"


def test_format_distance_of_a_part_mile():
    assert format_distance(hundredths(5)) == "0.05 mi"


def test_format_round_trips_through_parse():
    for value in (0, 1, 99, 100, 1234, 100000):
        assert int(parse_distance(format_distance(hundredths(value)))) == value


def test_to_miles_is_exact():
    assert to_miles(hundredths(1234)) == Decimal("12.34")


def test_whole_miles_of_an_exact_mile():
    assert whole_miles(miles(12)) == 12


def test_whole_miles_rounds_a_part_mile_up():
    assert whole_miles(hundredths(1201)) == 13


def test_whole_miles_of_one_hundredth_is_one():
    assert whole_miles(hundredths(1)) == 1


def test_whole_miles_of_zero_is_zero():
    assert whole_miles(NO_DISTANCE) == 0


def test_add_distance_sums_its_arguments():
    assert int(add_distance(hundredths(100), hundredths(234))) == 334


def test_add_distance_of_nothing_is_zero():
    assert int(add_distance()) == 0


def test_total_distance_sums_an_iterable():
    assert int(total_distance(hundredths(n) for n in (100, 234, 5))) == 339


def test_total_distance_of_an_empty_iterable_is_zero():
    assert int(total_distance([])) == 0


def test_a_sum_over_the_ceiling_is_refused():
    with pytest.raises(BadValueError):
        add_distance(hundredths(MAX_HUNDREDTHS), hundredths(1))
