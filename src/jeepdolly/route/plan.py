"""A route: an ordered run of stretches, each with a direction.

The direction matters and is not implied by the segment. ``SEG-AB`` between
junctions A and B is one record; travelling it from B to A is a different leg,
and a one way segment only makes one of the two. Storing the direction on the
leg rather than deriving it later is what stops a route sheet printing the
stops in the wrong order.

A route is contiguous by construction. Every leg starts where the last one
ended, and the constructor refuses anything else rather than routing around it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.roadway.network import Network
from jeepdolly.roadway.segment import Segment
from jeepdolly.units.distance import Miles, format_distance, total_distance

__all__ = ["Leg", "Route", "along_segments", "through_nodes"]


@dataclass(frozen=True, slots=True)
class Leg:
    """One stretch, travelled in one direction."""

    segment: Segment
    from_node: Code
    to_node: Code

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_node", code(str(self.from_node)))
        object.__setattr__(self, "to_node", code(str(self.to_node)))
        if not self.segment.runs(self.from_node, self.to_node):
            raise BadValueError(
                "leg",
                f"{self.from_node}->{self.to_node}",
                f"{self.segment.code} does not run that way",
            )

    @property
    def distance(self) -> Miles:
        """How far this leg is."""
        return self.segment.distance

    @property
    def reversed(self) -> bool:
        """Is the leg travelled against the segment's own direction."""
        return self.from_node == self.segment.end

    def __str__(self) -> str:
        return (
            f"{self.segment.route} {self.from_node} to {self.to_node}"
            f" ({format_distance(self.distance)})"
        )


@dataclass(frozen=True, slots=True)
class Route:
    """An ordered, contiguous run of legs."""

    legs: tuple[Leg, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "legs", tuple(self.legs))
        if not self.legs:
            raise BadValueError("route", "empty", "a route has at least one leg")
        for ahead, behind in pairwise(self.legs):
            if ahead.to_node != behind.from_node:
                raise BadValueError(
                    "route",
                    f"{ahead.to_node} then {behind.from_node}",
                    "the legs do not join up",
                )

    @property
    def origin(self) -> Code:
        """Where the run starts."""
        return self.legs[0].from_node

    @property
    def destination(self) -> Code:
        """Where the run ends."""
        return self.legs[-1].to_node

    @property
    def distance(self) -> Miles:
        """How far the whole run is."""
        return total_distance(leg.distance for leg in self.legs)

    @property
    def segments(self) -> tuple[Segment, ...]:
        """The stretches travelled, in order."""
        return tuple(leg.segment for leg in self.legs)

    @property
    def nodes(self) -> tuple[Code, ...]:
        """Every junction touched, in order, start and finish included."""
        return (self.origin, *[leg.to_node for leg in self.legs])

    @property
    def revisits(self) -> bool:
        """Does the run pass through the same junction twice."""
        seen = self.nodes
        return len(set(seen)) != len(seen)

    def __len__(self) -> int:
        return len(self.legs)

    def __str__(self) -> str:
        return (
            f"{self.origin} to {self.destination},"
            f" {len(self.legs)} legs, {format_distance(self.distance)}"
        )


def along_segments(network: Network, origin: str, segments: Sequence[str]) -> Route:
    """Build a route from a start junction and an ordered list of stretch codes."""
    if not segments:
        raise BadValueError("route", "empty", "a route has at least one leg")
    here = code(str(origin))
    network.node(str(here))
    legs: list[Leg] = []
    for key in segments:
        segment = network.segment(str(key))
        if here not in (segment.start, segment.end):
            raise BadValueError("route", key, f"does not touch {here}")
        legs.append(Leg(segment=segment, from_node=here, to_node=segment.other_end(here)))
        here = legs[-1].to_node
    return Route(legs=tuple(legs))


def through_nodes(network: Network, nodes: Sequence[str]) -> Route:
    """Build a route from an ordered list of junctions.

    Where two stretches connect the same pair of junctions the shorter one is
    taken. That is a convenience for the counter and not a routing decision; a
    clerk who wants the longer one names the segments instead.
    """
    if len(nodes) < 2:
        raise BadValueError("route", nodes, "want at least two junctions")
    legs: list[Leg] = []
    for first, second in pairwise(nodes):
        here = code(str(first))
        there = code(str(second))
        choices = network.between(str(here), str(there))
        if not choices:
            raise BadValueError("route", f"{here}->{there}", "nothing connects them")
        best = min(choices, key=lambda s: (int(s.distance), str(s.code)))
        legs.append(Leg(segment=best, from_node=here, to_node=there))
    return Route(legs=tuple(legs))
