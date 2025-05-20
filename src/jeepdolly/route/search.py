"""Finding a way through.

Two searches, and the difference between them is the whole point of the office.

``shortest`` is the ordinary one: fewest miles from here to there, ignoring what
is on the rig. ``clearing`` is the one a clerk actually runs: fewest miles from
here to there *that this rig can be driven on*, which usually means the long way
round a posted bridge.

Both are Dijkstra over junctions with distance as the cost. Ties break on the
segment code so that the same question asked twice gets the same answer, which
matters when a permit is reissued after an amendment and the route sheet has to
match the one the driver already has.

A blocked leg is skipped rather than penalised. There is no fee that buys a
fifteen foot load under a fourteen foot bridge, so a search that weighted it
heavily and still returned it would be lying.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from jeepdolly.errors import BadValueError
from jeepdolly.ids.reference import Code, code
from jeepdolly.rig.config import Configuration
from jeepdolly.rig.load import Load
from jeepdolly.roadway.network import Network
from jeepdolly.route.clear import check_leg
from jeepdolly.route.plan import Leg, Route
from jeepdolly.units.distance import Miles

__all__ = [
    "Passable",
    "cheapest_distance",
    "clearing",
    "every_route",
    "passable_for",
    "shortest",
]

#: Answers whether one leg may be used at all.
Passable = Callable[[Leg], bool]


def _always(leg: Leg) -> bool:  # noqa: ARG001
    """Every leg is usable. The argument is the protocol, not a mistake."""
    return True


@dataclass(frozen=True, slots=True)
class _Step:
    """A node reached, and the leg that reached it."""

    node: Code
    leg: Leg | None


def _relax(
    network: Network,
    passable: Passable,
    here: Code,
    cost: int,
    best: dict[Code, int],
    came: dict[Code, _Step],
    queue: list[tuple[int, str, Code]],
) -> None:
    """Try every way out of one junction and keep the ones that improve."""
    for link in network.links(str(here)):
        leg = Leg(segment=link.segment, from_node=here, to_node=link.to_node)
        if not passable(leg):
            continue
        step = cost + int(leg.distance)
        if link.to_node in best and best[link.to_node] <= step:
            continue
        best[link.to_node] = step
        came[link.to_node] = _Step(node=here, leg=leg)
        heapq.heappush(queue, (step, str(link.segment.code), link.to_node))


def _unwind(came: dict[Code, _Step], destination: Code) -> Route | None:
    """Walk the predecessors back to the start and turn them into a route."""
    if destination not in came:
        return None
    legs: list[Leg] = []
    here = destination
    while came[here].leg is not None:
        step = came[here]
        assert step.leg is not None
        legs.append(step.leg)
        here = step.node
    legs.reverse()
    if not legs:
        return None
    return Route(legs=tuple(legs))


def _search(
    network: Network, origin: Code, destination: Code, passable: Passable
) -> Route | None:
    """Dijkstra from one junction to another over the passable legs."""
    best: dict[Code, int] = {origin: 0}
    came: dict[Code, _Step] = {origin: _Step(node=origin, leg=None)}
    queue: list[tuple[int, str, Code]] = [(0, "", origin)]
    settled: set[Code] = set()
    while queue:
        cost, _, here = heapq.heappop(queue)
        if here in settled:
            continue
        settled.add(here)
        if here == destination:
            break
        _relax(network, passable, here, cost, best, came, queue)
    return _unwind(came, destination)


def _ends(network: Network, origin: str, destination: str) -> tuple[Code, Code]:
    start = code(str(origin))
    finish = code(str(destination))
    network.node(str(start))
    network.node(str(finish))
    if start == finish:
        raise BadValueError("route", start, "starts and ends at the same junction")
    return start, finish


def shortest(network: Network, origin: str, destination: str) -> Route | None:
    """The fewest miles from one junction to another, whatever is on the rig."""
    start, finish = _ends(network, origin, destination)
    return _search(network, start, finish, _always)


def passable_for(network: Network, config: Configuration, load: Load) -> Passable:
    """A test that says whether one leg can carry this rig and load."""
    gross = config.gross
    height = load.height

    def usable(leg: Leg) -> bool:
        return not any(finding.blocking for finding in check_leg(leg, network, gross, height))

    return usable


def clearing(
    network: Network, origin: str, destination: str, config: Configuration, load: Load
) -> Route | None:
    """The fewest miles this rig can actually be driven, or nothing."""
    start, finish = _ends(network, origin, destination)
    return _search(network, start, finish, passable_for(network, config, load))


def every_route(
    network: Network, origin: str, destination: str, max_legs: int = 6
) -> Iterator[Route]:
    """Every route that does not revisit a junction, shortest first.

    This is exponential and it is here for the handful of times a clerk wants to
    see the alternatives rather than the best one. ``max_legs`` is a hard stop,
    not a suggestion.
    """
    start, finish = _ends(network, origin, destination)
    if isinstance(max_legs, bool) or not isinstance(max_legs, int) or max_legs < 1:
        raise BadValueError("max legs", max_legs, "want at least one")
    found: list[Route] = []

    def walk_on(here: Code, seen: frozenset[Code], legs: list[Leg]) -> None:
        if len(legs) >= max_legs:
            return
        for link in network.links(str(here)):
            if link.to_node in seen:
                continue
            leg = Leg(segment=link.segment, from_node=here, to_node=link.to_node)
            legs.append(leg)
            if link.to_node == finish:
                found.append(Route(legs=tuple(legs)))
            else:
                walk_on(link.to_node, seen | {link.to_node}, legs)
            legs.pop()

    walk_on(start, frozenset({start}), [])
    yield from sorted(found, key=lambda r: (int(r.distance), [str(s.code) for s in r.segments]))


def cheapest_distance(network: Network, origin: str, destination: str) -> Miles | None:
    """How far the shortest route is, or nothing if there is none."""
    found = shortest(network, origin, destination)
    return None if found is None else found.distance
