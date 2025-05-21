import datetime as dt

import pytest

from jeepdolly.almanac.embargo import STATEWIDE, Embargo, EmbargoBook
from jeepdolly.errors import BadValueError
from jeepdolly.units.clock import DaySpan, Window

JULY = DaySpan(dt.date(2025, 7, 3), dt.date(2025, 7, 6))
SUMMER = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 8, 31))
FRIDAY = dt.date(2025, 7, 4)
SATURDAY = dt.date(2025, 7, 5)


def a_holiday(**over: object) -> Embargo:
    """The Fourth of July statewide embargo."""
    kw: dict[str, object] = {
        "code": "JUL4-25",
        "span": JULY,
        "reason": "Independence Day holiday",
    }
    kw.update(over)
    return Embargo(**kw)  # type: ignore[arg-type]


def a_rush_hour(**over: object) -> Embargo:
    """A weekday rush hour restriction in one county."""
    kw: dict[str, object] = {
        "code": "RUSH-MSO",
        "span": SUMMER,
        "reason": "peak traffic on Reserve Street",
        "window": Window(420, 540),
        "counties": frozenset({"Missoula"}),
    }
    kw.update(over)
    return Embargo(**kw)  # type: ignore[arg-type]


def test_a_holiday_is_statewide_and_all_day():
    made = a_holiday()
    assert made.statewide
    assert made.all_day


def test_a_rush_hour_is_neither():
    made = a_rush_hour()
    assert not made.statewide
    assert not made.all_day


def test_a_holiday_blocks_any_county():
    assert a_holiday().blocks(FRIDAY, 600, "Anywhere")


def test_a_holiday_blocks_any_minute():
    assert a_holiday().blocks(FRIDAY, 0, "Missoula")
    assert a_holiday().blocks(FRIDAY, 1439, "Missoula")


def test_a_holiday_does_not_block_outside_its_span():
    assert not a_holiday().blocks(dt.date(2025, 7, 7), 600, "Missoula")


def test_a_rush_hour_blocks_inside_the_window():
    assert a_rush_hour().blocks(FRIDAY, 450, "Missoula")


def test_a_rush_hour_does_not_block_outside_the_window():
    assert not a_rush_hour().blocks(FRIDAY, 600, "Missoula")


def test_a_rush_hour_does_not_block_another_county():
    assert not a_rush_hour().blocks(FRIDAY, 450, "Ravalli")


def test_a_county_name_is_tidied_before_matching():
    assert a_rush_hour().blocks(FRIDAY, 450, "  Missoula  ")


def test_a_weekend_only_order_skips_the_weekday():
    made = a_holiday(weekends_only=True)
    assert not made.blocks(FRIDAY, 600, "Missoula")
    assert made.blocks(SATURDAY, 600, "Missoula")


def test_a_wrapping_window_blocks_over_midnight():
    made = a_rush_hour(window=Window(1260, 360))
    assert made.blocks(FRIDAY, 1300, "Missoula")
    assert made.blocks(FRIDAY, 60, "Missoula")
    assert not made.blocks(FRIDAY, 600, "Missoula")


def test_embargo_normalises_its_code():
    assert a_holiday(code="jul4-25").code == "JUL4-25"


def test_embargo_collapses_whitespace_in_the_reason():
    assert a_holiday(reason="holiday   traffic").reason == "holiday traffic"


def test_embargo_refuses_an_empty_reason():
    with pytest.raises(BadValueError):
        a_holiday(reason=" ")


def test_embargo_refuses_a_span_that_is_not_one():
    with pytest.raises(BadValueError):
        a_holiday(span="july")


def test_embargo_refuses_a_window_that_is_not_one():
    with pytest.raises(BadValueError):
        a_holiday(window="morning")


def test_embargo_refuses_an_empty_window():
    with pytest.raises(BadValueError):
        a_holiday(window=Window(600, 600))


def test_embargo_refuses_an_empty_county_set():
    with pytest.raises(BadValueError):
        a_holiday(counties=frozenset())


def test_embargo_refuses_a_non_bool_weekends_only():
    with pytest.raises(BadValueError):
        a_holiday(weekends_only="yes")


def test_a_holiday_prints_statewide_and_all_day():
    printed = str(a_holiday())
    assert STATEWIDE in printed
    assert "all day" in printed


def test_a_rush_hour_prints_its_window():
    assert "07:00-09:00" in str(a_rush_hour())


def test_a_book_sorts_its_orders():
    book = EmbargoBook(embargoes=(a_rush_hour(), a_holiday()))
    assert [e.code for e in book.embargoes] == ["JUL4-25", "RUSH-MSO"]


def test_a_book_refuses_two_orders_with_one_code():
    with pytest.raises(BadValueError):
        EmbargoBook(embargoes=(a_holiday(), a_holiday()))


def test_a_book_finds_both_orders_at_once():
    book = EmbargoBook(embargoes=(a_holiday(), a_rush_hour()))
    assert len(book.blocking(FRIDAY, 450, "Missoula")) == 2


def test_a_book_finds_only_the_holiday_outside_the_window():
    book = EmbargoBook(embargoes=(a_holiday(), a_rush_hour()))
    assert [e.code for e in book.blocking(FRIDAY, 600, "Missoula")] == ["JUL4-25"]


def test_a_book_says_when_movement_is_free():
    book = EmbargoBook(embargoes=(a_rush_hour(),))
    assert book.free(FRIDAY, 600, "Missoula")
    assert not book.free(FRIDAY, 450, "Missoula")


def test_on_day_ignores_the_hour():
    book = EmbargoBook(embargoes=(a_rush_hour(),))
    assert len(book.on_day(FRIDAY, "Missoula")) == 1
    assert book.blocking(FRIDAY, 600, "Missoula") == ()


def test_on_day_still_respects_the_county():
    book = EmbargoBook(embargoes=(a_rush_hour(),))
    assert book.on_day(FRIDAY, "Ravalli") == ()


def test_an_empty_book_blocks_nothing():
    book = EmbargoBook(embargoes=())
    assert len(book) == 0
    assert book.free(FRIDAY, 450, "Missoula")


def test_a_book_iterates_its_orders():
    book = EmbargoBook(embargoes=(a_holiday(),))
    assert [e.code for e in book] == ["JUL4-25"]
