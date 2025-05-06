"""Stretches of road between two junctions.

A segment is the unit a route is built out of and the unit a limit is posted
against. It runs between two nodes, carries a route designation like ``US-12``,
and knows which statutory limit set applies to it.

Segments are two way unless they say otherwise. A one way segment can only be
travelled from ``start`` to ``end``, which the office records for the handful of
ramps and bridges where it matters.

A segment may post its own gross limit below the statutory one. That is a local
order, usually on a county road that has been undermined, and it beats the
statute in both directions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.limits.statute import INTERSTATE, STATE_ROUTE, Statute
from jeepdolly.units.distance import Miles, hundredths
from jeepdolly.units.mass import Pounds, pounds

__all__ = ["ROUTE_PATTERN", "RoadClass", "Segment", "statute_for"]

#: ``US-12``, ``I-90``, ``SR-200``, ``CR-14A``.
ROUTE_PATTERN = re.compile(r"^(?:I|US|SR|CR|FR)-\d{1,4}[A-Z]?$")


class RoadClass(StrEnum):
    """Which limit set a stretch of road runs under."""

    INTERSTATE = "interstate"
    STATE = "state"
    LOCAL = "local"


_STATUTES: dict[RoadClass, Statute] = {
    RoadClass.INTERSTATE: INTERSTATE,
    RoadClass.STATE: STATE_ROUTE,
    RoadClass.LOCAL: STATE_ROUTE,
}


def statute_for(road_class: RoadClass) -> Statute:
    """The flat limit set that applies to a class of road."""
    return _STATUTES[RoadClass(road_class)]


@dataclass(frozen=True, slots=True, order=True)
class Segment:
    """One stretch of road between two junctions."""

    code: Code
    start: Code
    end: Code
    route: str
    distance: Miles
    road_class: RoadClass = RoadClass.STATE
    one_way: bool = False
    posted_gross: Pounds | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", code(str(self.code)))
        object.__setattr__(self, "start", code(str(self.start)))
        object.__setattr__(self, "end", code(str(self.end)))
        object.__setattr__(self, "road_class", RoadClass(self.road_class))
        object.__setattr__(self, "distance", hundredths(int(self.distance)))
        if self.start == self.end:
            raise BadValueError("segment", self.code, "starts and ends at the same node")
        if not isinstance(self.route, str):
            raise BadValueError("route", self.route, "want text")
        route = self.route.strip().upper()
        if not ROUTE_PATTERN.match(route):
            raise BadValueError("route", self.route, "want something like US-12")
        object.__setattr__(self, "route", route)
        if int(self.distance) <= 0:
            raise BadValueError("distance", int(self.distance), "want more than nothing")
        if not isinstance(self.one_way, bool):
            raise BadValueError("one way", self.one_way, "want true or false")
        if self.posted_gross is not None:
            object.__setattr__(self, "posted_gross", pounds(int(self.posted_gross)))
            if int(self.posted_gross) <= 0:
                raise BadValueError("posted gross", self.posted_gross, "want more than nothing")

    @property
    def statute(self) -> Statute:
        """The flat limits for this stretch."""
        return statute_for(self.road_class)

    @property
    def gross_limit(self) -> Pounds:
        """The gross limit that actually applies, local order included."""
        if self.posted_gross is None:
            return self.statute.gross
        return pounds(min(int(self.posted_gross), int(self.statute.gross)))

    @property
    def posted(self) -> bool:
        """Does a local order cut this segment below the statute."""
        return self.posted_gross is not None and int(self.posted_gross) < int(
            self.statute.gross
        )

    def runs(self, first: Code, second: Code) -> bool:
        """May this segment be travelled from ``first`` to ``second``."""
        if first == self.start and second == self.end:
            return True
        return not self.one_way and first == self.end and second == self.start

    def other_end(self, node: Code) -> Code:
        """The node at the far end from the one given."""
        if node == self.start:
            return self.end
        if node == self.end:
            return self.start
        raise BadValueError("node", node, f"{self.code} does not touch it")

    def __str__(self) -> str:
        arrow = "->" if self.one_way else "<->"
        return f"{self.code} {self.route} {self.start} {arrow} {self.end}"
