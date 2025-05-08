"""The whole map, assembled and checked once.

Nothing above this layer looks up a segment by scanning a list. The network is
built from the three collections, checked for the four ways they can disagree,
and then answers questions in constant time.

The checks matter more than they look. A segment pointing at a node that was
renamed, or a structure left on a segment that was retired, is the kind of thing
that produces a route the office happily prices and the driver cannot drive.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

from jeepdolly.errors import BadValueError, NotFoundError
from jeepdolly.ids.reference import Code, code
from jeepdolly.roadway.node import Node
from jeepdolly.roadway.segment import Segment
from jeepdolly.roadway.structure import Structure

__all__ = ["Link", "Network", "build"]


@dataclass(frozen=True, slots=True)
class Link:
    """One way out of a node: which segment, and where it lands."""

    segment: Segment
    to_node: Code

    def __str__(self) -> str:
        return f"{self.segment.code} to {self.to_node}"


@dataclass(frozen=True, slots=True)
class Network:
    """Junctions, the stretches between them, and what is in the way."""

    nodes: Mapping[Code, Node]
    segments: Mapping[Code, Segment]
    structures: tuple[Structure, ...]
    _links: Mapping[Code, tuple[Link, ...]] = field(repr=False)
    _on_segment: Mapping[Code, tuple[Structure, ...]] = field(repr=False)

    @property
    def node_count(self) -> int:
        """How many junctions the map has."""
        return len(self.nodes)

    @property
    def segment_count(self) -> int:
        """How many stretches the map has."""
        return len(self.segments)

    def node(self, key: str) -> Node:
        """One junction by code."""
        wanted = code(str(key))
        if wanted not in self.nodes:
            raise NotFoundError("node", str(wanted))
        return self.nodes[wanted]

    def segment(self, key: str) -> Segment:
        """One stretch by code."""
        wanted = code(str(key))
        if wanted not in self.segments:
            raise NotFoundError("segment", str(wanted))
        return self.segments[wanted]

    def links(self, key: str) -> tuple[Link, ...]:
        """Every way out of a junction, in segment code order."""
        wanted = code(str(key))
        if wanted not in self.nodes:
            raise NotFoundError("node", str(wanted))
        return self._links.get(wanted, ())

    def structures_on(self, key: str) -> tuple[Structure, ...]:
        """Everything in the way on one stretch, by milepost."""
        wanted = code(str(key))
        if wanted not in self.segments:
            raise NotFoundError("segment", str(wanted))
        return self._on_segment.get(wanted, ())

    def between(self, first: str, second: str) -> tuple[Segment, ...]:
        """Every stretch that can be travelled from one junction to another."""
        start = code(str(first))
        end = code(str(second))
        return tuple(link.segment for link in self.links(str(start)) if link.to_node == end)

    def reachable(self, key: str) -> frozenset[Code]:
        """Every junction that can be got to from this one."""
        start = code(str(key))
        self.node(str(start))
        seen = {start}
        queue = [start]
        while queue:
            here = queue.pop()
            for link in self.links(str(here)):
                if link.to_node not in seen:
                    seen.add(link.to_node)
                    queue.append(link.to_node)
        return frozenset(seen)

    @property
    def connected(self) -> bool:
        """Can every junction be got to from every other one."""
        if not self.nodes:
            return True
        first = next(iter(sorted(self.nodes)))
        return self.reachable(str(first)) == frozenset(self.nodes)

    def __iter__(self) -> Iterator[Segment]:
        for key in sorted(self.segments):
            yield self.segments[key]

    def __len__(self) -> int:
        return len(self.segments)


def _collect_nodes(nodes: Iterable[Node]) -> dict[Code, Node]:
    """Index the junctions, refusing a code that turns up twice."""
    by_node: dict[Code, Node] = {}
    for node in nodes:
        if node.code in by_node:
            raise BadValueError("node", node.code, "listed twice")
        by_node[node.code] = node
    return by_node


def _collect_segments(
    segments: Iterable[Segment], by_node: Mapping[Code, Node]
) -> dict[Code, Segment]:
    """Index the stretches, refusing a repeat or an end that is not a node."""
    by_segment: dict[Code, Segment] = {}
    for segment in segments:
        if segment.code in by_segment:
            raise BadValueError("segment", segment.code, "listed twice")
        for end in (segment.start, segment.end):
            if end not in by_node:
                raise BadValueError("segment", segment.code, f"{end} is not a node")
        by_segment[segment.code] = segment
    return by_segment


def _collect_structures(
    structures: Iterable[Structure], by_segment: Mapping[Code, Segment]
) -> list[Structure]:
    """List what is in the way, refusing a repeat or a stretch that is not there."""
    held: list[Structure] = []
    seen: set[str] = set()
    for structure in structures:
        if str(structure.reference) in seen:
            raise BadValueError("structure", structure.reference, "listed twice")
        if structure.segment not in by_segment:
            raise BadValueError(
                "structure", structure.reference, f"{structure.segment} is not a segment"
            )
        seen.add(str(structure.reference))
        held.append(structure)
    return held


def build(
    nodes: Iterable[Node],
    segments: Iterable[Segment],
    structures: Iterable[Structure] = (),
) -> Network:
    """Assemble a network, refusing the four ways the parts disagree."""
    by_node = _collect_nodes(nodes)
    by_segment = _collect_segments(segments, by_node)
    held = _collect_structures(structures, by_segment)

    links: dict[Code, list[Link]] = defaultdict(list)
    for segment in by_segment.values():
        links[segment.start].append(Link(segment=segment, to_node=segment.end))
        if not segment.one_way:
            links[segment.end].append(Link(segment=segment, to_node=segment.start))

    on_segment: dict[Code, list[Structure]] = defaultdict(list)
    for structure in held:
        on_segment[structure.segment].append(structure)

    return Network(
        nodes=dict(sorted(by_node.items())),
        segments=dict(sorted(by_segment.items())),
        structures=tuple(sorted(held)),
        _links={
            key: tuple(sorted(value, key=lambda link: str(link.segment.code)))
            for key, value in sorted(links.items())
        },
        _on_segment={
            key: tuple(sorted(value, key=lambda s: (int(s.milepost), str(s.reference))))
            for key, value in sorted(on_segment.items())
        },
    )
