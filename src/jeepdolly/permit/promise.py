"""What the office promises on turnaround, and what is past it.

The counter has a sign with three numbers on it. A trip permit by the end of the
next working day. An annual within three. A superload within ten, and everybody
knows that one is the engineer's queue rather than the counter's.

Working days, which is the whole difficulty. An application filed at four on the
Friday of a long weekend is not late on the Tuesday morning, and a clerk counting
calendar days will tell the carrier it is. So the count skips weekends and skips
the office's own holidays, which means this has to read the holiday book, which
means the promise depends on the year the application was filed in.

That last part is the rule that composes. Two applications filed the same number
of calendar days ago can have different answers about being late, because one of
them straddled Thanksgiving and the other did not. Anything that works the
promise out from a subtraction is wrong, and every implementation of this the
office has had started as a subtraction.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from jeepdolly.almanac.holiday import holidays_in
from jeepdolly.errors import BadValueError
from jeepdolly.permit.application import Application, Kind
from jeepdolly.units.clock import WEEKEND, Day, format_day, only_a_day

__all__ = [
    "MAX_SPAN_DAYS",
    "TARGET_DAYS",
    "Standing",
    "holidays_between",
    "promised_by",
    "standing_of",
    "working_days",
]

#: What the sign at the counter says, in working days from the day it was filed.
TARGET_DAYS: dict[Kind, int] = {Kind.TRIP: 1, Kind.ANNUAL: 3, Kind.SUPERLOAD: 10}

#: Counting working days across a longer gap than this is a sign the caller has
#: the days the wrong way round, which used to loop for a very long time.
MAX_SPAN_DAYS = 800


def holidays_between(first: Day, last: Day) -> frozenset[Day]:
    """Every day the office is shut inside a run of days.

    Read a year at a time out of the almanac, so a span crossing New Year picks
    up both years. The book is cheap to build and this is not on any hot path.
    """
    only_a_day(first, "first")
    only_a_day(last, "last")
    shut: set[Day] = set()
    for year in range(first.year, last.year + 1):
        for holiday in holidays_in(year):
            shut.update(holiday.span)
    return frozenset(day for day in shut if first <= day <= last)


def working_days(first: Day, last: Day) -> int:
    """How many working days lie between two days, not counting the first.

    Nothing for a last day on or before the first, rather than a negative, so a
    caller asking about tomorrow's application gets zero and not a promise that
    has somehow already been met.
    """
    only_a_day(first, "first")
    only_a_day(last, "last")
    if last <= first:
        return 0
    if (last - first).days > MAX_SPAN_DAYS:
        raise BadValueError("span", (last - first).days, f"over {MAX_SPAN_DAYS} days")
    shut = holidays_between(first, last)
    count = 0
    day = first + dt.timedelta(days=1)
    while day <= last:
        if day.weekday() not in WEEKEND and day not in shut:
            count += 1
        day += dt.timedelta(days=1)
    return count


def promised_by(filed_on: Day, kind: Kind) -> Day:
    """The day the office has promised an answer by.

    Walks forward a working day at a time rather than adding the target and
    correcting, because correcting is what puts the answer on a Saturday when
    the target lands on the Friday of a holiday week.
    """
    only_a_day(filed_on, "filed on")
    target = TARGET_DAYS.get(Kind(kind))
    if target is None:
        raise BadValueError("kind", kind, "no promise for that sort of permit")
    day = filed_on
    left = target
    while left > 0:
        day += dt.timedelta(days=1)
        if (day - filed_on).days > MAX_SPAN_DAYS:
            raise BadValueError("filed on", filed_on, "no working day within reach")
        if day.weekday() in WEEKEND or day in holidays_between(day, day):
            continue
        left -= 1
    return day


@dataclass(frozen=True, slots=True, order=True)
class Standing:
    """One unanswered application and how it stands against the promise."""

    over: int
    key: int
    carrier: str
    kind: Kind
    filed_on: Day
    due: Day

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", Kind(self.kind))
        for name in ("filed_on", "due"):
            object.__setattr__(self, name, only_a_day(getattr(self, name), name))
        if isinstance(self.key, bool) or not isinstance(self.key, int) or self.key < 1:
            raise BadValueError("key", self.key, "application keys start at one")
        if not isinstance(self.carrier, str) or not self.carrier.strip():
            raise BadValueError("carrier", self.carrier, "want some text")
        object.__setattr__(self, "carrier", self.carrier.strip().upper())

    @property
    def late(self) -> bool:
        """Is the office past what it promised on this one."""
        return self.over > 0

    def __str__(self) -> str:
        if self.late:
            word = "day" if self.over == 1 else "days"
            return f"application {self.key} {self.carrier} is {self.over} {word} over"
        return f"application {self.key} {self.carrier} due {format_day(self.due)}"


def standing_of(key: int, application: Application, on: Day) -> Standing:
    """Where one unanswered application stands as at a day."""
    if not isinstance(application, Application):
        raise BadValueError("application", application, "want an application")
    due = promised_by(application.filed_on, application.kind)
    return Standing(
        over=working_days(due, only_a_day(on)),
        key=key,
        carrier=str(application.carrier),
        kind=application.kind,
        filed_on=application.filed_on,
        due=due,
    )
