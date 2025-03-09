import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.mass import (
    MAX_POUNDS,
    NO_WEIGHT,
    POUNDS_PER_TON,
    format_weight,
    parse_weight,
    pounds,
    to_tons,
    tons,
    tons_over,
)


def test_pounds_keeps_the_number():
    assert int(pounds(80000)) == 80000


def test_pounds_allows_zero():
    assert int(pounds(0)) == 0


def test_pounds_allows_the_ceiling():
    assert int(pounds(MAX_POUNDS)) == MAX_POUNDS


def test_pounds_refuses_negative():
    with pytest.raises(BadValueError):
        pounds(-1)


def test_pounds_refuses_above_the_ceiling():
    with pytest.raises(BadValueError):
        pounds(MAX_POUNDS + 1)


def test_pounds_refuses_a_float():
    with pytest.raises(BadValueError):
        pounds(80000.0)  # type: ignore[arg-type]


def test_pounds_refuses_a_bool():
    with pytest.raises(BadValueError):
        pounds(True)


def test_tons_converts_at_two_thousand():
    assert int(tons(40)) == 80000


def test_tons_takes_a_half():
    assert int(tons(40.5)) == 81000


def test_tons_rounds_to_the_nearest_pound():
    assert int(tons(0.00025)) == 0
    assert int(tons(0.00075)) == 2


def test_tons_refuses_text():
    with pytest.raises(BadValueError):
        tons("40")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("80000", 80000),
        ("80,000", 80000),
        ("80,000 lb", 80000),
        ("80000 lbs", 80000),
        ("80000 pounds", 80000),
        ("40 t", 80000),
        ("40 tons", 80000),
        ("40.5 tons", 81000),
        ("  80,000  ", 80000),
    ],
)
def test_parse_weight_reads_the_forms(text, want):
    assert int(parse_weight(text)) == want


def test_parse_weight_refuses_a_decimal_in_pounds():
    with pytest.raises(BadValueError):
        parse_weight("80000.5")


def test_parse_weight_refuses_empty():
    with pytest.raises(BadValueError):
        parse_weight("")


def test_parse_weight_refuses_words():
    with pytest.raises(BadValueError):
        parse_weight("heavy")


def test_parse_weight_refuses_a_number():
    with pytest.raises(BadValueError):
        parse_weight(80000)  # type: ignore[arg-type]


def test_format_weight_uses_commas():
    assert format_weight(pounds(80000)) == "80,000 lb"


def test_format_weight_of_zero():
    assert format_weight(pounds(0)) == "0 lb"


def test_to_tons_divides():
    assert to_tons(pounds(81000)) == pytest.approx(40.5)


def test_tons_over_is_zero_at_the_limit():
    assert tons_over(pounds(80000), pounds(80000)) == 0


def test_tons_over_is_zero_under_the_limit():
    assert tons_over(pounds(70000), pounds(80000)) == 0


def test_tons_over_rounds_one_pound_up_to_a_ton():
    assert tons_over(pounds(80001), pounds(80000)) == 1


def test_tons_over_at_an_exact_ton():
    assert tons_over(pounds(82000), pounds(80000)) == 1


def test_tons_over_one_pound_past_an_exact_ton():
    assert tons_over(pounds(82001), pounds(80000)) == 2


def test_pounds_per_ton_is_the_short_ton():
    assert POUNDS_PER_TON == 2000


def test_no_weight_is_zero():
    assert int(NO_WEIGHT) == 0
