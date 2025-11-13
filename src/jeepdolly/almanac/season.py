"""Frost laws and the winter weight premium.

For six weeks in spring the subgrade under a secondary road turns to soup and
the county drops the axle limits, usually to sixty percent. For three months in
midwinter the same road is frozen solid and a handful of them go the other way
and allow more. Both are seasonal orders against a set of counties, both have a
start and an end day, and both are the same shape, so they are one type with a
percentage rather than two types with opposite names.

A percentage under a hundred is a restriction and over a hundred is a premium.
Exactly a hundred is refused, because an order that changes nothing is an order
somebody entered wrong.

Scaled limits round *down* to the nearest hundred pounds. Rounding a restriction
up would hand back weight the order took away.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.limits.statute import Statute
from jeepdolly.units.clock import Day, DaySpan
from jeepdolly.units.mass import Pounds, pounds

__all__ = ["MAX_PERCENT", "MIN_PERCENT", "ROUND_TO", "Season", "SeasonBook"]

#: Scaled limits land on a multiple of this.
ROUND_TO = 100

MIN_PERCENT = 25
MAX_PERCENT = 150


def _scale(weight: Pounds, percent: int) -> Pounds:
    """Apply a percentage and round down to the nearest hundred pounds."""
    return pounds(int(weight) * percent // 100 // ROUND_TO * ROUND_TO)


@dataclass(frozen=True, slots=True, order=True)
class Season:
    """One seasonal order against a set of counties."""

    code: Code
    span: DaySpan
    percent: int
    counties: frozenset[str]
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", code(str(self.code)))
        if not isinstance(self.span, DaySpan):
            raise BadValueError("span", self.span, "want a day span")
        if isinstance(self.percent, bool) or not isinstance(self.percent, int):
            raise BadValueError("percent", self.percent, "want a whole number")
        if not MIN_PERCENT <= self.percent <= MAX_PERCENT:
            raise BadValueError("percent", self.percent, f"want {MIN_PERCENT} to {MAX_PERCENT}")
        if self.percent == 100:
            raise BadValueError("percent", self.percent, "an order that changes nothing")
        tidy = frozenset(" ".join(c.split()) for c in self.counties)
        if not tidy or any(not c for c in tidy):
            raise BadValueError("counties", self.counties, "want at least one county")
        object.__setattr__(self, "counties", tidy)
        if not isinstance(self.note, str):
            raise BadValueError("note", self.note, "want text")

    @property
    def restricting(self) -> bool:
        """Does this order take weight away."""
        return self.percent < 100

    @property
    def premium(self) -> bool:
        """Does this order allow more weight than usual."""
        return self.percent > 100

    def covers(self, day: Day, county: str) -> bool:
        """Is this order in force here on this day."""
        return self.span.covers(day) and " ".join(county.split()) in self.counties

    def applied(self, statute: Statute) -> Statute:
        """The limit set as this order leaves it."""
        return Statute(
            name=f"{statute.name} under {self.code}",
            single=_scale(statute.single, self.percent),
            tandem=_scale(statute.tandem, self.percent),
            gross=_scale(statute.gross, self.percent),
            tandem_low=statute.tandem_low,
            tandem_high=statute.tandem_high,
        )

    def __str__(self) -> str:
        way = "down to" if self.restricting else "up to"
        return f"{self.code} {self.span} {way} {self.percent}% in {len(self.counties)} counties"


@dataclass(frozen=True, slots=True)
class SeasonBook:
    """Every seasonal order the office has on the books."""

    seasons: tuple[Season, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "seasons", tuple(sorted(self.seasons)))
        seen = [s.code for s in self.seasons]
        if len(set(seen)) != len(seen):
            raise BadValueError("seasons", seen, "two orders share a code")

    def in_force(self, day: Day, county: str) -> tuple[Season, ...]:
        """Every order in force in one county on one day, code order."""
        return tuple(s for s in self.seasons if s.covers(day, county))

    def statute_on(self, statute: Statute, day: Day, county: str) -> Statute:
        """The limit set after every order in force is applied.

        Orders stack in code order. Two restrictions on the same county on the
        same day is a data entry mistake the office would rather see than
        silently take the harsher of, so both are applied and the result is
        harsher than either.
        """
        result = statute
        for season in self.in_force(day, county):
            result = season.applied(result)
        return result

    def over(self, day: Day, counties: Iterable[str]) -> tuple[Season, ...]:
        """Every order in force on one day in any of these counties.

        An order covering two of the counties is listed once. The route is one
        move and the order applies to it or it does not.
        """
        wanted: list[Season] = []
        for season in self.seasons:
            if any(season.covers(day, county) for county in counties):
                wanted.append(season)
        return tuple(wanted)

    def statute_over(self, statute: Statute, day: Day, counties: Iterable[str]) -> Statute:
        """The limit set after every order touching any of these counties.

        A route crossing three counties runs under the orders of all three, and
        the harshest of them decides. The office does not let a load run heavy
        through one county because the next one is thawed out.
        """
        result = statute
        for season in self.over(day, counties):
            result = season.applied(result)
        return result

    def __len__(self) -> int:
        return len(self.seasons)

    def __iter__(self) -> Iterator[Season]:
        return iter(self.seasons)
