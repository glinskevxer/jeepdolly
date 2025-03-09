from fractions import Fraction

import pytest

from jeepdolly.errors import BadValueError
from jeepdolly.units.share import divide_by_weight, divide_evenly, largest_remainder


def test_even_split_that_comes_out_exact():
    assert divide_evenly(9000, 3) == (3000, 3000, 3000)


def test_even_split_puts_the_leftover_at_the_front():
    assert divide_evenly(7, 3) == (3, 2, 2)


def test_even_split_into_one_part():
    assert divide_evenly(7, 1) == (7,)


def test_even_split_of_zero():
    assert divide_evenly(0, 3) == (0, 0, 0)


def test_even_split_always_adds_back():
    for total in range(40):
        for parts in range(1, 8):
            assert sum(divide_evenly(total, parts)) == total


def test_even_split_parts_never_differ_by_more_than_one():
    got = divide_evenly(100, 7)
    assert max(got) - min(got) == 1


def test_even_split_refuses_zero_parts():
    with pytest.raises(BadValueError):
        divide_evenly(9, 0)


def test_even_split_refuses_a_negative_total():
    with pytest.raises(BadValueError):
        divide_evenly(-1, 3)


def test_even_split_refuses_a_bool_total():
    with pytest.raises(BadValueError):
        divide_evenly(True, 3)


def test_even_split_refuses_a_bool_part_count():
    with pytest.raises(BadValueError):
        divide_evenly(9, True)


def test_weighted_split_is_proportional():
    assert divide_by_weight(9000, [1, 1, 1]) == (3000, 3000, 3000)


def test_weighted_split_follows_the_weights():
    assert divide_by_weight(10000, [3, 1]) == (7500, 2500)


def test_weighted_split_gives_the_leftover_to_the_largest_remainder():
    # Exact claims are 2.33, 2.33, 2.33 with one unit left over.
    assert divide_by_weight(7, [1, 1, 1]) == (3, 2, 2)


def test_weighted_split_breaks_a_tie_toward_the_earlier_position():
    assert divide_by_weight(1, [1, 1]) == (1, 0)


def test_weighted_split_gives_a_zero_weight_nothing():
    assert divide_by_weight(10, [0, 1, 1]) == (0, 5, 5)


def test_weighted_split_never_hands_a_leftover_to_a_zero_weight():
    got = divide_by_weight(7, [0, 1, 1, 1])
    assert got[0] == 0
    assert sum(got) == 7


def test_weighted_split_always_adds_back():
    for total in range(30):
        assert sum(divide_by_weight(total, [5, 3, 2])) == total


def test_weighted_split_of_zero():
    assert divide_by_weight(0, [5, 3, 2]) == (0, 0, 0)


def test_weighted_split_refuses_all_zero_weights():
    with pytest.raises(BadValueError):
        divide_by_weight(10, [0, 0])


def test_weighted_split_refuses_an_empty_weight_list():
    with pytest.raises(BadValueError):
        divide_by_weight(10, [])


def test_weighted_split_refuses_a_negative_weight():
    with pytest.raises(BadValueError):
        divide_by_weight(10, [1, -1])


def test_weighted_split_refuses_a_float_weight():
    with pytest.raises(BadValueError):
        divide_by_weight(10, [1.0, 1])  # type: ignore[list-item]


def test_weighted_split_refuses_a_bool_weight():
    with pytest.raises(BadValueError):
        divide_by_weight(10, [True, 1])


def test_weighted_split_refuses_a_string():
    with pytest.raises(BadValueError):
        divide_by_weight(10, "12")  # type: ignore[arg-type]


def test_largest_remainder_hands_out_the_leftovers():
    exact = [Fraction(7, 3), Fraction(7, 3), Fraction(7, 3)]
    assert largest_remainder(7, exact) == (3, 2, 2)


def test_largest_remainder_prefers_the_bigger_fraction():
    exact = [Fraction(1, 4), Fraction(7, 4)]
    assert largest_remainder(2, exact) == (0, 2)


def test_largest_remainder_takes_an_eligibility_mask():
    exact = [Fraction(1, 2), Fraction(1, 2), Fraction(1)]
    assert largest_remainder(2, exact, eligible=[False, True, True]) == (0, 1, 1)


def test_largest_remainder_refuses_a_mask_of_the_wrong_length():
    with pytest.raises(BadValueError):
        largest_remainder(2, [Fraction(1), Fraction(1)], eligible=[True])


def test_largest_remainder_refuses_shares_over_the_total():
    with pytest.raises(BadValueError):
        largest_remainder(1, [Fraction(3), Fraction(3)])


def test_largest_remainder_refuses_when_nobody_can_take_the_leftover():
    with pytest.raises(BadValueError):
        largest_remainder(3, [Fraction(1, 2), Fraction(1, 2)], eligible=[False, False])


def test_splits_are_reproducible():
    first = divide_by_weight(1234, [17, 13, 11, 7])
    for _ in range(5):
        assert divide_by_weight(1234, [17, 13, 11, 7]) == first
