import datetime as dt

import pytest

from jeepdolly.almanac.embargo import Embargo, EmbargoBook
from jeepdolly.almanac.holiday import embargoes_in
from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.travel.schedule import MAX_DAYS, DayPlan, Schedule, busiest, plan_days
from jeepdolly.units.clock import DaySpan, Window
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds

WEEK = DaySpan(dt.date(2025, 6, 30), dt.date(2025, 7, 6))
JULY = DaySpan(dt.date(2025, 7, 1), dt.date(2025, 7, 31))
EMPTY = EmbargoBook(embargoes=())


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


def holidays() -> EmbargoBook:
    """The 2025 holiday embargoes."""
    return EmbargoBook(embargoes=tuple(embargoes_in(2025)))


def test_a_plain_week_has_a_plan_for_every_day():
    made = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    assert len(made) == 7


def test_a_legal_load_may_move_every_day():
    made = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    assert len(made.movable) == 7
    assert made.stopped == ()


def test_the_holiday_stops_one_day():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    assert dt.date(2025, 7, 4) in [one.day for one in made.stopped]


def test_a_stopped_day_stays_in_the_plan():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    assert len(made) == 7


def test_a_stopped_day_names_the_order_that_stopped_it():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    stopped = made.on(dt.date(2025, 7, 4))
    assert stopped is not None
    assert stopped.stopped_by == ("JULY4-25",)


def test_a_stopped_day_says_so_when_printed():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    stopped = made.on(dt.date(2025, 7, 4))
    assert stopped is not None
    assert "no movement" in str(stopped)
    assert "JULY4-25" in str(stopped)


def test_a_movable_day_prints_its_hours():
    made = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    assert ":" in str(made.days[0])


def test_a_wide_load_is_held_to_daylight():
    plain = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    wide = plan_days(a_load(width=feet(11)), WEEK, "Missoula", EMPTY)
    assert wide.minutes < plain.minutes


def test_a_very_wide_load_loses_the_weekend():
    made = plan_days(a_load(width=feet(15)), WEEK, "Missoula", EMPTY)
    weekend = [one for one in made.stopped if one.day.weekday() >= 5]
    assert len(weekend) == 2


def test_a_rush_hour_splits_a_day():
    book = EmbargoBook(
        embargoes=(
            Embargo(
                code="RUSH-MSO",  # type: ignore[arg-type]
                span=JULY,
                reason="peak traffic",
                window=Window(420, 540),
                counties=frozenset({"Missoula"}),
            ),
        )
    )
    made = plan_days(a_load(), JULY, "Missoula", book)
    assert len(made.days[0].windows) == 2


def test_the_first_movable_day_is_found():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    first = made.first_movable
    assert first is not None
    assert first.day == dt.date(2025, 6, 30)


def test_a_plan_with_no_movable_day_has_no_first():
    book = EmbargoBook(
        embargoes=(Embargo(code="SHUT-25", span=WEEK, reason="closed"),)  # type: ignore[arg-type]
    )
    made = plan_days(a_load(), WEEK, "Missoula", book)
    assert made.first_movable is None


def test_a_day_outside_the_span_is_not_in_the_plan():
    made = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    assert made.on(dt.date(2025, 8, 1)) is None


def test_the_plan_counts_its_minutes():
    made = plan_days(a_load(), WEEK, "Missoula", EMPTY)
    assert made.minutes == 7 * 1439


def test_a_span_that_is_too_long_is_refused():
    long = DaySpan(dt.date(2025, 1, 1), dt.date(2025, 1, 1) + dt.timedelta(days=MAX_DAYS))
    with pytest.raises(BadValueError):
        plan_days(a_load(), long, "Missoula", EMPTY)


def test_a_year_is_inside_the_cap():
    year = DaySpan(dt.date(2025, 1, 1), dt.date(2025, 12, 31))
    assert len(plan_days(a_load(), year, "Missoula", EMPTY)) == 365


def test_a_schedule_refuses_an_empty_county():
    with pytest.raises(BadValueError):
        Schedule(county="  ", days=())


def test_a_schedule_sorts_its_days():
    later = DayPlan(day=dt.date(2025, 7, 2), windows=())
    earlier = DayPlan(day=dt.date(2025, 7, 1), windows=())
    made = Schedule(county="Missoula", days=(later, earlier))
    assert made.days[0] is earlier


def test_a_schedule_prints_a_summary():
    made = plan_days(a_load(), WEEK, "Missoula", holidays())
    assert str(made).startswith("Missoula: 4 of 7 days")


def test_the_busiest_county_is_found():
    quiet = plan_days(a_load(), WEEK, "Missoula", holidays())
    busy = plan_days(a_load(), WEEK, "Granite", EMPTY)
    assert busiest([quiet, busy]) is busy


def test_the_busiest_of_nothing_is_nothing():
    assert busiest([]) is None


def test_a_day_plan_counts_its_own_minutes():
    made = DayPlan(day=dt.date(2025, 7, 1), windows=(Window(360, 600), Window(700, 800)))
    assert made.minutes == 240 + 100
