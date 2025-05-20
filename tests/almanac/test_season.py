import datetime as dt

import pytest

from jeepdolly.almanac.season import MAX_PERCENT, MIN_PERCENT, Season, SeasonBook
from jeepdolly.errors import BadValueError
from jeepdolly.limits.statute import STATE_ROUTE
from jeepdolly.units.clock import DaySpan

THAW = DaySpan(dt.date(2025, 3, 1), dt.date(2025, 4, 15))
FREEZE = DaySpan(dt.date(2025, 12, 15), dt.date(2026, 2, 28))


def a_season(**over: object) -> Season:
    """A spring thaw order, with any part of it swapped out."""
    kw: dict[str, object] = {
        "code": "THAW-25",
        "span": THAW,
        "percent": 60,
        "counties": frozenset({"Missoula", "Ravalli"}),
    }
    kw.update(over)
    return Season(**kw)  # type: ignore[arg-type]


def test_a_thaw_order_restricts():
    assert a_season().restricting
    assert not a_season().premium


def test_a_winter_order_is_a_premium():
    made = a_season(code="FREEZE-25", span=FREEZE, percent=110)
    assert made.premium
    assert not made.restricting


def test_a_season_normalises_its_code():
    assert a_season(code="thaw-25").code == "THAW-25"


def test_a_season_refuses_a_hundred_percent():
    with pytest.raises(BadValueError):
        a_season(percent=100)


def test_a_season_refuses_too_low_a_percent():
    with pytest.raises(BadValueError):
        a_season(percent=MIN_PERCENT - 1)


def test_a_season_refuses_too_high_a_percent():
    with pytest.raises(BadValueError):
        a_season(percent=MAX_PERCENT + 1)


def test_a_season_takes_the_lowest_percent():
    assert a_season(percent=MIN_PERCENT).percent == MIN_PERCENT


def test_a_season_refuses_a_bool_percent():
    with pytest.raises(BadValueError):
        a_season(percent=True)


def test_a_season_refuses_no_counties():
    with pytest.raises(BadValueError):
        a_season(counties=frozenset())


def test_a_season_refuses_an_empty_county_name():
    with pytest.raises(BadValueError):
        a_season(counties=frozenset({" "}))


def test_a_season_refuses_a_span_that_is_not_one():
    with pytest.raises(BadValueError):
        a_season(span="march to april")


def test_a_season_covers_a_day_inside_it():
    assert a_season().covers(dt.date(2025, 3, 20), "Missoula")


def test_a_season_covers_its_first_day():
    assert a_season().covers(dt.date(2025, 3, 1), "Missoula")


def test_a_season_covers_its_last_day():
    assert a_season().covers(dt.date(2025, 4, 15), "Missoula")


def test_a_season_does_not_cover_the_day_after():
    assert not a_season().covers(dt.date(2025, 4, 16), "Missoula")


def test_a_season_does_not_cover_another_county():
    assert not a_season().covers(dt.date(2025, 3, 20), "Lewis and Clark")


def test_a_county_name_is_matched_after_whitespace_is_tidied():
    assert a_season().covers(dt.date(2025, 3, 20), " Missoula ")


def test_applying_a_thaw_cuts_the_limits():
    reduced = a_season().applied(STATE_ROUTE)
    assert int(reduced.gross) == 48000
    assert int(reduced.single) == 12900


def test_applying_rounds_down_to_the_hundred():
    reduced = a_season(percent=61).applied(STATE_ROUTE)
    assert int(reduced.single) == 13100


def test_applying_names_the_order():
    assert "THAW-25" in a_season().applied(STATE_ROUTE).name


def test_applying_leaves_the_tandem_bracket_alone():
    reduced = a_season().applied(STATE_ROUTE)
    assert reduced.tandem_low == STATE_ROUTE.tandem_low


def test_applying_a_premium_raises_the_limits():
    raised = a_season(code="FREEZE-25", span=FREEZE, percent=110).applied(STATE_ROUTE)
    assert int(raised.gross) == 88000


def test_a_season_prints_which_way_it_goes():
    assert "down to 60%" in str(a_season())
    assert "up to 110%" in str(a_season(code="FR-25", span=FREEZE, percent=110))


def test_a_book_sorts_its_orders():
    book = SeasonBook(seasons=(a_season(code="ZED"), a_season(code="ACE")))
    assert [s.code for s in book.seasons] == ["ACE", "ZED"]


def test_a_book_refuses_two_orders_with_one_code():
    with pytest.raises(BadValueError):
        SeasonBook(seasons=(a_season(), a_season()))


def test_a_book_finds_what_is_in_force():
    book = SeasonBook(seasons=(a_season(),))
    assert len(book.in_force(dt.date(2025, 3, 20), "Missoula")) == 1


def test_a_book_finds_nothing_out_of_season():
    book = SeasonBook(seasons=(a_season(),))
    assert book.in_force(dt.date(2025, 7, 1), "Missoula") == ()


def test_a_book_applies_what_is_in_force():
    book = SeasonBook(seasons=(a_season(),))
    got = book.statute_on(STATE_ROUTE, dt.date(2025, 3, 20), "Missoula")
    assert int(got.gross) == 48000


def test_a_book_leaves_the_statute_alone_out_of_season():
    book = SeasonBook(seasons=(a_season(),))
    got = book.statute_on(STATE_ROUTE, dt.date(2025, 7, 1), "Missoula")
    assert got is STATE_ROUTE


def test_two_orders_on_one_day_both_apply():
    book = SeasonBook(
        seasons=(
            a_season(code="A-THAW", percent=60),
            a_season(code="B-THAW", percent=80),
        )
    )
    got = book.statute_on(STATE_ROUTE, dt.date(2025, 3, 20), "Missoula")
    assert int(got.gross) == 38400


def test_an_empty_book_changes_nothing():
    book = SeasonBook(seasons=())
    assert len(book) == 0
    assert book.statute_on(STATE_ROUTE, dt.date(2025, 3, 20), "Missoula") is STATE_ROUTE


def test_a_book_iterates_its_orders():
    book = SeasonBook(seasons=(a_season(),))
    assert [s.code for s in book] == ["THAW-25"]
