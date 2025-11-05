"""The holidays the office embargoes, worked out rather than typed in.

A list of dates has to be retyped every year and gets forgotten in December. The
rules are simple enough to compute: five of the eleven are fixed dates and six
are the nth weekday of a month, and a fixed date falling at the weekend is
observed on the nearest weekday.

The embargo is not the holiday. An oversize load may not move from noon the day
before through the morning after, so each holiday produces a span of days rather
than one day, and the span is what goes in the embargo book.

Which day is observed matters here in a way it does not on a calendar. A carrier
planning a Thursday move around a Friday holiday needs the office and the
carrier to agree on which Friday, and computing it from one rule is how they do.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from jeepdolly.almanac.embargo import Embargo
from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.units.clock import Day, DaySpan

__all__ = [
    "FIXED",
    "FLOATING",
    "SHOULDER_AFTER",
    "SHOULDER_BEFORE",
    "Holiday",
    "embargoes_in",
    "holidays_in",
    "last_weekday",
    "nth_weekday",
    "observed",
]

#: Days of embargo before the observed holiday.
SHOULDER_BEFORE = 1

#: Days of embargo after it.
SHOULDER_AFTER = 1

#: Holidays that fall on a fixed date, as name, short code, month and day. The
#: short code is what the embargo is filed under, because a code is sixteen
#: characters and ``martin-luther-king-25`` is twenty one.
FIXED: tuple[tuple[str, str, int, int], ...] = (
    ("new-year", "NEWYEAR", 1, 1),
    ("juneteenth", "JUNE19", 6, 19),
    ("independence", "JULY4", 7, 4),
    ("veterans", "VETS", 11, 11),
    ("christmas", "XMAS", 12, 25),
)

#: Holidays that fall on the nth weekday of a month. A count of ``-1`` means the
#: last one in the month, which is how Memorial Day is written.
FLOATING: tuple[tuple[str, str, int, int, int], ...] = (
    ("martin-luther-king", "MLK", 1, 0, 3),
    ("presidents", "PRES", 2, 0, 3),
    ("memorial", "MEMORIAL", 5, 0, -1),
    ("labor", "LABOR", 9, 0, 1),
    ("columbus", "COLUMBUS", 10, 0, 2),
    ("thanksgiving", "THANKS", 11, 3, 4),
)


def nth_weekday(year: int, month: int, weekday: int, count: int) -> Day:
    """The ``count``th ``weekday`` of a month, counting from one."""
    if not 1 <= count <= 5:
        raise BadValueError("count", count, "want 1 to 5")
    first = dt.date(year, month, 1)
    ahead = (weekday - first.weekday()) % 7
    day = first + dt.timedelta(days=ahead + 7 * (count - 1))
    if day.month != month:
        raise BadValueError("count", count, f"there is no {count}th in {month}")
    return day


def last_weekday(year: int, month: int, weekday: int) -> Day:
    """The last ``weekday`` of a month."""
    after = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    day = after - dt.timedelta(days=1)
    while day.weekday() != weekday:
        day -= dt.timedelta(days=1)
    return day


def observed(day: Day) -> Day:
    """The weekday a fixed holiday is kept on.

    Saturday moves back to Friday and Sunday forward to Monday, which is the
    federal rule and the one the office follows.
    """
    if day.weekday() == 5:
        return day - dt.timedelta(days=1)
    if day.weekday() == 6:
        return day + dt.timedelta(days=1)
    return day


@dataclass(frozen=True, slots=True, order=True)
class Holiday:
    """One holiday in one year, on the day it is actually kept."""

    day: Day
    name: str
    short: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.day, dt.date) or isinstance(self.day, dt.datetime):
            raise BadValueError("day", self.day, "want a date")
        if not isinstance(self.name, str) or not self.name.strip():
            raise BadValueError("name", self.name, "want some text")
        object.__setattr__(self, "name", "-".join(self.name.split()))
        if not isinstance(self.short, str):
            raise BadValueError("short", self.short, "want text")
        object.__setattr__(self, "short", (self.short or self.name[:8]).upper())

    @property
    def span(self) -> DaySpan:
        """The days movement is stopped around it."""
        return DaySpan(
            self.day - dt.timedelta(days=SHOULDER_BEFORE),
            self.day + dt.timedelta(days=SHOULDER_AFTER),
        )

    @property
    def code(self) -> Code:
        """The code the embargo is filed under."""
        return code(f"{self.short}-{self.day.year % 100:02d}")

    def __str__(self) -> str:
        return f"{self.name} {self.day}"


def holidays_in(year: int) -> list[Holiday]:
    """Every holiday in one year, on the day it is kept, earliest first."""
    if isinstance(year, bool) or not isinstance(year, int):
        raise BadValueError("year", year, "want a whole number")
    if not 1900 <= year <= 2999:
        raise BadValueError("year", year, "want a four digit year")
    found = [
        Holiday(day=observed(dt.date(year, month, day)), name=name, short=short)
        for name, short, month, day in FIXED
    ]
    for name, short, month, weekday, count in FLOATING:
        day = (
            last_weekday(year, month, weekday)
            if count == -1
            else nth_weekday(year, month, weekday, count)
        )
        found.append(Holiday(day=day, name=name, short=short))
    return sorted(found)


def embargoes_in(year: int) -> list[Embargo]:
    """The statewide embargo each holiday produces, earliest first."""
    return [
        Embargo(
            code=holiday.code,
            span=holiday.span,
            reason=f"{holiday.name.replace('-', ' ')} holiday",
        )
        for holiday in holidays_in(year)
    ]
