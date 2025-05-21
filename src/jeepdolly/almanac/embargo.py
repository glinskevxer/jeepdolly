"""Days and hours when an oversize load may not move.

Three shapes, one type.

A holiday embargo is whole days, statewide, and covers the day before and the
day after a holiday as often as the holiday itself. A construction embargo is
whole days in one or two counties. A rush hour embargo is a window inside every
day of a span, in a named county.

The type carries an optional window and an optional county set, and the two
optionals are what make the three shapes. No window means whole days. No
counties means statewide. Both together is a rush hour restriction in one place,
which is the common case.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.units.clock import WEEKEND, Day, DaySpan, Window

__all__ = ["STATEWIDE", "Embargo", "EmbargoBook"]

#: What a county set of ``None`` prints as.
STATEWIDE = "statewide"


@dataclass(frozen=True, slots=True, order=True)
class Embargo:
    """One order stopping movement over a span of days."""

    code: Code
    span: DaySpan
    reason: str
    window: Window | None = None
    counties: frozenset[str] | None = None
    weekends_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", code(str(self.code)))
        if not isinstance(self.span, DaySpan):
            raise BadValueError("span", self.span, "want a day span")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise BadValueError("reason", self.reason, "want some text")
        object.__setattr__(self, "reason", " ".join(self.reason.split()))
        if self.window is not None:
            if not isinstance(self.window, Window):
                raise BadValueError("window", self.window, "want a window")
            if self.window.empty:
                raise BadValueError("window", self.window, "an embargo of no minutes")
        if self.counties is not None:
            tidy = frozenset(" ".join(c.split()) for c in self.counties)
            if not tidy or any(not c for c in tidy):
                raise BadValueError("counties", self.counties, "want at least one county")
            object.__setattr__(self, "counties", tidy)
        if not isinstance(self.weekends_only, bool):
            raise BadValueError("weekends only", self.weekends_only, "want true or false")

    @property
    def statewide(self) -> bool:
        """Does this order cover the whole state."""
        return self.counties is None

    @property
    def all_day(self) -> bool:
        """Does this order cover whole days rather than a window."""
        return self.window is None

    def covers_county(self, county: str) -> bool:
        """Is this county inside the order."""
        if self.counties is None:
            return True
        return " ".join(county.split()) in self.counties

    def covers_day(self, day: Day) -> bool:
        """Is this day inside the order."""
        if not self.span.covers(day):
            return False
        return not self.weekends_only or day.weekday() in WEEKEND

    def blocks(self, day: Day, minute: int, county: str) -> bool:
        """Is movement stopped at this moment, here."""
        if not self.covers_day(day) or not self.covers_county(county):
            return False
        if self.window is None:
            return True
        return self.window.covers(minute)

    def __str__(self) -> str:
        where = STATEWIDE if self.counties is None else f"{len(self.counties)} counties"
        when = "all day" if self.window is None else str(self.window)
        return f"{self.code} {self.span} {when} {where}: {self.reason}"


@dataclass(frozen=True, slots=True)
class EmbargoBook:
    """Every embargo the office has on the books."""

    embargoes: tuple[Embargo, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "embargoes", tuple(sorted(self.embargoes)))
        seen = [e.code for e in self.embargoes]
        if len(set(seen)) != len(seen):
            raise BadValueError("embargoes", seen, "two orders share a code")

    def blocking(self, day: Day, minute: int, county: str) -> tuple[Embargo, ...]:
        """Every order stopping movement at this moment, here."""
        return tuple(e for e in self.embargoes if e.blocks(day, minute, county))

    def on_day(self, day: Day, county: str) -> tuple[Embargo, ...]:
        """Every order touching this day here, whatever the hour."""
        return tuple(e for e in self.embargoes if e.covers_day(day) and e.covers_county(county))

    def free(self, day: Day, minute: int, county: str) -> bool:
        """May a load move at this moment, here."""
        return not self.blocking(day, minute, county)

    def __len__(self) -> int:
        return len(self.embargoes)

    def __iter__(self) -> Iterator[Embargo]:
        return iter(self.embargoes)
