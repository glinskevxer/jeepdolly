"""Days, times of day, and the two kinds of span built on them.

A permit is good for a run of days. A curfew is a run of minutes inside a day.
Those are different enough that they get different types, and similar enough
that people keep trying to use one for the other, so both are closed here.

Times of day are minutes since midnight. A window may wrap past midnight, which
is the normal case for a night curfew, and every method has to cope with that
rather than assuming start is below end.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError

__all__ = [
    "MINUTES_PER_DAY",
    "WEEKEND",
    "Day",
    "DaySpan",
    "Window",
    "format_clock",
    "format_day",
    "minute_of_day",
    "parse_clock",
    "parse_day",
]

Day = dt.date

MINUTES_PER_DAY = 24 * 60

#: Saturday and Sunday as ``date.weekday()`` numbers.
WEEKEND = frozenset({5, 6})

_CLOCK = re.compile(r"^\s*(?P<h>\d{1,2}):?(?P<m>\d{2})\s*$")


def parse_day(text: str) -> Day:
    """Read a date in the one format the office writes."""
    if not isinstance(text, str):
        raise BadValueError("day", text, "want text")
    try:
        return dt.date.fromisoformat(text.strip())
    except ValueError as exc:
        raise BadValueError("day", text, "want YYYY-MM-DD") from exc


def format_day(day: Day) -> str:
    """Write a date the way the permit prints it."""
    return day.isoformat()


def minute_of_day(value: int) -> int:
    """Check a minutes since midnight figure."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadValueError("minute", value, "want a whole number of minutes")
    if not 0 <= value < MINUTES_PER_DAY:
        raise BadValueError("minute", value, "outside the day")
    return value


def parse_clock(text: str) -> int:
    """Read a time of day as minutes since midnight.

    Accepts ``07:30`` and ``0730``. Twenty four hundred is refused; the end of a
    day is written ``23:59`` on the office's forms and a window that runs to
    midnight is written as wrapping to ``00:00``.
    """
    if not isinstance(text, str):
        raise BadValueError("clock", text, "want text")
    hit = _CLOCK.match(text)
    if hit is None:
        raise BadValueError("clock", text, "want HH:MM")
    hour = int(hit.group("h"))
    minute = int(hit.group("m"))
    if hour > 23 or minute > 59:
        raise BadValueError("clock", text, "not a time of day")
    return hour * 60 + minute


def format_clock(value: int) -> str:
    """Write minutes since midnight as HH:MM."""
    hour, minute = divmod(minute_of_day(value), 60)
    return f"{hour:02d}:{minute:02d}"


@dataclass(frozen=True, slots=True, order=True)
class Window:
    """A run of minutes inside a day, half open at the end.

    ``Window(360, 1080)`` is six in the morning to six at night and does not
    include the minute at six. ``Window(1260, 360)`` wraps: nine at night to six
    the next morning. Start equal to end is the empty window, not the whole day,
    because an empty curfew is the thing people write by accident and a
    twenty four hour curfew is written as such.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", minute_of_day(self.start))
        object.__setattr__(self, "end", minute_of_day(self.end))

    @property
    def wraps(self) -> bool:
        """True when the window runs past midnight."""
        return self.end < self.start

    @property
    def empty(self) -> bool:
        """True when the window holds no minutes at all."""
        return self.start == self.end

    @property
    def minutes(self) -> int:
        """How many minutes the window holds."""
        if self.wraps:
            return MINUTES_PER_DAY - self.start + self.end
        return self.end - self.start

    def covers(self, minute: int) -> bool:
        """Is this minute inside the window."""
        minute = minute_of_day(minute)
        if self.empty:
            return False
        if self.wraps:
            return minute >= self.start or minute < self.end
        return self.start <= minute < self.end

    def overlaps(self, other: Window) -> bool:
        """Do the two windows share any minute."""
        if self.empty or other.empty:
            return False
        return any(other.covers(m) for m in self._edges()) or any(
            self.covers(m) for m in other._edges()
        )

    def _edges(self) -> tuple[int, ...]:
        last = (self.end - 1) % MINUTES_PER_DAY
        return (self.start, last)

    def __str__(self) -> str:
        return f"{format_clock(self.start)}-{format_clock(self.end)}"


@dataclass(frozen=True, slots=True, order=True)
class DaySpan:
    """A run of calendar days, both ends included.

    A permit good for one day has ``first == last``. Unlike ``Window`` there is
    no empty span, because a permit valid for no days is not a thing the office
    can issue and the check belongs here rather than in every caller.
    """

    first: Day
    last: Day

    def __post_init__(self) -> None:
        for name in ("first", "last"):
            value = getattr(self, name)
            if not isinstance(value, dt.date) or isinstance(value, dt.datetime):
                raise BadValueError(name, value, "want a date")
        if self.last < self.first:
            raise BadValueError("span", f"{self.first}..{self.last}", "ends before it starts")

    @property
    def days(self) -> int:
        """How many days the span holds, counting both ends."""
        return (self.last - self.first).days + 1

    def covers(self, day: Day) -> bool:
        """Is this day inside the span."""
        return self.first <= day <= self.last

    def overlaps(self, other: DaySpan) -> bool:
        """Do the two spans share any day."""
        return self.first <= other.last and other.first <= self.last

    def __iter__(self) -> Iterator[Day]:
        day = self.first
        while day <= self.last:
            yield day
            day += dt.timedelta(days=1)

    def __str__(self) -> str:
        if self.first == self.last:
            return format_day(self.first)
        return f"{format_day(self.first)}..{format_day(self.last)}"
