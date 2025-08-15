import datetime as dt

import pytest

from jeepdolly.almanac.embargo import Embargo, EmbargoBook
from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.travel.window import (
    DAYLIGHT,
    ORDINARY,
    TravelRule,
    daylight_on,
    movable,
    spans_of,
    subtract,
    travel_windows,
)
from jeepdolly.units.clock import MINUTES_PER_DAY, DaySpan, Window
from jeepdolly.units.length import feet, feet_inches, inches
from jeepdolly.units.mass import pounds

JUNE = DaySpan(dt.date(2025, 6, 1), dt.date(2025, 6, 30))
WEDNESDAY = dt.date(2025, 6, 11)
SATURDAY = dt.date(2025, 6, 14)


def a_load(**over: object) -> Load:
    kw: dict[str, object] = {
        "description": "excavator",
        "weight": pounds(96000),
        "width": feet_inches(8, 6),
        "height": feet_inches(13, 6),
        "length": feet(48),
        "divisible": False,
        "reason": "single-piece",
    }
    kw.update(over)
    return Load(**kw)  # type: ignore[arg-type]


def rush_hour(**over: object) -> Embargo:
    kw: dict[str, object] = {
        "code": "RUSH-MSO",
        "span": JUNE,
        "reason": "peak traffic",
        "window": Window(420, 540),
        "counties": frozenset({"Missoula"}),
    }
    kw.update(over)
    return Embargo(**kw)  # type: ignore[arg-type]


EMPTY = EmbargoBook(embargoes=())


def test_spans_of_a_plain_window_is_one_interval():
    assert spans_of(Window(360, 1080)) == ((360, 1080),)


def test_spans_of_a_wrapping_window_is_two():
    assert spans_of(Window(1260, 360)) == ((1260, 1440), (0, 360))


def test_spans_of_an_empty_window_is_nothing():
    assert spans_of(Window(600, 600)) == ()


def test_subtract_nothing_leaves_the_base():
    assert subtract(Window(360, 1080), ()) == (Window(360, 1080),)


def test_subtract_a_hole_in_the_middle_leaves_two():
    assert subtract(Window(360, 1080), (Window(600, 700),)) == (
        Window(360, 600),
        Window(700, 1080),
    )


def test_subtract_a_hole_at_the_start():
    assert subtract(Window(360, 1080), (Window(300, 400),)) == (Window(400, 1080),)


def test_subtract_a_hole_at_the_end():
    assert subtract(Window(360, 1080), (Window(1000, 1200),)) == (Window(360, 1000),)


def test_subtract_a_hole_that_covers_everything_leaves_nothing():
    assert subtract(Window(360, 1080), (Window(0, 1439),)) == ()


def test_subtract_cuts_two_holes_out():
    got = subtract(Window(0, 1439), (Window(300, 400), Window(600, 700)))
    assert got == (Window(0, 300), Window(400, 600), Window(700, 1439))


def test_subtract_from_a_wrapping_base_never_wraps_back():
    got = subtract(Window(1260, 360), (Window(0, 60),))
    assert got == (Window(60, 360), Window(1260, 0))


def test_subtract_a_touching_hole_changes_nothing():
    assert subtract(Window(360, 600), (Window(600, 700),)) == (Window(360, 600),)


def test_the_daylight_table_has_every_month():
    assert sorted(DAYLIGHT) == list(range(1, 13))


def test_daylight_is_longer_in_june_than_in_december():
    assert DAYLIGHT[6].minutes > DAYLIGHT[12].minutes


def test_daylight_on_picks_the_month():
    assert daylight_on(WEDNESDAY) == DAYLIGHT[6]


def test_a_legal_load_may_run_the_whole_day():
    got = travel_windows(a_load(), WEDNESDAY, "Missoula", EMPTY)
    assert got == (Window(0, MINUTES_PER_DAY - 1),)


def test_a_wide_load_is_held_to_daylight():
    got = travel_windows(a_load(width=feet(11)), WEDNESDAY, "Missoula", EMPTY)
    assert got == (DAYLIGHT[6],)


def test_a_load_exactly_at_the_daylight_width_is_not_held():
    got = travel_windows(a_load(width=inches(120)), WEDNESDAY, "Missoula", EMPTY)
    assert got[0].minutes == MINUTES_PER_DAY - 1


def test_a_long_load_is_held_to_daylight():
    got = travel_windows(a_load(length=feet(100)), WEDNESDAY, "Missoula", EMPTY)
    assert got == (DAYLIGHT[6],)


def test_a_very_wide_load_may_not_run_at_the_weekend():
    assert travel_windows(a_load(width=feet(15)), SATURDAY, "Missoula", EMPTY) == ()


def test_the_same_load_may_run_on_a_weekday():
    assert travel_windows(a_load(width=feet(15)), WEDNESDAY, "Missoula", EMPTY) != ()


def test_a_rush_hour_cuts_a_hole():
    book = EmbargoBook(embargoes=(rush_hour(),))
    got = travel_windows(a_load(), WEDNESDAY, "Missoula", book)
    assert Window(0, 420) in got
    assert Window(540, MINUTES_PER_DAY - 1) in got


def test_a_rush_hour_in_another_county_cuts_nothing():
    book = EmbargoBook(embargoes=(rush_hour(),))
    got = travel_windows(a_load(), WEDNESDAY, "Ravalli", book)
    assert got == (Window(0, MINUTES_PER_DAY - 1),)


def test_a_whole_day_embargo_leaves_nothing():
    book = EmbargoBook(
        embargoes=(Embargo(code="JUL4", span=JUNE, reason="holiday"),)  # type: ignore[arg-type]
    )
    assert travel_windows(a_load(), WEDNESDAY, "Missoula", book) == ()


def test_movable_agrees_with_the_windows():
    book = EmbargoBook(
        embargoes=(Embargo(code="JUL4", span=JUNE, reason="holiday"),)  # type: ignore[arg-type]
    )
    assert not movable(a_load(), WEDNESDAY, "Missoula", book)
    assert movable(a_load(), WEDNESDAY, "Missoula", EMPTY)


def test_a_rush_hour_inside_daylight_splits_it():
    book = EmbargoBook(embargoes=(rush_hour(),))
    got = travel_windows(a_load(width=feet(11)), WEDNESDAY, "Missoula", book)
    assert len(got) == 2
    assert got[0].start == DAYLIGHT[6].start


def test_the_rule_refuses_a_weekend_width_below_the_daylight_width():
    with pytest.raises(BadValueError):
        TravelRule(
            name="odd",
            daylight_width=feet(14),
            daylight_length=feet(90),
            no_weekend_width=feet(12),
        )


def test_the_rule_refuses_an_empty_name():
    with pytest.raises(BadValueError):
        TravelRule(
            name=" ",
            daylight_width=feet(10),
            daylight_length=feet(90),
            no_weekend_width=feet(14),
        )


def test_a_stricter_rule_holds_a_narrower_load_to_daylight():
    strict = TravelRule(
        name="metro",
        daylight_width=feet(9),
        daylight_length=feet(70),
        no_weekend_width=feet(12),
    )
    narrow = a_load(width=feet_inches(9, 6))
    assert strict.daylight_only(narrow)
    assert not ORDINARY.daylight_only(narrow)
