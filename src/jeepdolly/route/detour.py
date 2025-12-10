"""What a closure costs, and whether there is a way round it at all.

Two questions the office is asked constantly. The bridge crew rings to say a
structure is coming down for six weeks; which permits does that break, and how
far round do they have to go? A county closes a stretch for a fair; same
question.

The answer is the ordinary clearing search run twice, once with the stretch and
once without. What makes it useful is the comparison rather than either route,
so that is what comes back: both, and the difference.

A detour is worked out against a rig, not against the map in the abstract. The
long way round a posted bridge is not a detour for a legal load and is the only
way for a heavy one, and telling a carrier the wrong one of those wastes a day.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.network import Network
from jeepdolly.route.plan import Leg, Route
from jeepdolly.route.search import Passable, ends_of, passable_for, search_between
from jeepdolly.units.distance import Miles, format_distance, hundredths

__all__ = ["Detour", "affected", "detour_for", "without"]


def without(base: Passable, closed: Iterable[str]) -> Passable:
    """A passability test that also refuses a set of closed stretches."""
    shut = {str(code(str(one))) for one in closed}
    if not shut:
        raise BadValueError("closed", closed, "want at least one stretch")

    def usable(leg: Leg) -> bool:
        return str(leg.segment.code) not in shut and base(leg)

    return usable


@dataclass(frozen=True, slots=True)
class Detour:
    """The route before a closure and the route after it."""

    origin: Code
    destination: Code
    closed: tuple[Code, ...]
    usual: Route | None
    instead: Route | None

    @property
    def affected(self) -> bool:
        """Did the closure touch the route this rig would normally take."""
        if self.usual is None:
            return False
        used = {str(s.code) for s in self.usual.segments}
        return any(str(one) in used for one in self.closed)

    @property
    def stranded(self) -> bool:
        """Is there no way through at all once the closure is in."""
        return self.instead is None

    @property
    def extra(self) -> Miles:
        """How much further the detour is, or zero when nothing changed."""
        if self.usual is None or self.instead is None:
            return hundredths(0)
        return hundredths(max(0, int(self.instead.distance) - int(self.usual.distance)))

    def __str__(self) -> str:
        shut = ", ".join(str(one) for one in self.closed)
        if self.usual is None:
            return f"{self.origin} to {self.destination}: no route even before closing {shut}"
        if not self.affected:
            return f"{self.origin} to {self.destination}: {shut} is not on the route"
        if self.instead is None:
            return f"{self.origin} to {self.destination}: nothing gets through without {shut}"
        return (
            f"{self.origin} to {self.destination}: {format_distance(self.extra)} further"
            f" without {shut}"
        )


def detour_for(
    network: Network,
    origin: str,
    destination: str,
    config: Configuration,
    load: Load,
    closed: Iterable[str],
) -> Detour:
    """Work out what closing some stretches does to one rig's run."""
    start, finish = ends_of(network, origin, destination)
    shut = tuple(code(str(one)) for one in closed)
    for one in shut:
        network.segment(str(one))
    base = passable_for(network, config, load)
    usual = search_between(network, start, finish, base)
    instead = search_between(network, start, finish, without(base, shut))
    return Detour(origin=start, destination=finish, closed=shut, usual=usual, instead=instead)


def affected(route: Route, closed: Iterable[str]) -> tuple[Code, ...]:
    """Which of the closed stretches this route actually uses."""
    used = {str(s.code) for s in route.segments}
    return tuple(code(str(one)) for one in closed if str(code(str(one))) in used)
