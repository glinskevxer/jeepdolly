import datetime as dt

import pytest

from jeepdolly.almanac.embargo import Embargo, EmbargoBook
from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.route.plan import along_segments
from jeepdolly.route.stage import (
    DEFAULT_SPEED,
    MAX_SPEED,
    Stage,
    minutes_for,
    stage_run,
)
from jeepdolly.travel.schedule import plan_days
from jeepdolly.units.clock import DaySpan
from jeepdolly.units.distance import hundredths, miles
from jeepdolly.units.length import feet, feet_inches
from jeepdolly.units.mass import pounds

WEEK = DaySpan(dt.date(2025, 6, 16), dt.date(2025, 6, 20))
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


def a_schedule(load: Load | None = None, span: DaySpan = WEEK, book: EmbargoBook = EMPTY):
    """The movement plan for a load over a span."""
    return plan_days(load or a_load(), span, "Missoula", book)


def test_an_hour_at_thirty_five_covers_thirty_five_miles():
    assert minutes_for(miles(35), 35) == 60


def test_a_part_mile_rounds_the_minutes_up():
    assert minutes_for(hundredths(1), 35) == 1


def test_no_distance_takes_no_time():
    assert minutes_for(hundredths(0), 35) == 0


def test_a_slower_speed_takes_longer():
    assert minutes_for(miles(35), 20) > minutes_for(miles(35), 35)


def test_a_speed_of_zero_is_refused():
    with pytest.raises(BadValueError):
        minutes_for(miles(10), 0)


def test_a_speed_above_the_cap_is_refused():
    with pytest.raises(BadValueError):
        minutes_for(miles(10), MAX_SPEED + 1)


def test_a_bool_speed_is_refused():
    with pytest.raises(BadValueError):
        minutes_for(miles(10), True)


def test_the_default_speed_is_a_haul_speed():
    assert 20 <= DEFAULT_SPEED <= 45


def test_a_short_run_finishes_on_the_first_day(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    made = stage_run(route, a_schedule())
    assert made.finished
    assert made.days == 1


def test_a_finished_run_covers_the_whole_route(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    made = stage_run(route, a_schedule())
    assert made.covered == route.distance


def test_the_stop_is_the_end_of_the_route(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    made = stage_run(route, a_schedule())
    assert made.stops[-1] == "JCT-D"


def test_a_daylight_load_takes_longer_than_a_free_one(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    free = stage_run(route, a_schedule(), speed=5)
    held = stage_run(route, a_schedule(a_load(width=feet(11))), speed=5)
    assert held.days >= free.days


def test_a_leg_that_will_not_fit_waits_for_the_morning(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    one_day = DaySpan(dt.date(2025, 6, 16), dt.date(2025, 6, 17))
    made = stage_run(route, a_schedule(a_load(width=feet(11)), one_day), speed=2)
    assert len(made.stages[0].legs) == 1
    assert made.days == 2
    assert made.finished


def test_a_run_that_does_not_fit_reports_what_is_left(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    one_day = DaySpan(dt.date(2025, 6, 16), dt.date(2025, 6, 16))
    made = stage_run(route, a_schedule(a_load(width=feet(11)), one_day), speed=1)
    assert not made.finished
    assert made.left_over


def test_an_unfinished_run_says_so_when_printed(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    one_day = DaySpan(dt.date(2025, 6, 16), dt.date(2025, 6, 16))
    made = stage_run(route, a_schedule(a_load(width=feet(11)), one_day), speed=1)
    assert "do not fit" in str(made)


def test_a_finished_run_says_how_many_days(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    assert "in 1 days" in str(stage_run(route, a_schedule()))


def test_a_stopped_day_carries_no_legs(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    book = EmbargoBook(
        embargoes=(
            Embargo(
                code="SHUT-25",  # type: ignore[arg-type]
                span=DaySpan(dt.date(2025, 6, 16), dt.date(2025, 6, 16)),
                reason="bridge work",
            ),
        )
    )
    made = stage_run(route, a_schedule(a_load(width=feet(11)), WEEK, book), speed=3)
    assert not made.stages[0].moving
    assert made.stages[0].ends_at is None


def test_a_stopped_day_says_so_when_printed(corridor):
    made = Stage(day=dt.date(2025, 6, 16), legs=(), minutes=0)
    assert str(made) == "2025-06-16 no movement"


def test_a_moving_day_prints_where_it_ends(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    made = stage_run(route, a_schedule())
    assert "to JCT-B" in str(made.stages[0])


def test_the_minutes_add_up(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    made = stage_run(route, a_schedule())
    assert made.minutes == sum(stage.minutes for stage in made.stages)


def test_the_distance_adds_up(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    made = stage_run(route, a_schedule())
    assert int(made.covered) == sum(int(stage.distance) for stage in made.stages)


def test_a_schedule_that_is_not_one_is_refused(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    with pytest.raises(BadValueError):
        stage_run(route, "next week")  # type: ignore[arg-type]


def test_a_bad_speed_is_refused_before_anything_is_staged(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    with pytest.raises(BadValueError):
        stage_run(route, a_schedule(), speed=0)


def test_the_staging_stops_once_the_route_is_done(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB"])
    made = stage_run(route, a_schedule())
    assert len(made.stages) == 1


def test_a_slower_haul_needs_more_days(corridor):
    route = along_segments(corridor, "JCT-A", ["SEG-AB", "SEG-BD"])
    quick = stage_run(route, a_schedule(a_load(width=feet(11))), speed=35)
    slow = stage_run(route, a_schedule(a_load(width=feet(11))), speed=4)
    assert slow.days >= quick.days
