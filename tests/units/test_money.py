from decimal import Decimal

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.money import (
    ZERO,
    add,
    at_rate,
    cents,
    dollars,
    format_money,
    parse_money,
    total,
)


def test_cents_keeps_the_number():
    assert int(cents(12500)) == 12500


def test_cents_allows_a_negative_amount():
    assert int(cents(-4000)) == -4000


def test_cents_refuses_a_float():
    with pytest.raises(BadValueError):
        cents(125.0)  # type: ignore[arg-type]


def test_cents_refuses_a_bool():
    with pytest.raises(BadValueError):
        cents(True)


def test_the_zero_amount_is_no_cents():
    assert int(ZERO) == 0


def test_dollars_from_an_int():
    assert int(dollars(125)) == 12500


def test_dollars_from_a_string():
    assert int(dollars("125.45")) == 12545


def test_dollars_from_a_decimal():
    assert int(dollars(Decimal("0.07"))) == 7


def test_dollars_rounds_half_up():
    assert int(dollars("0.005")) == 1


def test_dollars_rounds_half_up_away_from_zero():
    assert int(dollars("-0.005")) == -1


def test_dollars_refuses_a_bool():
    with pytest.raises(BadValueError):
        dollars(True)


def test_dollars_refuses_a_word_for_an_amount():
    with pytest.raises(BadValueError):
        dollars("free")


def test_dollars_refuses_an_infinite_amount():
    with pytest.raises(BadValueError):
        dollars(float("inf"))


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("$125.00", 12500),
        ("125.00", 12500),
        ("125", 12500),
        ("1,250.50", 125050),
        ("-40.00", -4000),
        ("$ 125.5", 12550),
        ("  $1,000  ", 100000),
    ],
)
def test_parse_money_reads_the_forms(text, want):
    assert int(parse_money(text)) == want


def test_parse_money_refuses_three_decimals():
    with pytest.raises(BadValueError):
        parse_money("125.005")


def test_parse_money_refuses_empty():
    with pytest.raises(BadValueError):
        parse_money("")


def test_parse_money_refuses_a_number():
    with pytest.raises(BadValueError):
        parse_money(125)  # type: ignore[arg-type]


def test_format_money_pads_the_cents():
    assert format_money(cents(12505)) == "$125.05"


def test_format_money_uses_commas():
    assert format_money(cents(125050)) == "$1,250.50"


def test_format_money_of_zero():
    assert format_money(ZERO) == "$0.00"


def test_format_money_signs_a_negative():
    assert format_money(cents(-4000)) == "-$40.00"


def test_format_round_trips_through_parse():
    for value in (0, 1, 99, 100, 12500, 125050):
        assert int(parse_money(format_money(cents(value)))) == value


def test_add_sums_the_arguments():
    assert int(add(cents(100), cents(250), cents(5))) == 355


def test_add_of_nothing_is_zero():
    assert int(add()) == 0


def test_total_sums_an_iterable():
    assert int(total(cents(n) for n in (100, 250, 5))) == 355


def test_total_of_an_empty_iterable_is_zero():
    assert int(total([])) == 0


def test_at_rate_multiplies_rate_by_quantity():
    assert int(at_rate(cents(6), 37)) == 222


def test_at_rate_by_zero():
    assert int(at_rate(cents(600), 0)) == 0


def test_at_rate_rounds_once_at_the_end():
    assert int(at_rate(cents(7), Decimal("0.5"))) == 4


def test_at_rate_takes_a_decimal_quantity():
    assert int(at_rate(cents(250), Decimal("3.4"))) == 850


def test_at_rate_refuses_a_float_quantity():
    with pytest.raises(BadValueError):
        at_rate(cents(6), 3.5)  # type: ignore[arg-type]


def test_at_rate_refuses_a_bool_quantity():
    with pytest.raises(BadValueError):
        at_rate(cents(6), True)


def test_two_rates_added_is_not_the_same_as_the_sum_applied_once():
    miles = Decimal("2.5")
    apart = int(at_rate(cents(3), miles)) + int(at_rate(cents(3), miles))
    together = int(at_rate(cents(6), miles))
    assert apart == 16
    assert together == 15
