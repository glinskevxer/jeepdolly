"""The day by day movement plan for one permit.

A permit says the load may run between two dates. What the driver actually needs
is which of those days it may run at all, and between which hours on each of
them, once daylight, the weekend rule and every embargo in force have been
applied.

Working that out for a three day trip is a minute's work by hand and nobody
minds. Working it out for an annual permit across three counties and a year of
holidays is four hundred rows, which is why this exists.

A day with no window at all is kept in the plan rather than dropped. "You may not
move on the fourth of July" is information; a plan that silently skips that day
looks like the fourth of July does not exist.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from jeepdolly.almanac.embargo import EmbargoBook
from jeepdolly.errors import BadValueError
from jeepdolly.rig.load import Load
from jeepdolly.travel.window import ORDINARY, TravelRule, travel_windows
from jeepdolly.units.clock import Day, DaySpan, Window, format_day

__all__ = ["MAX_DAYS", "DayPlan", "Schedule", "busiest", "plan_days"]

#: A plan longer than this is refused rather than built. An annual permit is
#: three hundred and sixty five days and nothing the office issues is longer.
MAX_DAYS = 400


@dataclass(frozen=True, slots=True, order=True)
class DayPlan:
    """One day of a permit, and the hours the load may move on it."""

    day: Day
    windows: tuple[Window, ...]
    stopped_by: tuple[str, ...] = ()

    @property
    def movable(self) -> bool:
        """May the load move at all on this day."""
        return bool(self.windows)

    @property
    def minutes(self) -> int:
        """How many minutes of movement the day allows."""
        return sum(window.minutes for window in self.windows)

    @property
    def hours(self) -> str:
        """The windows as one printable field."""
        if not self.windows:
            return "no movement"
        return ", ".join(str(window) for window in self.windows)

    def __str__(self) -> str:
        why = f" ({', '.join(self.stopped_by)})" if self.stopped_by and not self.movable else ""
        return f"{format_day(self.day)} {self.hours}{why}"


@dataclass(frozen=True, slots=True)
class Schedule:
    """A whole permit's worth of day plans, in order."""

    county: str
    days: tuple[DayPlan, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "days", tuple(sorted(self.days)))
        if not self.county.strip():
            raise BadValueError("county", self.county, "want some text")

    @property
    def movable(self) -> tuple[DayPlan, ...]:
        """The days the load may move on."""
        return tuple(one for one in self.days if one.movable)

    @property
    def stopped(self) -> tuple[DayPlan, ...]:
        """The days it may not."""
        return tuple(one for one in self.days if not one.movable)

    @property
    def minutes(self) -> int:
        """Total movement time across the whole permit."""
        return sum(one.minutes for one in self.days)

    @property
    def first_movable(self) -> DayPlan | None:
        """The first day the load may actually leave, if there is one."""
        found = self.movable
        return found[0] if found else None

    def on(self, day: Day) -> DayPlan | None:
        """The plan for one day, if it is inside the permit."""
        for one in self.days:
            if one.day == day:
                return one
        return None

    def __len__(self) -> int:
        return len(self.days)

    def __str__(self) -> str:
        return (
            f"{self.county}: {len(self.movable)} of {len(self.days)} days,"
            f" {self.minutes} minutes"
        )


def plan_days(
    load: Load,
    span: DaySpan,
    county: str,
    book: EmbargoBook,
    rule: TravelRule = ORDINARY,
) -> Schedule:
    """Work out the movement plan for one load in one county over a span."""
    if span.days > MAX_DAYS:
        raise BadValueError("span", span.days, f"over {MAX_DAYS} days")
    days: list[DayPlan] = []
    for day in span:
        windows = travel_windows(load, day, county, book, rule)
        stopped = tuple(str(one.code) for one in book.on_day(day, county) if one.window is None)
        days.append(DayPlan(day=day, windows=windows, stopped_by=stopped))
    return Schedule(county=county, days=tuple(days))


def busiest(schedules: Iterable[Schedule]) -> Schedule | None:
    """The county with the most movement time, or nothing for an empty list."""
    found = list(schedules)
    if not found:
        return None
    return max(found, key=lambda one: (one.minutes, one.county))
